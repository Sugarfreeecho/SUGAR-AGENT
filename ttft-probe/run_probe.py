"""TTFT A/B runner.

Reads the model profile straight from model_profiles.json (UTF-8, secrets never
echoed), then runs the four arms of a 2x2 factorial:

              | DSH body shape        | MyAgent body shape
    ----------|-----------------------|--------------------
    node fetch| node:dsh  <-- DSH     | node:myagent
    openai SDK| py:dsh                | py:myagent <-- MyAgent

The two highlighted arms are the faithful reproductions; the other two isolate
whether any difference comes from the request shape or from the HTTP stack.

Every trial uses the same fresh (cache-cold) prompt for all arms and a
randomized arm order, so provider-side load drift and prompt-cache warmth are
spread evenly instead of landing on one arm.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_ID = "63193ce01d724a0084a1fd850c7f397b"
PROFILES_PATH = os.path.join(os.path.dirname(HERE), "model_profiles.json")

ARMS = {
    "node:dsh": ("node", "node_probe.mjs", "dsh", {}),
    "node:dshjson": ("node", "node_probe.mjs", "dsh", {"PROBE_ACCEPT_JSON": "1"}),
    "node:myagent": ("node", "node_probe.mjs", "myagent", {}),
    "py:dsh": ("python", "py_probe.py", "dsh", {}),
    "py:myagent": ("python", "py_probe.py", "myagent", {}),
}

FAITHFUL = {"node:dsh": "DSH", "py:myagent": "MyAgent"}


def load_profile() -> dict:
    with open(PROFILES_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    for prof in data["profiles"]:
        if prof.get("id") == PROFILE_ID:
            return prof
    raise SystemExit(f"profile {PROFILE_ID} not found")


def max_tokens_for(shape: str, args) -> str:
    """The cap each implementation actually puts on the wire.

    DSH materializes the adapter default (DEFAULT_MAX_TOKENS = 256_000, see
    packages/llm/llm/src/index.ts:876-877) into the request; MyAgent sends the
    profile's max_output_tokens (50000 here).
    """
    if args.omit_max_tokens:
        return ""
    return str(args.dsh_max_tokens if shape == "dsh" else args.ma_max_tokens)


def build_env(profile: dict, shape: str, prompt: str, args, extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env.update(
        {
            "PROBE_SHAPE": shape,
            "PROBE_BASE_URL": profile["base_url"],
            "PROBE_API_KEY": profile["api_key"],
            "PROBE_MODEL": profile["model"],
            "PROBE_PROMPT": prompt,
            "PROBE_MAX_TOKENS": max_tokens_for(shape, args),
            "PROBE_TIMEOUT_MS": str(args.timeout_ms),
            "PROBE_GRACE_MS": str(args.grace_ms),
            "PROBE_WARM": "1" if args.warm else "0",
            "PROBE_VERIFY": "0" if args.no_verify else "1",
        }
    )
    env.update(extra or {})
    return env


def run_arm(arm: str, profile: dict, prompt: str, args) -> dict:
    kind, script, shape, extra = ARMS[arm]
    cmd = ["node", os.path.join(HERE, script)] if kind == "node" else [sys.executable, os.path.join(HERE, script)]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            env=build_env(profile, shape, prompt, args, extra),
            capture_output=True,
            text=True,
            timeout=args.timeout_ms / 1000.0 + 30.0,
        )
    except subprocess.TimeoutExpired:
        return {"arm": arm, "ok": False, "error": "runner timeout"}
    wall = time.time() - t0
    line = ""
    for candidate in reversed((proc.stdout or "").strip().splitlines()):
        if candidate.strip().startswith("{"):
            line = candidate.strip()
            break
    if not line:
        return {
            "arm": arm,
            "ok": False,
            "error": f"no json (rc={proc.returncode})",
            "stderr": (proc.stderr or "")[-400:],
        }
    try:
        result = json.loads(line)
    except json.JSONDecodeError as exc:
        return {"arm": arm, "ok": False, "error": f"bad json: {exc}"}
    result["arm"] = arm
    result["proc_wall_s"] = round(wall, 2)
    return result


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def summarize(rows: list[dict], key: str) -> None:
    print(f"\n== {key} (ms) ==")
    header = f"{'arm':<14}{'n':>4}{'min':>9}{'p25':>9}{'median':>9}{'p75':>9}{'max':>9}{'mean':>9}{'sd':>9}"
    print(header)
    print("-" * len(header))
    for arm in ARMS:
        vals = [r[key] for r in rows if r["arm"] == arm and r.get("ok") and r.get(key) is not None]
        if not vals:
            print(f"{arm:<14}{0:>4}   (no data)")
            continue
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        print(
            f"{arm:<14}{len(vals):>4}{min(vals):>9.1f}{pct(vals, 0.25):>9.1f}"
            f"{statistics.median(vals):>9.1f}{pct(vals, 0.75):>9.1f}{max(vals):>9.1f}"
            f"{statistics.mean(vals):>9.1f}{sd:>9.1f}"
        )


def paired(rows: list[dict], key: str, a: str, b: str) -> None:
    by_trial: dict[int, dict[str, float]] = {}
    for row in rows:
        if row.get("ok") and row.get(key) is not None:
            by_trial.setdefault(row["trial"], {})[row["arm"]] = row[key]
    diffs = [
        pair[a] - pair[b] for pair in by_trial.values() if a in pair and b in pair
    ]
    if not diffs:
        print(f"\npaired {a} - {b}: no complete pairs")
        return
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    se = sd / (len(diffs) ** 0.5) if diffs else 0.0
    wins = sum(1 for d in diffs if d < 0)
    print(
        f"\npaired ({a}) - ({b}) on {key}: n={len(diffs)} "
        f"mean={mean:+.1f}ms sd={sd:.1f} se={se:.1f} "
        f"{a}-faster-in {wins}/{len(diffs)}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--arms", default="node:dsh,node:myagent,py:dsh,py:myagent")
    ap.add_argument("--max-tokens", type=int, default=2048, help="deprecated: use --dsh/--ma-max-tokens")
    ap.add_argument("--dsh-max-tokens", type=int, default=256000)
    ap.add_argument("--ma-max-tokens", type=int, default=50000)
    ap.add_argument("--omit-max-tokens", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=120000)
    ap.add_argument("--grace-ms", type=int, default=250)
    ap.add_argument("--warm", action="store_true", help="one throwaway request per process (warm connection)")
    ap.add_argument("--no-verify", action="store_true", help="disable TLS verification (MyAgent's ssl_bypass)")
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--out", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    profile = load_profile()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for arm in arms:
        if arm not in ARMS:
            raise SystemExit(f"unknown arm {arm!r}")

    rng = random.Random(args.seed)
    print(f"target : {profile['base_url']}  model={profile['model']}")
    print(f"llm_type={profile['llm_type']} thinking={profile.get('thinking_mode')!r} "
          f"effort={profile.get('reasoning_effort')!r} max_out={profile.get('max_output_tokens')}")
    print(f"arms   : {arms}")
    print(f"trials : {args.trials}  warm={args.warm}  verify={not args.no_verify}  "
          f"max_tokens(dsh/ma)={'omit' if args.omit_max_tokens else f'{args.dsh_max_tokens}/{args.ma_max_tokens}'}"
          f"  label={args.label or '-'}")

    rows: list[dict] = []
    for trial in range(1, args.trials + 1):
        nonce = f"{rng.randrange(16**8):08x}"
        prompt = f"[nonce {nonce}] Reply with exactly one word: hello"
        order = arms[:]
        rng.shuffle(order)
        for arm in order:
            row = run_arm(arm, profile, prompt, args)
            row["trial"] = trial
            row["nonce"] = nonce
            row["order_pos"] = order.index(arm)
            rows.append(row)
            mark = "ok " if row.get("ok") else "ERR"
            ttft = row.get("ttft_ms")
            print(
                f"  t{trial:>2} {arm:<13}{mark} ttft={ttft if ttft is not None else '-'}"
                f"  hdr={row.get('t_headers_ms', '-')} kind={row.get('first_kind')}"
                + ("" if row.get("ok") else f"  {str(row.get('error'))[:110]}")
            )

    ok_rows = [r for r in rows if r.get("ok")]
    summarize(ok_rows, "ttft_ms")
    summarize(ok_rows, "t_headers_ms")
    summarize(ok_rows, "server_think_ms")
    print("\n== failures ==")
    for row in rows:
        if not row.get("ok"):
            print(f"  t{row['trial']} {row['arm']}: {str(row.get('error'))[:200]}")
    for a, b in (("node:dsh", "py:myagent"), ("node:dsh", "node:myagent"), ("py:dsh", "py:myagent")):
        if a in arms and b in arms:
            paired(ok_rows, "ttft_ms", a, b)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"label": args.label, "args": vars(args), "rows": rows}, fh, indent=2)
    print(f"\nraw results -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
