#!/usr/bin/env python3
"""
Backtest: does the Robinhood-Chain tokenized-stock PREMIUM mean-revert?

THE SETUP
  The same underlying equity is tokenized by several issuers. Only Robinhood's
  version is used as the quote asset in memecoin pools, so only Robinhood's
  version carries memecoin-driven demand. An xStock/Ondo token of the same
  stock is therefore a near-perfect CONTROL: same equity, same 24/7 settlement,
  no memecoin bid.

      premium_t = RH_price_t / control_price_t - 1

  This removes the need for real-stock market data entirely, and it removes the
  market-hours problem: both legs are crypto tokens trading 24/7.

WHAT IS BEING TESTED
  H3b (mania)       high premium -> RH token UNDERPERFORMS control next days.
                    Premium mean-reverts. Actionable as a risk filter.
  H3a (informative) premium persists or predicts control catching UP.
                    Premium is a forecast, tradeable in a brokerage account.

  Null: premium is noise and predicts nothing.

HONEST LIMITS (read before acting)
  * Daily closes only, and CoinGecko daily points are UTC-midnight snapshots —
    not aligned to the US cash open, which is where convergence should happen.
  * Robinhood Chain launched 2026-07-01 and these tokens listed later, so the
    sample is short. Overlapping forward windows make observations
    non-independent; treat any t-stat as indicative, never as proof.
  * Survivorship: only tokens CoinGecko lists today are included.

Usage:  python3 backtest_premium.py
"""
import json, time, urllib.request, datetime, statistics as st, sys

UA = {"User-Agent": "Mozilla/5.0"}


def get(u, tries=10):
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=30))
        except Exception:
            time.sleep(12)
    return None


def series(cid, days=90):
    d = get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
            f"?vs_currency=usd&days={days}&interval=daily")
    if not d or "prices" not in d:
        return {}
    out = {}
    for ts, px in d["prices"]:
        day = datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")
        out[day] = px          # last write wins = latest point that day
    return out


def main():
    ids = json.load(open("cg_ids.json"))
    rows = []
    for sym, leg in ids.items():
        rh, ct = series(leg["rh"]), series(leg["ctrl"])
        time.sleep(6)
        common = sorted(set(rh) & set(ct))
        if len(common) < 8:
            print(f"  {sym}: only {len(common)} overlapping days, skipped", file=sys.stderr)
            continue
        print(f"  {sym}: {len(common)} overlapping days "
              f"({common[0]} -> {common[-1]})", file=sys.stderr)
        for i, day in enumerate(common):
            rows.append({"sym": sym, "day": day, "i": i,
                         "rh": rh[day], "ct": ct[day],
                         "prem": (rh[day] / ct[day] - 1) * 100})
    if not rows:
        print("no data"); return 1

    # index by (sym, i) for forward lookups
    by = {(r["sym"], r["i"]): r for r in rows}
    obs = []
    for r in rows:
        nxt = by.get((r["sym"], r["i"] + 1))
        n3 = by.get((r["sym"], r["i"] + 3))
        if not nxt:
            continue
        rh_ret = (nxt["rh"] / r["rh"] - 1) * 100
        ct_ret = (nxt["ct"] / r["ct"] - 1) * 100
        o = {"sym": r["sym"], "day": r["day"], "prem": r["prem"],
             "rel_1d": rh_ret - ct_ret,                  # RH minus control
             "d_prem_1d": nxt["prem"] - r["prem"]}
        if n3:
            o["rel_3d"] = ((n3["rh"] / r["rh"] - 1) - (n3["ct"] / r["ct"] - 1)) * 100
        obs.append(o)

    print(f"\n=== {len(obs)} observations across {len(set(o['sym'] for o in obs))} stocks ===")
    prem = [o["prem"] for o in obs]
    print(f"premium: mean {st.mean(prem):+.2f}%  median {st.median(prem):+.2f}%  "
          f"min {min(prem):+.2f}%  max {max(prem):+.2f}%")

    # --- mean reversion of the premium itself ---
    xs = [o["prem"] for o in obs]; ys = [o["d_prem_1d"] for o in obs]
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / len(xs)
    vx = sum((a - mx) ** 2 for a in xs) / len(xs)
    beta = cov / vx if vx else 0
    sx, sy = st.pstdev(xs), st.pstdev(ys)
    corr = cov / (sx * sy) if sx and sy else 0
    print(f"\nMEAN REVERSION  d(premium) = a + b*premium")
    print(f"  b = {beta:+.3f}   corr = {corr:+.3f}")
    print(f"  b<0 means premium decays toward its mean (H3b). b~0 means it persists.")
    if beta < 0:
        print(f"  -> premium decays ~{abs(beta)*100:.0f}% of its level per day; "
              f"half-life {(0.693/abs(beta)):.1f} days" if abs(beta) > 0.01 else "")

    # --- does premium predict RH underperformance? ---
    for horizon, key in (("1d", "rel_1d"), ("3d", "rel_3d")):
        sub = [o for o in obs if key in o]
        if len(sub) < 10:
            continue
        srt = sorted(sub, key=lambda o: o["prem"])
        n = len(srt) // 3
        lo, hi = srt[:n], srt[-n:]
        print(f"\nFORWARD {horizon} RELATIVE RETURN (RH minus control), by premium tercile")
        print(f"  LOW  premium (mean {st.mean([o['prem'] for o in lo]):+.2f}%): "
              f"{st.mean([o[key] for o in lo]):+.2f}%")
        print(f"  HIGH premium (mean {st.mean([o['prem'] for o in hi]):+.2f}%): "
              f"{st.mean([o[key] for o in hi]):+.2f}%")
        spread = st.mean([o[key] for o in lo]) - st.mean([o[key] for o in hi])
        print(f"  LOW minus HIGH spread: {spread:+.2f}%  "
              f"({'supports H3b' if spread > 0 else 'contradicts H3b'})")
        pooled = st.pstdev([o[key] for o in sub])
        if pooled:
            print(f"  (pooled sd {pooled:.2f}%, so spread is {spread/pooled:.2f} sd — "
                  f"{'noise' if abs(spread/pooled) < 0.5 else 'notable'})")

    json.dump(obs, open("backtest_obs.json", "w"), indent=1)
    print(f"\nwrote backtest_obs.json ({len(obs)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
