#!/usr/bin/env python3
"""
floatwatch diff — change in float concentration between two snapshots.

This is the part that needed history, and it is the reason the series is worth
logging. A single snapshot says "BONER holds 32.8% of tokenized HIMS". Only a
diff says whether that is RISING (the pool is absorbing float — squeeze) or
FALLING (the issuer is minting into demand — supply expansion).

Today's motivating case: The Defiant reported BONER at 53.1% of the HIMS float.
It now reads 32.7% — not because the pool shrank, but because the float more
than doubled underneath it. Only a diff can tell those two apart, and no
amount of cleverness recovers it after the fact.

Usage:  python3 diff.py [old.json] [new.json]      # defaults to last two
"""
import json, glob, sys, argparse, datetime

ALERT_PP = 2.0        # percentage-point move worth flagging
CROSS_LEVELS = [10.0, 25.0, 50.0]
DEADBAND_PP = 0.5     # a crossing must finish this far past the level to alert


def load(path):
    d = json.load(open(path))
    per = {}
    for r in d["pools"]:
        if not r["counterparty_meme"] or not r["stock_float"]:
            continue
        u = r["stock_units_in_pool"]
        if not u or not (0.5 <= r["liq_usd"] / (2 * u) <= 5000) or r["pct_of_float"] > 100:
            continue
        s = per.setdefault(r["stock_addr"], {
            "symbol": r["stock"], "float": r["stock_float"],
            "meme_units": 0.0, "liq": 0.0, "pairs": set()})
        s["meme_units"] += u
        s["liq"] += r["liq_usd"]
        s["pairs"].add(r["pair"])
    for s in per.values():
        s["pct"] = s["meme_units"] / s["float"] * 100
    return d["captured_at"], per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old", nargs="?")
    ap.add_argument("new", nargs="?")
    a = ap.parse_args()

    snaps = sorted(glob.glob("snapshots/*.json"))
    if len(snaps) < 2:
        print("need at least 2 snapshots; only", len(snaps), "present")
        return 1
    op, np_ = (a.old or snaps[-2]), (a.new or snaps[-1])
    t0, A = load(op)
    t1, B = load(np_)

    dt = (datetime.datetime.fromisoformat(t1) - datetime.datetime.fromisoformat(t0))
    hrs = dt.total_seconds() / 3600.0
    print(f"floatwatch diff   {t0[:19]}Z -> {t1[:19]}Z   ({hrs:.2f}h)\n")

    rows = []
    for addr, b in B.items():
        aa = A.get(addr)
        if not aa:
            rows.append((999, b["symbol"], None, b["pct"], None, b, "NEW"))
            continue
        d_pct = b["pct"] - aa["pct"]
        d_float = (b["float"] / aa["float"] - 1) * 100 if aa["float"] else 0
        d_units = (b["meme_units"] / aa["meme_units"] - 1) * 100 if aa["meme_units"] else 0
        # Pool-set stability is what separates a real move from a discovery
        # artifact. The AAPL "-90%" phantom was caused entirely by a live pool
        # dropping out of enumeration; the real IBM +7.3pp move had an
        # identical pool set on both sides. Never alert without this.
        gone, new_p = aa["pairs"] - b["pairs"], b["pairs"] - aa["pairs"]
        if gone or new_p:
            stab = f"  [UNVERIFIED: {len(gone)} pool(s) left, {len(new_p)} joined set]"
        else:
            stab = "  [pool set stable]"
        rows.append((abs(d_pct), b["symbol"], aa["pct"], b["pct"], d_pct, b,
                     f"float {d_float:+.1f}%  pooled {d_units:+.1f}%{stab}"))
    rows.sort(reverse=True, key=lambda r: r[0])

    print(f"{'stock':8}{'was %':>9}{'now %':>9}{'delta pp':>11}  what moved")
    print("-" * 74)
    shown = 0
    for mag, sym, was, now, d, b, note in rows:
        if was is None:
            print(f"{sym[:7]:8}{'-':>9}{now:>8.1f}%{'NEW':>11}  {note}")
            shown += 1
            continue
        if abs(d) < 0.05:
            continue
        flag = "  <<< ALERT" if abs(d) >= ALERT_PP else ""
        print(f"{sym[:7]:8}{was:>8.1f}%{now:>8.1f}%{d:>+10.2f}pp  {note}{flag}")
        shown += 1
    if not shown:
        print("  (no measurable change)")

    # threshold crossings — the alertable event the paid tier would sell.
    # DEADBAND: a bare crossing test fires every time a value oscillates around
    # a level. Observed 2026-09-07: HOODon 10.1% -> 9.8% tripped the 10% alert
    # on a 0.3pp move, and would trip again on any wobble back. A paid alert
    # that cries wolf on noise is worse than no alert, so require the value to
    # finish at least DEADBAND_PP clear of the level.
    print("\nTHRESHOLD CROSSINGS")
    hits = 0
    for mag, sym, was, now, d, b, note in rows:
        if was is None:
            continue
        for lvl in CROSS_LEVELS:
            if was < lvl <= now and (now - lvl) >= DEADBAND_PP:
                print(f"  {sym} crossed UP through {lvl:.0f}% of float "
                      f"({was:.1f}% -> {now:.1f}%)")
                hits += 1
            elif now < lvl <= was and (lvl - now) >= DEADBAND_PP:
                print(f"  {sym} crossed DOWN through {lvl:.0f}% of float "
                      f"({was:.1f}% -> {now:.1f}%)")
                hits += 1
            elif (was < lvl <= now) or (now < lvl <= was):
                print(f"  ({sym} grazed {lvl:.0f}% — {was:.1f}% -> {now:.1f}%, "
                      f"inside {DEADBAND_PP}pp deadband, not alerted)")
    if not hits:
        print("  none")

    print("\nINTERPRETATION KEY")
    print("  pct up   + float flat   -> pool absorbing float (squeeze-ish)")
    print("  pct down + float up     -> issuer minting into demand (supply expansion)")
    print("  pct down + pooled down  -> liquidity leaving; exit is getting thinner")
    return 0


if __name__ == "__main__":
    sys.exit(main())
