"""Reversible, hash-guarded 1007 variants. Never write archived frontend files."""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Experiments:
    def __init__(self, root, versions):
        self.root = Path(root)
        self.versions = versions
        raw = (self.root / "web/experiments-1007.json").read_bytes()
        self.definition_sha256 = sha(raw)
        self.definition = json.loads(raw)
        self.features = self.definition["features"]
        self.ids = [d["id"] for d in self.features]
        self.cache = OrderedDict()

    def disabled(self, version, value=""):
        items = set(filter(None, value.split(",")))
        if items and version != "20261007":
            raise ValueError("这些改动开关只适用于 10/07")
        if items - set(self.ids):
            raise ValueError("未知改动开关：" + ",".join(sorted(items - set(self.ids))))
        return tuple(key for key in self.ids if key in items)

    def asset_versions(self, version, disabled=()):
        selected = dict.fromkeys(("js", "css", "html", "plugin"), version)
        for feature in self.features:
            if feature["id"] in disabled:
                selected.update(feature.get("restore_assets", {}))
        if version == "20261007" and "review_updates" in disabled:
            selected["plugin"] = "20261004"
        return selected

    def source_plan(self, version, disabled=()):
        selected = [(f, op) for f in self.features if f["id"] in disabled for op in f["source"]]
        whole_files = {op["file"] for _, op in selected if op.get("whole_module")}
        restored_js = self.asset_versions(version, disabled)["js"] != version
        operations, skipped = [], []
        for feature, op in sorted(selected, key=lambda item: not item[1].get("whole_module", False)):
            shared = feature["commit"] == "shared"
            reason = "完整脚本已回退" if restored_js and not shared else (
                "所属模块已整体回退" if not shared and not op.get("whole_module") and op["file"] in whole_files else "")
            if reason:
                skipped.append({"feature": feature["id"], "name": op["name"], "reason": reason})
            else:
                operations.append(dict(op, feature=feature["id"]))
        return operations, skipped

    def asset(self, version, kind, disabled=()):
        key = version, kind, tuple(disabled)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        config = self.versions[version]
        original = (self.root / "versions" / version / "site" / config[kind].lstrip("/")).read_bytes()
        if sha(original) != config[kind + "_sha256"]:
            raise ValueError("归档资源校验失败：" + version + " " + kind)
        operations = []
        source_version = self.asset_versions(version, disabled)[kind]
        source_config = self.versions[source_version]
        data = (self.root / "versions" / source_version / "site" / source_config[kind].lstrip("/")).read_bytes()
        if sha(data) != source_config[kind + "_sha256"]:
            raise ValueError("回退资源校验失败：" + source_version + " " + kind)
        if source_version != version:
            operations.append("1004 完整" + kind + "资源")
        if disabled:
            if version != self.definition["version"] or config[kind + "_sha256"] != self.definition["base_" + kind + "_sha256"]:
                raise ValueError("改动开关与归档资源不匹配")
            text = data.decode("utf-8")
            applied = set()
            for feature in self.features:
                if feature["id"] not in disabled:
                    continue
                if kind == "js":
                    if source_version != version:
                        continue
                    for op in feature["module"]:
                        if op["before"] in applied:
                            continue
                        if text.count(op["before"]) != 1:
                            raise ValueError("模块开关适配失败：" + op["name"])
                        text = text.replace(op["before"], op["after"], 1)
                        operations.append(feature["id"] + ":" + op["name"])
                        applied.add(op["before"])
                elif feature["css"] and (source_version == version or feature["commit"] == "shared"):
                    text += "\n/* Replay experiment: " + feature["id"] + " */\n" + feature["css"] + "\n"
                    operations.append(feature["id"])
            data = text.encode("utf-8")
        receipt = {"base_sha256": sha(original), "source_version": source_version,
                   "source_sha256": source_config[kind + "_sha256"], "served_sha256": sha(data), "operations": operations}
        self.cache[key] = data, receipt
        while len(self.cache) > 32:
            self.cache.popitem(last=False)
        return data, receipt

    def plugin(self, version, relative, disabled=()):
        plugin_version = self.asset_versions(version, disabled)["plugin"]
        return self.root / "versions" / plugin_version / "plugins", relative

    def config(self, version, disabled=()):
        _, js = self.asset(version, "js", disabled)
        _, css = self.asset(version, "css", disabled)
        result = {"supported": version == "20261007", "disabled": list(disabled), "js": js, "css": css,
                  "features": [], "source_operations": [], "uncovered": self.definition["uncovered"],
                  "definition_sha256": self.definition_sha256}
        result["follow_mode"] = "off" if "auto_follow" in disabled else "immediate" if "smooth_follow" in disabled else "smooth"
        result["asset_versions"] = self.asset_versions(version, disabled)
        html_path = self.root / "versions" / result["asset_versions"]["html"] / "site/index.html"
        result["html_source_sha256"] = sha(html_path.read_bytes())
        result["source_operations"], result["covered_operations"] = self.source_plan(version, disabled)
        if result["supported"]:
            for d in self.features:
                result["features"].append({k: d[k] for k in ("id", "label", "commit", "scope", "description")})
        result["label"] = "1007 原版（全部开启）" if result["supported"] and not disabled else (
            "关闭：" + "、".join(d["label"] for d in self.features if d["id"] in disabled) if disabled else "原版")
        root, _ = self.plugin(version, "", disabled)
        result["plugin_version"] = result["asset_versions"]["plugin"]
        result["plugin_sha256"] = {kind: sha((root / "change-review/web" / ("change-review." + kind)).read_bytes()) for kind in ("js", "css")}
        identity = json.dumps({"version": version, "disabled": list(disabled), "js": js["served_sha256"], "css": css["served_sha256"],
                               "plugin": result["plugin_sha256"], "html": result["html_source_sha256"],
                               "asset_versions": result["asset_versions"], "definition": self.definition_sha256}, sort_keys=True).encode()
        result["fingerprint"] = sha(identity)[:16]
        return result
