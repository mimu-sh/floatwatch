#!/usr/bin/env python3
"""
floatwatch collector — daily snapshot of tokenized-equity float locked in
memecoin liquidity pools on Robinhood Chain.

THE METRIC NOBODY PUBLISHES
  What fraction of a tokenized stock's entire on-chain float is sitting inside
  a memecoin liquidity pool. DEX Screener shows USD liquidity; it does not
  divide by the stock's float, so it cannot tell you that one memecoin pool
  holds a third of every tokenized HIMS share in existence.

WHY IT IS DEFENSIBLE
  The series cannot be backfilled. Nobody can reconstruct today's concentration
  tomorrow. Whoever starts logging first owns the only history that exists.

METHOD
  1. Seed: ticker-term search on DEX Screener surfaces candidate tokens.
  2. Classify: a tokenized equity has a SMALL float (thousands of shares).
     A memecoin named after a ticker has ~1e9 supply. This is the discriminator
     that separates real stock tokens from memecoins cosplaying as tickers
     (the data is full of them: a memecoin literally named SPY quotes against
     tokenized NVDA).
  3. Enumerate: for each confirmed stock token, pull EVERY pool via
     /token-pairs/v1, handling the token appearing as base OR quote.
  4. Divide: pooled units / totalSupply.

DATA SOURCES (both free, no key)
  numerator   DEX Screener  liquidity.base / liquidity.quote
  denominator public RPC    ERC-20 totalSupply()

GOTCHAS ENCODED HERE (each cost a debugging cycle)
  * Robinhood Chain runs Uniswap v4: pool IDs are 32 bytes, not addresses.
    balanceOf(pairAddress) is meaningless — tokens sit in the singleton
    PoolManager. The reserves must come from the indexer, not the chain.
  * The public RPC returns 403 on JSON-RPC *batch* requests. Single calls only,
    modest concurrency.
  * Blockscout for this chain sits behind Cloudflare; scripted access fails.

Usage:  python3 collect.py [--out snapshots] [--min-liq 25000]
"""
import json, time, argparse, datetime, urllib.request, sys
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
RPC = "https://rpc.mainnet.chain.robinhood.com"
CHAIN = "robinhood"

NON_EQUITY = {"WETH", "ETH", "USDG", "USDC", "USDT", "DAI", "USD1", "FDUSD"}

# A tokenized equity's float is thousands of shares. A memecoin is ~1e9 units.
EQUITY_MAX_FLOAT = 50_000_000

TERMS = ["BONER", "AMC", "UBIK", "MEME", "WSB", "GME", "HOOD", "SPY", "NVDA",
         "TSLA", "HIMS", "MSTR", "PLTR", "COIN", "QQQ", "PFE", "COST", "MU",
         "AAPL", "SHROOM", "STONK", "ZCAT", "GOOGL", "META", "AMZN", "MSFT",
         "GLD", "IWM", "ARKK", "AI", "MRNA", "SCHIFFY", "MONITOR", "IONQ",
         "RGTI", "SMCI", "AVGO", "AMD", "INTC", "BABA", "NFLX"]


def fetch(url, tries=5):
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            time.sleep(2 + a * 2)
    return None


def eth_call(to, data, tries=8):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    h = dict(UA); h["content-type"] = "application/json"
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(RPC, data=body, headers=h), timeout=30)).get("result")
        except Exception:
            time.sleep(2 + a * 2)
    return None


def to_int(h):
    return int(h, 16) if h and h not in ("0x", None) else 0


def seed_tokens():
    """Ticker-term sweep -> every token address seen on this chain."""
    toks, seen_pairs = {}, {}
    for q in TERMS:
        d = fetch(f"https://api.dexscreener.com/latest/dex/search?q={q}") or {}
        for p in (d.get("pairs") or []):
            if p.get("chainId") != CHAIN:
                continue
            seen_pairs[p["pairAddress"]] = p
            for side in ("baseToken", "quoteToken"):
                t = p[side]
                toks[t["address"]] = t["symbol"]
        time.sleep(0.35)
    return toks, seen_pairs


def classify(tokens, workers=4):
    """totalSupply per token -> equity or not."""
    addrs = [a for a, s in tokens.items() if s.upper() not in NON_EQUITY]

    def one(a):
        ts = eth_call(a, "0x18160ddd")
        de = eth_call(a, "0x313ce567")
        return a, to_int(ts), (to_int(de) or 18)

    out = {}
    with ThreadPoolExecutor(workers) as ex:
        for a, raw, dec in ex.map(one, addrs):
            if not raw:
                continue
            supply = raw / 10 ** dec
            out[a] = {"symbol": tokens[a], "supply": supply, "decimals": dec,
                      "is_equity": supply < EQUITY_MAX_FLOAT}
    return out


REGISTRY = "registry.json"


def load_registry():
    try:
        return json.load(open(REGISTRY))
    except Exception:
        return {"equities": {}, "pairs": {}}


def pools_for(addr):
    d = fetch(f"https://api.dexscreener.com/token-pairs/v1/{CHAIN}/{addr}")
    return d if isinstance(d, list) else []


def pair_by_id(pair_id):
    d = fetch(f"https://api.dexscreener.com/latest/dex/pairs/{CHAIN}/{pair_id}")
    if not d:
        return None
    ps = d.get("pairs") or ([d["pair"]] if d.get("pair") else [])
    return ps[0] if ps else None


def build(min_liq):
    # PERSISTENT REGISTRY — do not rely on rediscovery.
    # DEX Screener's term search is non-deterministic and /token-pairs/v1 caps
    # at 30 pairs, so a live pool can silently drop out of enumeration between
    # runs. Observed: the AAPL/ICOIN pool ($634k, 907 units) vanished from one
    # run and reappeared, which naively reads as a -90% concentration collapse.
    # Phantom alerts like that would destroy trust in an alert product, so every
    # equity and every pair ever seen is remembered and re-fetched by id.
    reg = load_registry()
    tokens, _ = seed_tokens()
    meta = classify(tokens)
    equities = {a: m for a, m in meta.items() if m["is_equity"]}

    for a, m in equities.items():
        reg["equities"][a] = {"symbol": m["symbol"], "decimals": m["decimals"]}
    # re-price registry equities that this run's search failed to surface
    stale = [a for a in reg["equities"] if a not in equities]
    if stale:
        for a, m in classify({a: reg["equities"][a]["symbol"] for a in stale}).items():
            if m["is_equity"]:
                equities[a] = m
    print(f"seeded {len(tokens)} tokens -> {len(equities)} equities "
          f"({len(reg['equities'])} in registry)", file=sys.stderr)

    rows, per_stock = [], {}
    for addr, m in equities.items():
        pools = pools_for(addr)
        time.sleep(0.3)
        # union with every pair previously seen for this token
        seen_ids = {p["pairAddress"] for p in pools}
        for pid in reg["pairs"].get(addr, []):
            if pid in seen_ids:
                continue
            p = pair_by_id(pid)
            time.sleep(0.3)
            if p:
                pools.append(p)
        reg["pairs"][addr] = sorted(seen_ids | {p["pairAddress"] for p in pools})
        agg = {"symbol": m["symbol"], "address": addr, "supply": m["supply"],
               "units_in_pools": 0.0, "units_in_meme_pools": 0.0,
               "pool_count": 0, "liq_usd": 0.0, "top_meme": None, "top_meme_pct": 0.0}
        for p in pools:
            liq = p.get("liquidity") or {}
            usd = liq.get("usd", 0) or 0
            if usd < min_liq:
                continue
            base, quote = p["baseToken"], p["quoteToken"]
            if base["address"].lower() == addr.lower():
                units, counter = liq.get("base") or 0, quote
            elif quote["address"].lower() == addr.lower():
                units, counter = liq.get("quote") or 0, base
            else:
                continue
            cmeta = meta.get(counter["address"], {})
            # counterparty is a memecoin if it is not an equity and not a stable
            is_meme = (counter["symbol"].upper() not in NON_EQUITY
                       and not cmeta.get("is_equity", False))
            pct = units / m["supply"] * 100 if m["supply"] else 0
            agg["units_in_pools"] += units
            agg["pool_count"] += 1
            agg["liq_usd"] += usd
            if is_meme:
                agg["units_in_meme_pools"] += units
                if pct > agg["top_meme_pct"]:
                    agg["top_meme_pct"], agg["top_meme"] = pct, counter["symbol"]
            rows.append({
                "chain": CHAIN, "pair": p["pairAddress"], "dex": p.get("dexId"),
                "stock": m["symbol"], "stock_addr": addr,
                "counterparty": counter["symbol"], "counterparty_meme": is_meme,
                "liq_usd": usd, "vol24_usd": (p.get("volume") or {}).get("h24", 0),
                "stock_units_in_pool": units, "stock_float": m["supply"],
                "pct_of_float": pct,
            })
        agg["pct_float_in_pools"] = (agg["units_in_pools"] / m["supply"] * 100) if m["supply"] else 0
        agg["pct_float_in_meme_pools"] = (agg["units_in_meme_pools"] / m["supply"] * 100) if m["supply"] else 0
        per_stock[m["symbol"]] = agg

    json.dump(reg, open(REGISTRY, "w"), indent=1)
    return rows, per_stock


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="snapshots")
    ap.add_argument("--min-liq", type=float, default=25_000)
    a = ap.parse_args()

    rows, per_stock = build(a.min_liq)
    ts = datetime.datetime.now(datetime.timezone.utc)
    # Hour-stamped: concentration moves intraday and the series cannot be
    # backfilled, so an hourly run must never overwrite an earlier one.
    path = f"{a.out}/{ts:%Y-%m-%dT%H}.json"
    with open(path, "w") as f:
        json.dump({"captured_at": ts.isoformat(), "chain": CHAIN,
                   "per_stock": per_stock, "pools": rows}, f, indent=1)

    S = sorted(per_stock.values(), key=lambda s: -s["pct_float_in_meme_pools"])
    print(f"\nwrote {path}   {len(rows)} pools across {len(per_stock)} tokenized equities")
    print(f"\n{'stock':8}{'float (sh)':>13}{'in pools':>11}{'in MEME pools':>15}"
          f"{'top memecoin':>15}{'top pool %':>12}{'pool liq $':>14}")
    print("-" * 90)
    for s in S[:25]:
        if s["pct_float_in_pools"] < 0.05:
            continue
        print(f"{s['symbol'][:7]:8}{s['supply']:>13,.0f}"
              f"{s['pct_float_in_pools']:>10.1f}%{s['pct_float_in_meme_pools']:>14.1f}%"
              f"{str(s['top_meme'] or '-'):>15}{s['top_meme_pct']:>11.1f}%"
              f"${s['liq_usd']:>13,.0f}")

    meme_rows = [r for r in rows if r["counterparty_meme"]]
    print(f"\nmemecoin-paired pools: {len(meme_rows)}  "
          f"liquidity ${sum(r['liq_usd'] for r in meme_rows):,.0f}  "
          f"24h volume ${sum(r['vol24_usd'] for r in meme_rows):,.0f}")
    print(f"stocks with >10% of float in memecoin pools: "
          f"{sum(1 for s in per_stock.values() if s['pct_float_in_meme_pools'] > 10)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
