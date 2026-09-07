#!/usr/bin/env python3
"""
floatwatch report — validate a raw snapshot and emit the clean concentration table.

Kept separate from collect.py on purpose: snapshots stay raw and immutable
(they are the unreconstructable asset), validation rules evolve and get
re-applied to history.

WHY VALIDATION IS THE ACTUAL PRODUCT
  DEX Screener's raw liquidity figures are not usable as-is. Observed in the
  first snapshot: an AMD/AD pool reporting $1.16bn of liquidity while holding
  ZERO units and doing $8 of daily volume — an implied $1.5 trillion per share.
  Anyone plotting raw DEX Screener numbers publishes that as fact. The filters
  below are what separate a real dataset from a plausible-looking wrong one.

REJECT RULES
  1. implied share price outside $0.50-$5,000     -> mispriced/dead pool
  2. zero units held                              -> empty pool, phantom TVL
  3. 24h volume < $100 AND liquidity > $1m        -> stale price, no real market
  4. pooled units > 100% of float                 -> indexer/float mismatch
"""
import json, sys, glob, argparse

PRICE_MIN, PRICE_MAX = 0.50, 5_000.0


def validate(r):
    """Return (ok, reason)."""
    u, liq, vol = r["stock_units_in_pool"], r["liq_usd"], r["vol24_usd"]
    if not u or u <= 0:
        return False, "zero units held"
    implied = liq / (2 * u)                       # half the pool is the stock side
    if not (PRICE_MIN <= implied <= PRICE_MAX):
        return False, f"implied ${implied:,.0f}/share out of range"
    if vol < 100 and liq > 1_000_000:
        return False, "stale: >$1m liq, <$100 volume"
    if r["pct_of_float"] > 100:
        return False, "pooled units exceed float"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--show-rejects", action="store_true")
    a = ap.parse_args()

    path = a.snapshot or sorted(glob.glob("snapshots/*.json"))[-1]
    d = json.load(open(path))
    pools = d["pools"]

    clean, rejects = [], []
    for r in pools:
        ok, why = validate(r)
        (clean if ok else rejects).append((r, why))
    clean = [r for r, _ in clean]

    # Re-aggregate per stock from validated pools only.
    # Key on ADDRESS, never symbol: this niche is full of memecoins that named
    # themselves after the ticker they quote against, so grouping by symbol
    # silently merges a memecoin's reserves into the real stock token's and
    # produces impossible readings (observed: HOOD at 4873% of float).
    per = {}
    for r in clean:
        s = per.setdefault(r["stock_addr"], {
            "symbol": r["stock"],
            "float": r["stock_float"], "units": 0.0, "meme_units": 0.0,
            "liq": 0.0, "vol": 0.0, "pools": 0, "top": None, "top_pct": 0.0})
        s["units"] += r["stock_units_in_pool"]
        s["liq"] += r["liq_usd"]; s["vol"] += r["vol24_usd"]; s["pools"] += 1
        if r["counterparty_meme"]:
            s["meme_units"] += r["stock_units_in_pool"]
            if r["pct_of_float"] > s["top_pct"]:
                s["top_pct"], s["top"] = r["pct_of_float"], r["counterparty"]

    rows = []
    for addr, s in per.items():
        if not s["float"]:
            continue
        # A stock token's pooled units can never exceed its float. If they do,
        # the indexer has mixed two tokens and the row is not trustworthy.
        if s["units"] > s["float"] * 1.05:
            continue
        rows.append((s["meme_units"] / s["float"] * 100, s["symbol"], s))
    rows.sort(reverse=True)

    print(f"floatwatch — {d['captured_at'][:19]}Z   chain={d.get('chain')}")
    print(f"pools: {len(pools)} raw -> {len(clean)} validated ({len(rejects)} rejected)\n")
    print(f"{'stock':8}{'float (sh)':>12}{'% in pools':>12}{'% in MEME':>11}"
          f"{'top memecoin':>14}{'top %':>8}{'liquidity $':>14}{'24h vol $':>13}")
    print("-" * 92)
    for pct, sym, s in rows:
        if pct < 0.5:
            continue
        print(f"{sym[:7]:8}{s['float']:>12,.0f}"
              f"{s['units']/s['float']*100:>11.1f}%{pct:>10.1f}%"
              f"{str(s['top'] or '-'):>14}{s['top_pct']:>7.1f}%"
              f"${s['liq']:>13,.0f}${s['vol']:>12,.0f}")

    meme = [r for r in clean if r["counterparty_meme"]]
    print(f"\nVALIDATED TOTALS")
    print(f"  memecoin-paired pools     {len(meme)}")
    print(f"  liquidity                 ${sum(r['liq_usd'] for r in meme):,.0f}")
    print(f"  24h volume                ${sum(r['vol24_usd'] for r in meme):,.0f}")
    print(f"  stocks >10% float in meme pools  "
          f"{sum(1 for p, _, _ in rows if p > 10)}")
    print(f"  stocks >25% float in meme pools  "
          f"{sum(1 for p, _, _ in rows if p > 25)}")

    if a.show_rejects:
        print(f"\nREJECTED ({len(rejects)})")
        for r, why in sorted(rejects, key=lambda x: -x[0]["liq_usd"])[:15]:
            print(f"  {r['stock']:7}/{r['counterparty']:<12} ${r['liq_usd']:>14,.0f}  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
