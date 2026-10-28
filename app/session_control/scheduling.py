"""Pure scheduling arithmetic, sampled clocks, and typed event predicates."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ControlError

UTC = timezone.utc


def instant(value):
    if not isinstance(value, str):
        raise ControlError("invalid_schedule", "at must be an offset-bearing ISO timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("offset required")
        return dt.timestamp()
    except (ValueError, OverflowError) as exc:
        raise ControlError("invalid_schedule", "Invalid absolute timestamp") from exc


def validate_trigger(raw, now):
    if not isinstance(raw, dict):
        raise ControlError("invalid_schedule", "trigger must be an object")
    trigger = dict(raw)
    kind = trigger.get("kind")
    if kind == "event":
        if not isinstance(trigger.get("types"), list) or not trigger["types"] or any(not isinstance(x, str) for x in trigger["types"]):
            raise ControlError("invalid_rule", "Event trigger requires types")
        match_condition(trigger.get("condition"), {}, validate_only=True)
        return trigger, None
    if kind == "after":
        delay = trigger.get("seconds")
        if type(delay) not in {int, float} or not math.isfinite(delay) or delay <= 0:
            raise ControlError("invalid_schedule", "Delay must be positive")
        trigger = {"kind": "at", "at": datetime.fromtimestamp(now + delay, UTC).isoformat()}
        return trigger, now + delay
    if kind == "at":
        target = instant(trigger.get("at"))
        if target <= now:
            raise ControlError("invalid_schedule", "One-shot time must be in the future")
        return trigger, target
    if kind == "interval":
        seconds = trigger.get("seconds")
        if type(seconds) not in {int, float} or not math.isfinite(seconds) or seconds < 60:
            raise ControlError("invalid_schedule", "Interval must be at least 60 seconds")
        trigger["anchor"] = now
        return trigger, now + seconds
    if kind in {"daily", "weekdays", "weekly", "monthly"}:
        try:
            clock = datetime.strptime(trigger.get("time", "09:00"), "%H:%M")
        except (ValueError, TypeError) as exc:
            raise ControlError("invalid_schedule", "time must be HH:MM") from exc
        day, week = "*", "*"
        if kind == "weekdays":
            week = "1-5"
        elif kind == "weekly":
            days = trigger.get("weekdays", [])
            if not isinstance(days, list) or not days or any(type(d) is not int or not 1 <= d <= 7 for d in days):
                raise ControlError("invalid_schedule", "weekdays must contain ISO weekdays 1-7")
            week = ",".join(str(d % 7) for d in sorted(set(days)))
        elif kind == "monthly":
            days = trigger.get("days", [])
            if not isinstance(days, list) or not days or any(type(d) is not int or not 1 <= d <= 31 for d in days):
                raise ControlError("invalid_schedule", "days must contain month days 1-31")
            day = ",".join(str(d) for d in sorted(set(days)))
        trigger = {"kind": "cron", "expression": f"{clock.minute} {clock.hour} {day} * {week}",
                   "time_zone": trigger.get("time_zone", "Asia/Shanghai")}
        kind = "cron"
    if kind == "cron":
        expression = trigger.get("expression", "")
        if not isinstance(expression, str) or len(expression.split()) != 5:
            raise ControlError("invalid_schedule", "Cron requires exactly five fields")
        if any(c not in "0123456789*/,- " for c in expression):
            raise ControlError("invalid_schedule", "Only numeric five-field cron syntax is supported")
        trigger["time_zone"] = trigger.get("time_zone", "Asia/Shanghai")
        try:
            ZoneInfo(trigger["time_zone"])
            from croniter import croniter
            if not croniter.is_valid(expression):
                raise ValueError("Invalid cron")
        except ImportError as exc:
            raise ControlError("dependency_missing", "Install app requirements (croniter and tzdata)", status=409) from exc
        except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
            raise ControlError("invalid_schedule", "Invalid cron expression or IANA zone") from exc
        return trigger, next_time(trigger, now)
    raise ControlError("invalid_schedule", "Unsupported trigger kind")


def next_time(trigger, now):
    kind = trigger["kind"]
    if kind in {"at", "event"}:
        return None
    if kind == "interval":
        anchor, interval = trigger["anchor"], trigger["seconds"]
        return anchor + (math.floor((now - anchor) / interval) + 1) * interval
    from croniter import croniter
    zone = ZoneInfo(trigger["time_zone"])
    # Iterate local naive calendar candidates, then validate their actual instants.
    # This avoids treating a spring gap as a shifted reminder or firing both folds.
    local = datetime.fromtimestamp(now, zone).replace(tzinfo=None)
    iterator = croniter(trigger["expression"], local)
    for _ in range(10000):
        candidate = iterator.get_next(datetime)
        aware = candidate.replace(tzinfo=zone, fold=0)
        stamp = aware.timestamp()
        if datetime.fromtimestamp(stamp, zone).replace(tzinfo=None) == candidate and stamp > now:
            return stamp
    raise ControlError("invalid_schedule", "No future occurrence found")


def latest_due(trigger, due, now):
    if trigger["kind"] == "interval":
        return due + math.floor((now - due) / trigger["seconds"]) * trigger["seconds"]
    if trigger["kind"] == "cron":
        from croniter import croniter
        zone = ZoneInfo(trigger["time_zone"])
        sample = datetime.fromtimestamp(now + .001, zone).replace(tzinfo=None)
        it = croniter(trigger["expression"], sample)
        for _ in range(10000):
            local = it.get_prev(datetime)
            stamp = local.replace(tzinfo=zone, fold=0).timestamp()
            if due <= stamp <= now and datetime.fromtimestamp(stamp, zone).replace(tzinfo=None) == local:
                return stamp
            if stamp < due:
                break
        return due
    return due


def match_condition(rule, event, *, validate_only=False, depth=0):
    if rule is None:
        return True
    if depth > 10 or not isinstance(rule, dict):
        raise ControlError("invalid_rule", "Invalid condition")
    if "all" in rule or "any" in rule:
        key = "all" if "all" in rule else "any"
        if set(rule) != {key} or not isinstance(rule[key], list) or not 1 <= len(rule[key]) <= 50:
            raise ControlError("invalid_rule", "Invalid condition group")
        values = [match_condition(r, event, validate_only=validate_only, depth=depth + 1) for r in rule[key]]
        return all(values) if key == "all" else any(values)
    if set(rule) != {"field", "op", "value"} or not isinstance(rule["field"], str):
        raise ControlError("invalid_rule", "Condition requires field, op and value")
    op = rule["op"]
    if op not in {"eq", "ne", "contains", "in", "gt", "gte", "lt", "lte"}:
        raise ControlError("invalid_rule", "Unsupported condition operator")
    if validate_only:
        return True
    value = event
    for field in rule["field"].split("."):
        if not isinstance(value, dict) or field not in value:
            return False
        value = value[field]
    other = rule["value"]
    if op in {"eq", "ne"}:
        equal = type(value) is type(other) and value == other
        return equal if op == "eq" else not equal
    if op == "contains":
        return isinstance(value, (str, list)) and isinstance(other, str) and other in value
    if op == "in":
        return isinstance(other, list) and any(type(value) is type(x) and value == x for x in other)
    if type(value) not in {int, float} or type(other) not in {int, float}:
        return False
    return {"gt": value > other, "gte": value >= other, "lt": value < other, "lte": value <= other}[op]
