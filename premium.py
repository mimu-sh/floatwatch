#!/usr/bin/env python3
"""
floatwatch premium — tokenized stock price vs the REAL share price.

THE MECHANISM (discovered 2026-09-07, pre-market)
  A memecoin quoted in a stock token forces its buyers to acquire that stock
  token first. That demand is price-insensitive (they want the memecoin, not
  the equity), so the stock TOKEN trades above the real share. Measured at
  08:40 ET Monday, after a full weekend of closed US markets, EVERY tokenized
  stock sat at a premium, and the premium tracked memecoin heat:

      IBM  +5.17%   (QC memecoin +581%/24h)   <- hottest meme, fattest premium
      MSTR +2.39%
      MU   +2.33%
      HIMS +1.95%
      NVDA +0.79%   (deepest pool, tightest)

  This also explains the HIMS float doubling (58,714 -> 130,876 shares): the
  issuer mints new tokens and sells them into the premium. Minting is the
  arbitrage, and it is what collapses the premium.

WHY THIS MATTERS MORE THAN THE CONCENTRATION SIGNAL
  Concentration was a LAGGING restatement of memecoin buy flow. The premium is
  a live dislocation against an external, independent reference price. It is
  the first thing measured here that is not circular.

THE TWO HYPOTHESES (opposite; the Monday open decides)
  H3a INFORMATIVE — the token is forward-pricing news and the REAL stock gaps
      up toward it at the open. Then the premium is a free forecast of the open
      and is tradeable in an ordinary brokerage account.
  H3b MANIA — the premium is memecoin demand, not information, and it COLLAPSES
      at the open as arbitrage returns. Then the premium is a risk warning:
      a memecoin quoted in a premium token carries hidden downside equal to
      that premium.

  Prior favours H3b: closed-end fund and ADR premiums mean-revert, and the
  observed HIMS minting is a live premium-collapse mechanism. But it is a
  prior, not a result.

Usage:
  python3 premium.py --record       # snapshot premiums (run pre-open)
  python3 premium.py --compare      # re-measure and score H3a vs H3b
"""
import json, time, datetime, urllib.request, argparse, sys, glob

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}

# Real Friday-close references, captured 2026-09-07 pre-open (stockanalysis.com).
# Stored rather than re-fetched so the comparison uses a fixed baseline.
REAL_CLOSE = {
    "IBM":  {"close": 234.89, "after": 234.30},
    "HIMS": {"close": 27.71,  "after": 27.82},
    "MU":   {"close": 1016.59, "after": 1014.95},
    "MSTR": {"close": 142.80, "after": 142.58},
    "NVDA": {"close": 230.36, "after": 229.47},
}


def fetch(url, tries=4):
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=25))
        except Exception:
            time.sleep(2 + a)
    return {}


def token_price(sym):
    """Deepest LIVE stock/USDG pool = the token's reference USD price."""
    d = fetch(f"https://api.dexscreener.com/latest/dex/search?q={sym}%20USDG")
    best = None
    for p in (d.get("pairs") or []):
        if p.get("chainId") != "robinhood":
            continue
        if p["baseToken"]["symbol"] != sym or p["quoteToken"]["symbol"] != "USDG":
            continue
        liq = (p.get("liquidity") or {}).get("usd", 0)
        t = (p.get("txns") or {}).get("h24", {}) or {}
        if liq < 20_000 or (t.get("buys", 0) + t.get("sells", 0)) < 50:
            continue
        if not best or liq > best[1]:
            best = (float(p["priceUsd"]), liq,
                    (p.get("priceChange") or {}).get("h24"))
    return best


def measure():
    out = {}
    for sym, ref in REAL_CLOSE.items():
        tp = token_price(sym)
        time.sleep(0.5)
        if not tp:
            continue
        px, liq, chg = tp
        out[sym] = {"token_px": px, "token_liq": liq, "token_chg24": chg,
                    "real_close": ref["close"], "real_after": ref["after"],
                    "premium_pct": (px / ref["close"] - 1) * 100}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    cur = measure()

    print(f"floatwatch premium  {now.isoformat()[:19]}Z\n")
    print(f"{'stock':7}{'token $':>11}{'real close $':>14}{'premium':>10}{'tok 24h%':>11}{'pool liq $':>13}")
    print("-" * 68)
    for s, v in sorted(cur.items(), key=lambda kv: -kv[1]["premium_pct"]):
        print(f"{s:7}{v['token_px']:>11.2f}{v['real_close']:>14.2f}"
              f"{v['premium_pct']:>+9.2f}%{str(v['token_chg24']):>11}{v['token_liq']:>13,.0f}")
    print(f"\nmean premium {sum(v['premium_pct'] for v in cur.values())/len(cur):+.2f}%")

    if a.record:
        p = f"premiums/{now:%Y-%m-%dT%H%M}.json"
        json.dump({"captured_at": now.isoformat(), "premiums": cur},
                  open(p, "w"), indent=1)
        print(f"\nrecorded -> {p}")

    if a.compare:
        snaps = sorted(glob.glob("premiums/*.json"))
        if not snaps:
            print("\nno prior recording to compare against")
            return 1
        base = json.load(open(snaps[0]))
        print(f"\nvs baseline {base['captured_at'][:19]}Z")
        print(f"{'stock':7}{'prem then':>12}{'prem now':>11}{'change':>10}  reading")
        print("-" * 62)
        for s, v in cur.items():
            b = base["premiums"].get(s)
            if not b:
                continue
            d = v["premium_pct"] - b["premium_pct"]
            # premium shrinking = H3b (mania collapsing); token holding = H3a
            read = "H3b premium collapsing" if d < -0.5 else (
                   "H3a premium held//grew" if d > 0.5 else "flat, undecided")
            print(f"{s:7}{b['premium_pct']:>+11.2f}%{v['premium_pct']:>+10.2f}%"
                  f"{d:>+9.2f}%  {read}")
        print("\nNOTE: the real-stock leg is a STORED Friday close. After the open")
        print("it is stale — re-fetch live quotes before drawing any conclusion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
