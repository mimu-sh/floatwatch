# floatwatch

Tracks what fraction of a tokenized stock's on-chain float is locked inside
memecoin liquidity pools — and what that does to its price.

On Robinhood Chain, memecoins are frequently quoted **against tokenized
equities** rather than stablecoins. Buying the memecoin means first buying the
stock token, which creates price-insensitive demand for a tokenized security.

**Headline finding: memecoin-quoted stock tokens trade 2–5% above the identical
equity tokenized by another issuer. Tokens with no memecoin attached trade at
parity.** Full writeup, including three hypotheses that failed: **[FINDINGS.md](FINDINGS.md)**

```
Stock   memecoin        mean |premium|      Stock   memecoin   mean |premium|
MSTR    $SAYLORMOON          4.09%          PLTR    —               0.73%
HIMS    $BONER               4.03%          AAPL    —               0.68%
IBM     $QC                  2.24%          NVDA    —               0.56%
                                            TSLA    —               0.51%
```

One memecoin pool holds **32.8% of every tokenized HIMS share in existence**.

## Why the series matters

Float concentration **cannot be backfilled**. Nobody can reconstruct today's
number tomorrow. `snapshots/` is an append-only record starting 2026-09-07.

## Usage

```bash
python3 collect.py            # snapshot every stock-paired pool + float concentration
python3 report.py             # validated concentration table (see validation notes)
python3 diff.py               # what changed between snapshots, with pool-set verification
python3 premium.py --record   # premium vs real share prices
python3 backtest_premium.py   # mean-reversion test using same-stock token controls
./run_hourly.sh               # collect + report + paper-trade mark, for cron
```

No API keys. Data from DEX Screener, CoinGecko, and the public Robinhood Chain RPC.

## Files

| File | Purpose |
|---|---|
| `collect.py` | Discovery → equity classification → pool enumeration → float division |
| `report.py` | Validation layer. Kept separate so raw snapshots stay immutable |
| `diff.py` | Concentration changes, tagged `[pool set stable]` vs `[UNVERIFIED]` |
| `premium.py` | Tokenized price vs real share price |
| `backtest_premium.py` | Premium mean-reversion test with same-stock controls |
| `simulate.py` / `check.py` | Pre-registered paper positions, costs modelled |
| `registry.json` | Persistent token/pair registry — required for correct diffs |
| `snapshots/` | The append-only record. Never edit |

## A warning about the underlying data

Raw DEX Screener output for this chain is not usable without validation — one
pool reported **$1.16bn of liquidity while holding zero units**, and validation
cut total reported liquidity by 98%. Pool discovery is also non-deterministic,
which produces phantom "concentration collapsed" alerts unless you keep a
persistent registry. Details and the rest of the traps are in
[FINDINGS.md](FINDINGS.md#if-you-build-on-this-data-read-this-first).

## Not investment advice

Measurement, published because it is interesting. Every tradeable hypothesis
tested here failed, and they are documented alongside the finding that worked.

MIT licensed.
