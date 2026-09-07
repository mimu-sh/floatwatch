#!/usr/bin/env python3
"""
floatwatch paper simulation — PRE-REGISTERED signal test. Zero capital at risk.

WHAT THIS IS TESTING
  floatwatch measures what % of a tokenized stock's float sits in a memecoin's
  liquidity pool. That was built as a RISK metric (how trapped is your exit).
  Whether it also predicts RETURN is an open question, and the direction is
  genuinely ambiguous ex ante:

    bear case  high concentration = the pool IS the market. No outside bid,
               exit liquidity is structurally trapped -> underperforms.
    bull case  high concentration = the memecoin has cornered the float,
               supply squeeze -> outperforms.

  Both are plausible. That is exactly why it is worth pre-registering rather
  than deciding after the fact.

HYPOTHESES (fixed at t0, not revisable afterwards)
  H1  RECAP FADE. Tokens named in a daily memecoin recap underperform over the
      following days. Prior: 6/6 were below their printed number at ~24h,
      median -26%.
  H2  CONCENTRATION. Long the LOW-concentration bucket, short the HIGH one,
      dollar-neutral. Positive H2 return = the bear case is right.

COSTS ARE MODELLED, NOT IGNORED
  These pools are thin. Round-trip cost is charged per position as
  30bps swap fee + price impact estimated as size / (pool_liquidity / 2),
  applied on BOTH entry and exit. A paper test that ignores slippage in
  $300k pools is worthless.

Usage:  python3 simulate.py            # opens positions, writes positions.json
"""
import json, time, datetime, urllib.request, sys, glob

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}

NOTIONAL_PER_LEG = 10_000.0     # USD per bucket, equal-weighted within it
MIN_LIQ = 250_000.0             # below this a paper fill is fiction
BUCKET_N = 5

# H1 basket: the Sept-6 mellometrics recap names, by CoinGecko id
RECAP = ["stonk-3", "anonymous-cat", "a-meme-coin", "boner-coin", "ubik", "otc"]


def fetch(url, tries=5):
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            time.sleep(2 + a * 2)
    return None


def cost_bps(size_usd, liq_usd):
    """30bps fee + constant-product price impact against half the pool."""
    if not liq_usd:
        return 10_000.0
    impact = size_usd / (liq_usd / 2.0) * 10_000.0
    return 30.0 + impact


def load_candidates():
    """Memecoins from the latest snapshot, keyed by their deepest stock pool."""
    snap = json.load(open(sorted(glob.glob("snapshots/*.json"))[-1]))
    best = {}
    for r in snap["pools"]:
        if not r["counterparty_meme"]:
            continue
        if r["liq_usd"] < MIN_LIQ:
            continue
        # sanity: reuse the report.py validation floor
        u = r["stock_units_in_pool"]
        if not u or not (0.5 <= r["liq_usd"] / (2 * u) <= 5000):
            continue
        if r["pct_of_float"] > 100:
            continue
        m = r["counterparty"]
        if m not in best or r["liq_usd"] > best[m]["liq_usd"]:
            best[m] = r
    return snap["captured_at"], best


def price_pair(pair_id):
    d = fetch(f"https://api.dexscreener.com/latest/dex/pairs/robinhood/{pair_id}")
    if not d:
        return None
    ps = d.get("pairs") or ([d["pair"]] if d.get("pair") else [])
    return ps[0] if ps else None


def main():
    captured, best = load_candidates()
    ranked = sorted(best.items(), key=lambda kv: -kv[1]["pct_of_float"])
    print(f"{len(ranked)} memecoins with a stock pool >${MIN_LIQ:,.0f}\n")

    high = ranked[:BUCKET_N]
    low = ranked[-BUCKET_N:]

    positions, now = [], datetime.datetime.now(datetime.timezone.utc)
    for bucket, side, items in (("HIGH_conc", "short", high),
                                ("LOW_conc", "long", low)):
        size = NOTIONAL_PER_LEG / len(items)
        for meme, r in items:
            p = price_pair(r["pair"])
            time.sleep(0.4)
            if not p or not p.get("priceUsd"):
                print(f"  !! no price for {meme}, skipped")
                continue
            liq = (p.get("liquidity") or {}).get("usd", r["liq_usd"])
            positions.append({
                "hypothesis": "H2", "bucket": bucket, "side": side,
                "symbol": meme, "pair": r["pair"], "stock": r["stock"],
                "pct_of_float_t0": r["pct_of_float"],
                "entry_price_usd": float(p["priceUsd"]),
                "entry_liq_usd": liq, "size_usd": size,
                "entry_cost_bps": cost_bps(size, liq),
            })
            print(f"  {bucket:10} {side:5} {meme:12} ${float(p['priceUsd']):<12.8g} "
                  f"float% {r['pct_of_float']:>5.1f}  liq ${liq:>11,.0f}  "
                  f"cost {cost_bps(size, liq):.0f}bps")

    # H1 — recap fade, priced off CoinGecko (these span chains)
    cg = fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids="
               + ",".join(RECAP) + "&price_change_percentage=24h") or []
    size = NOTIONAL_PER_LEG / max(len(cg), 1)
    for c in cg:
        positions.append({
            "hypothesis": "H1", "bucket": "RECAP_named", "side": "short",
            "symbol": c["symbol"].upper(), "coingecko_id": c["id"],
            "entry_price_usd": c["current_price"],
            "entry_mcap_usd": c["market_cap"], "size_usd": size,
            "entry_cost_bps": 60.0,   # CEX/aggregator round trip, flat estimate
        })
        print(f"  RECAP      short {c['symbol'].upper():12} ${c['current_price']:<12.8g} "
              f"mcap ${c['market_cap']:>13,.0f}")

    out = {
        "opened_at": now.isoformat(),
        "snapshot_used": captured,
        "notional_per_leg_usd": NOTIONAL_PER_LEG,
        "hypotheses": {
            "H1": "Recap-named tokens underperform over the following days (short).",
            "H2": "Long LOW float-concentration, short HIGH. Positive = pool-is-the-market "
                  "bear case correct; negative = supply-squeeze bull case correct.",
        },
        "benchmark": "equal-weight all candidate memecoins, same entry timestamps",
        "positions": positions,
    }
    json.dump(out, open("positions.json", "w"), indent=1)
    print(f"\nopened {len(positions)} paper positions -> positions.json")
    print(f"opened_at {now.isoformat()}")
    print("\nNOTE: n is tiny and the horizon is days. This can DISCONFIRM a")
    print("strong effect; it cannot confirm a weak one. See check.py output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
