#!/usr/bin/env python3
"""
floatwatch paper check — mark the pre-registered positions to market.

Reports per-hypothesis P&L net of modelled round-trip costs, plus the
benchmark, plus an honest read on whether the result means anything yet.

Usage:  python3 check.py
"""
import json, time, datetime, urllib.request, sys

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}


def fetch(url, tries=5):
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            time.sleep(2 + a * 2)
    return None


# A mark this far from entry is a data fault, not a price move.
ABSURD_MULTIPLE = 50.0


def mark(pos):
    """Current price for one position, orientation-checked.

    priceUsd ALWAYS describes the pair's BASE token. DEX Screener can reorient a
    pair, and when it does, priceUsd silently starts describing the other side.
    Observed 2026-09-08: the UBIK/GLD pool flipped to GLD/UBIK, so UBIK marked
    at $403.60 (the price of tokenized gold) against a $0.02462 entry -- a
    +1,639,217% "gain" and a $32.7m paper P&L on $20k deployed.

    If our token is the quote, its USD price is base_usd / priceNative.
    """
    if pos.get("coingecko_id"):
        return None  # filled in batch below
    d = fetch(f"https://api.dexscreener.com/latest/dex/pairs/robinhood/{pos['pair']}")
    if not d:
        return None
    ps = d.get("pairs") or ([d["pair"]] if d.get("pair") else [])
    if not ps:
        return None
    p = ps[0]
    liq = (p.get("liquidity") or {}).get("usd")
    base, quote = p["baseToken"]["symbol"], p["quoteToken"]["symbol"]
    sym = pos["symbol"]
    px = float(p["priceUsd"]) if p.get("priceUsd") else None
    if px is None:
        return None

    if base == sym:
        pass                                   # priceUsd already describes us
    elif quote == sym:
        native = float(p.get("priceNative") or 0)   # base priced in quote units
        if native <= 0:
            return None
        px = px / native                       # -> quote token in USD
    else:
        return None                            # neither side is us; refuse

    # last-ditch guard: reject a mark that cannot be a real price move
    e = pos.get("entry_price_usd") or 0
    if e > 0 and (px / e > ABSURD_MULTIPLE or e / px > ABSURD_MULTIPLE):
        print(f"  !! {sym}: mark ${px:.8g} vs entry ${e:.8g} exceeds "
              f"{ABSURD_MULTIPLE}x — treating as a data fault, position skipped")
        return None
    return (px, liq)


def main():
    book = json.load(open("positions.json"))
    opened = datetime.datetime.fromisoformat(book["opened_at"])
    now = datetime.datetime.now(datetime.timezone.utc)
    held_h = (now - opened).total_seconds() / 3600.0

    # batch-price the CoinGecko leg
    cg_ids = [p["coingecko_id"] for p in book["positions"] if p.get("coingecko_id")]
    cg = {}
    if cg_ids:
        for c in (fetch("https://api.coingecko.com/api/v3/coins/markets"
                        "?vs_currency=usd&ids=" + ",".join(cg_ids)) or []):
            cg[c["id"]] = c

    rows = []
    for p in book["positions"]:
        if p.get("coingecko_id"):
            c = cg.get(p["coingecko_id"])
            cur, liq = (c["current_price"] if c else None), None
        else:
            m = mark(p)
            time.sleep(0.35)
            cur, liq = m if m else (None, None)
        if not cur:
            continue
        gross = (cur / p["entry_price_usd"] - 1.0) * 100.0
        if p["side"] == "short":
            gross = -gross
        # round trip: entry cost already known, exit cost re-estimated on current liq
        exit_bps = p["entry_cost_bps"] if liq is None else (
            30.0 + p["size_usd"] / (liq / 2.0) * 10_000.0)
        net = gross - (p["entry_cost_bps"] + exit_bps) / 100.0
        rows.append({**p, "cur": cur, "gross_pct": gross, "net_pct": net,
                     "pnl_usd": p["size_usd"] * net / 100.0})

    print(f"floatwatch paper check   opened {book['opened_at'][:19]}Z   "
          f"held {held_h:.1f}h")
    print(f"{'hyp':5}{'bucket':12}{'side':6}{'sym':12}{'entry':>13}{'now':>13}"
          f"{'gross%':>9}{'net%':>9}{'P&L $':>10}")
    print("-" * 99)
    for r in sorted(rows, key=lambda x: (x["hypothesis"], x["bucket"], x["symbol"])):
        print(f"{r['hypothesis']:5}{r['bucket']:12}{r['side']:6}{r['symbol'][:11]:12}"
              f"{r['entry_price_usd']:>13.8g}{r['cur']:>13.8g}"
              f"{r['gross_pct']:>8.1f}%{r['net_pct']:>8.1f}%{r['pnl_usd']:>10,.0f}")

    print()
    for h in ("H1", "H2"):
        sub = [r for r in rows if r["hypothesis"] == h]
        if not sub:
            continue
        pnl = sum(r["pnl_usd"] for r in sub)
        cap = sum(r["size_usd"] for r in sub)
        print(f"{h}  net P&L ${pnl:>9,.0f} on ${cap:,.0f} deployed  "
              f"= {pnl/cap*100:+.2f}%")
        if h == "H2":
            for b in ("HIGH_conc", "LOW_conc"):
                bb = [r for r in sub if r["bucket"] == b]
                if bb:
                    g = sum(r["gross_pct"] for r in bb) / len(bb)
                    print(f"     {b:10} mean gross move (signed by side) {g:+.1f}%")

    # benchmark: unsigned mean move of every H2 name, i.e. just holding the basket
    h2 = [r for r in rows if r["hypothesis"] == "H2"]
    if h2:
        bench = sum((r["gross_pct"] if r["side"] == "long" else -r["gross_pct"])
                    for r in h2) / len(h2)
        print(f"\nbenchmark (equal-weight long all H2 names): {bench:+.1f}%")

    print("\nREAD THIS BEFORE BELIEVING ANY OF IT")
    n = len(h2)
    print(f"  n = {n} names, horizon = {held_h:.1f}h. Memecoin daily vol is ~50-150%.")
    print("  A result under roughly +/-30% here is indistinguishable from noise.")
    print("  This test can DISCONFIRM a strong effect. It cannot confirm a weak one.")
    print("  Costs are modelled but fills are not: a real short leg needs a borrow")
    print("  that mostly does not exist for these tokens.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
