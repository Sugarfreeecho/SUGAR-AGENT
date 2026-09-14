"""Is the request SHAPE (headers/body) itself causing server-side delay?

The 2x2 probe crossed client stack with request shape. Its paired difference
`node:dsh - node:myagent` was ~ -509 ms, but medians for t_headers and server_think
looked nearly identical, so the gap must live in one of the two halves. This splits
each pair into connection (t_headers) and server (server_think) to find out which.

Also hashes the two API credentials to check whether DSH and MyAgent are even on the
same account -- different keys can route to different upstream pools/priority tiers,
which would produce exactly the constant offset the regression shows.

Usage: python ttft-probe/shape_decompose.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import statistics
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"


def load_probe_rows():
    rows = []
    for path in glob.glob(os.path.join(HERE, "*.json")):
        name = os.path.basename(path)
        if name in ("ttft_stats.json", "myagent_ttft.json"):
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        for r in data.get("rows", []):
            if r.get("ok") and r.get("ttft_ms") and r.get("t_headers_ms"):
                r["_src"] = name
                rows.append(r)
    return rows


def paired_split(rows, arm_a, arm_b):
    """arms are compared per nonce; positive means arm_b is larger."""
    by_nonce = defaultdict(dict)
    for r in rows:
        by_nonce[r["nonce"]][r["arm"]] = r
    d_head, d_think, d_total = [], [], []
    for arms in by_nonce.values():
        if arm_a in arms and arm_b in arms:
            a, b = arms[arm_a], arms[arm_b]
            d_head.append(b["t_headers_ms"] - a["t_headers_ms"])
            if a.get("server_think_ms") is not None and b.get("server_think_ms") is not None:
                d_think.append(b["server_think_ms"] - a["server_think_ms"])
            d_total.append(b["ttft_ms"] - a["ttft_ms"])
    return d_head, d_think, d_total


def main():
    rows = load_probe_rows()
    print(f"probe rows with headers+ttft: {len(rows)}")
    print(f"sources: {sorted({r['_src'] for r in rows})}")

    pairs = [
        ("node:dsh", "node:myagent", "shape effect (same stack=node)"),
        ("node:dsh", "py:myagent", "real-world combination"),
        ("node:dsh", "py:dsh", "stack effect (same shape=dsh)"),
        ("py:dsh", "py:myagent", "shape effect (same stack=py)"),
    ]
    print(f"\n{'comparison':38s} {'n':>3s} {'d(headers)':>11s} {'d(server)':>11s} {'d(total)':>10s}")
    for a, b, label in pairs:
        dh, dt, dtt = paired_split(rows, a, b)
        if not dtt:
            continue
        tag = f"{a} -> {b}"
        print(f"{tag:38s} {len(dtt):3d} {statistics.mean(dh):+11.0f} {statistics.mean(dt):+11.0f} "
              f"{statistics.mean(dtt):+10.0f}")
    print("\n  (positive = the second arm is slower; means in ms)")

    print("\n=== shape-only pairs, per source (order effects visible across runs) ===")
    for src in sorted({r["_src"] for r in rows}):
        sub = [r for r in rows if r["_src"] == src]
        for a, b, label in pairs:
            dh, dt, dtt = paired_split(sub, a, b)
            if len(dtt) >= 5:
                print(f"  {src:14s} {a} -> {b:12s} n={len(dtt):3d} "
                      f"head={statistics.mean(dh):+7.0f} server={statistics.mean(dt):+7.0f} "
                      f"total={statistics.mean(dtt):+7.0f}")

    print("\n=== credential check (hashed, never printed) ===")
    cred_path = os.path.join(os.environ.get("USERPROFILE", ""), ".dsh", ".credentials.yaml")
    dsh_key = None
    try:
        text = open(cred_path, encoding="utf-8").read()
        m = re.search(r"COMMAND_API_KEY\s*:\s*[\"']?([^\"'\s]+)", text)
        if m:
            dsh_key = m.group(1)
    except Exception as exc:
        print(f"  could not read {cred_path}: {exc}")

    ma_key = None
    try:
        profiles = json.load(open(os.path.join(WORKSPACE, "model_profiles.json"), encoding="utf-8"))
        for p in profiles.get("profiles", []):
            if p.get("model") == "deepseek/deepseek-v4.1-flash":
                ma_key = p.get("api_key")
                print(f"  MyAgent profile id={p.get('id')} base_url={p.get('base_url')}")
    except Exception as exc:
        print(f"  could not read model_profiles.json: {exc}")

    def fp(key):
        if not key:
            return "absent"
        return f"sha256:{hashlib.sha256(key.encode()).hexdigest()[:16]} len={len(key)}"

    print(f"  DSH     key: {fp(dsh_key)}")
    print(f"  MyAgent key: {fp(ma_key)}")
    if dsh_key and ma_key:
        print(f"  SAME credential: {dsh_key == ma_key}")
    else:
        print("  could not compare (one side missing)")


if __name__ == "__main__":
    main()
