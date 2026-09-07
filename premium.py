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

RESOLVED 2026-09-07: the premium does NOT converge at the open.
  Measured against the same-stock twin across the 09:30 ET Monday open:
      12:30 UTC (60m pre)  +5.10%
      13:00 UTC (30m pre)  +2.75%
      13:32 UTC (open)     +2.55%
      13:38 UTC (T+8m)     +2.50%
  The compression happened entirely BEFORE the open; 0.20pp across the bell
  itself. H3a and H3b below are both unsupported for this session -- the
  premium is a persistent level, consistent with the backtest. One session.

THE TWO HYPOTHESES (framed pre-open, kept for the record)
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


def twin_premiums():
    """RH token vs the SAME stock tokenized by another issuer.

    This is the measure that survives. REAL_CLOSE below is a hardcoded Friday
    close: it is stale the moment the equity market reopens, and outright wrong
    on any later date. The twin needs no equity data at all -- both legs are
    24/7 crypto tokens -- so it is the only one of the two safe to accumulate
    into a multi-session series.

    Verified 2026-09-07 across the cash open: measured against the stored close
    IBM read +5.43%, against its twin +2.55%, at the same instant.
    """
    try:
        ids = json.load(open("cg_ids.json"))
    except Exception:
        return {}
    every = [v["rh"] for v in ids.values()] + [v["ctrl"] for v in ids.values()]
    d = fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids="
              + ",".join(every))
    if not d:
        return {}
    px = {c["id"]: c["current_price"] for c in d}
    out = {}
    for sym, leg in ids.items():
        a, b = px.get(leg["rh"]), px.get(leg["ctrl"])
        if a and b:
            out[sym] = {"rh_px": a, "twin_px": b, "twin_premium_pct": (a / b - 1) * 100}
    return out


def measure():
    out = {}
    twins = twin_premiums()
    for sym, ref in REAL_CLOSE.items():
        tp = token_price(sym)
        time.sleep(0.5)
        if not tp:
            continue
        px, liq, chg = tp
        out[sym] = {"token_px": px, "token_liq": liq, "token_chg24": chg,
                    "real_close": ref["close"], "real_after": ref["after"],
                    # NOTE: stale after the reopen; prefer twin_premium_pct
                    "premium_pct": (px / ref["close"] - 1) * 100}
    # twins cover more symbols than REAL_CLOSE, so merge rather than intersect
    for sym, t in twins.items():
        out.setdefault(sym, {}).update(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    cur = measure()

    print(f"floatwatch premium  {now.isoformat()[:19]}Z\n")
    print(f"{'stock':7}{'vs twin':>10}{'vs close':>11}{'token $':>11}{'pool liq $':>13}")
    print("-" * 56)
    # sort on the twin measure; it is the one that stays valid
    for s, v in sorted(cur.items(), key=lambda kv: -(kv[1].get("twin_premium_pct") or -99)):
        twin = f"{v['twin_premium_pct']:+.2f}%" if "twin_premium_pct" in v else "-"
        close = f"{v['premium_pct']:+.2f}%" if "premium_pct" in v else "-"
        tpx = f"{v['token_px']:.2f}" if "token_px" in v else f"{v.get('rh_px', 0):.2f}"
        liq = f"{v['token_liq']:,.0f}" if "token_liq" in v else "-"
        print(f"{s:7}{twin:>10}{close:>11}{tpx:>11}{liq:>13}")
    tw = [v["twin_premium_pct"] for v in cur.values() if "twin_premium_pct" in v]
    if tw:
        print(f"\nmean twin premium {sum(tw)/len(tw):+.2f}%   "
              f"(vs-close column goes stale after the reopen)")

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
            k = "twin_premium_pct" if ("twin_premium_pct" in v and
                                       "twin_premium_pct" in b) else "premium_pct"
            if k not in v or k not in b:
                continue
            d = v[k] - b[k]
            # premium shrinking = H3b (mania collapsing); token holding = H3a
            read = "H3b premium collapsing" if d < -0.5 else (
                   "H3a premium held//grew" if d > 0.5 else "flat, undecided")
            print(f"{s:7}{b[k]:>+11.2f}%{v[k]:>+10.2f}%"
                  f"{d:>+9.2f}%  {read}")
        print("\nNOTE: the real-stock leg is a STORED Friday close. After the open")
        print("it is stale — re-fetch live quotes before drawing any conclusion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
