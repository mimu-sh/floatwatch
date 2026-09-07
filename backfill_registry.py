#!/usr/bin/env python3
"""Seed registry.json from every historical snapshot.

Pools discovered before the registry existed are otherwise lost to it, which
reintroduces exactly the phantom-drop alerts the registry was added to prevent.
Safe to re-run; it only ever adds.
"""
import json, glob
reg = json.load(open("registry.json"))
added_p = added_e = 0
for f in sorted(glob.glob("snapshots/*.json")):
    d = json.load(open(f))
    for r in d["pools"]:
        a = r["stock_addr"]
        if a not in reg["equities"]:
            reg["equities"][a] = {"symbol": r["stock"], "decimals": 18}
            added_e += 1
        pairs = set(reg["pairs"].get(a, []))
        if r["pair"] not in pairs:
            pairs.add(r["pair"]); added_p += 1
        reg["pairs"][a] = sorted(pairs)
json.dump(reg, open("registry.json", "w"), indent=1)
print(f"backfilled +{added_e} equities, +{added_p} pairs")
print(f"registry now: {len(reg['equities'])} equities, "
      f"{sum(len(v) for v in reg['pairs'].values())} pairs")
