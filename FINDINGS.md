# Memecoins are taxing tokenized stocks

**Measured 2026-09-07. Robinhood Chain. 365 observations, 7 stocks, back to 2026-07-02.**

On Robinhood Chain, a tokenized stock that is used as a memecoin's quote asset
trades **2–5% above the identical equity tokenized by a different issuer**.
Tokenized stocks with no memecoin attached trade at parity.

Everything below is reproducible with the code in this repo, from free APIs, no
keys required.

---

## The mechanism

Robinhood Chain launched 2026-07-01 to host tokenized equities. Memecoins took
it over — they were ~79% of DEX volume within a month. The unusual part is
*how*: a memecoin here is often quoted **against a tokenized stock** rather than
against a stablecoin. $BONER trades against tokenized HIMS. $QC trades against
tokenized IBM. $SAYLORMOON against tokenized MSTR.

To buy the memecoin, you must first acquire the stock token. That demand is
**price-insensitive** — the buyer wants $QC, not IBM equity, and will pay
whatever the stock token costs to get there.

So the stock token gets bid above the real share. The memecoin's popularity
leaks into the price of a tokenized security.

## The measurement

The same underlying equity is tokenized by several issuers — Robinhood, Ondo,
Backed (xStocks), Dinari. **Only Robinhood's version is used as memecoin
collateral.** So an xStock or Ondo token of the same stock is a near-perfect
control: same company, same 24/7 settlement, no memecoin bid.

```
premium = robinhood_token_price / control_token_price - 1
```

This needs no equity market data at all — both legs are crypto tokens trading
24/7, which sidesteps the market-hours alignment problem entirely.

## The result

Mean absolute premium, 2026-07-02 to 2026-09-07:

| Stock | Memecoin quoted against it | Mean \|premium\| |
|---|---|---|
| MSTR | $SAYLORMOON | **4.09%** |
| HIMS | $BONER | **4.03%** |
| IBM | $QC | **2.24%** |
| PLTR | — | 0.73% |
| AAPL | — | 0.68% |
| NVDA | — | 0.56% |
| TSLA | — | 0.51% |

A 6–8x separation, split cleanly by whether a memecoin quotes against the token.

### Cross-validated against a second, independent method

Measured live on 2026-09-07, comparing (A) Robinhood token vs its xStock/Ondo
twin, against (B) Robinhood token vs the real share price on Nasdaq:

| Stock | A: vs token twin | B: vs real share | Agree |
|---|---|---|---|
| MSTR | +2.32% | +2.31% | yes |
| HIMS | +2.25% | +1.95% | yes |
| NVDA | −0.02% | +0.85% | yes |
| TSLA | −0.06% | +0.09% | yes |
| IBM | +2.75% | +5.32% | **no — see below** |

Four of five agree closely. IBM disagreed because it was **converging in real
time**: the premium was +5.10% before the 09:30 ET open and +2.75% an hour
after. One observation, not a pattern, but it is the first direct evidence that
the premium compresses when the underlying market reopens.

## The float story

The same mechanism has a second-order effect. Because memecoin pools must
*hold* the stock token, they end up owning large fractions of its entire
on-chain float:

| Stock | Tokenized float (shares) | % held in memecoin pools | Largest single pool |
|---|---|---|---|
| HIMS | 130,876 | 34.0% | $BONER — **32.8%** |
| MU | 4,223 | 30.7% | $MOO |
| IBM | 2,168 | 27.4%–35.8% | $QC |
| AMC | 2,895,758 | 23.8% | $MEME |
| MSTR | 16,083 | 22.2% | $SAYLORMOON |

**One memecoin pool holds roughly a third of every tokenized HIMS share in
existence.**

### The issuer arbitrages its own premium

The Defiant reported the $BONER pool holding **31,198 of 58,714** tokenized HIMS
shares — 53.1%. As of 2026-09-07 it holds **42,826 of 130,876 — 32.7%**.

The pool grew 37%. The float **more than doubled**. Concentration fell because
Robinhood minted new tokens, not because the pool shrank.

That is the premium-collapse mechanism: mint new tokens, sell into the premium.
It is invisible in price data and only shows up if you track float directly.

---

## Three hypotheses that failed

Published because negative results in this area are rarer and more useful than
positive ones.

### 1. Fading the daily recap — direction right, framing wrong

Tokens named in a popular daily memecoin recap were all below their printed
peak ~24h later — 6 of 6, median −26%. But this is selection, not prediction:
a recap can only list things that already moved, so it is a list of local tops
by construction. Not an edge, just an artifact of how the list is built.

### 2. Cross-pool arbitrage — real, and already gone

The same tokenized stock quotes at different prices in different pools on the
same chain. Best live spread found was IBM at 0.74%, or **+0.14% net of 60bps
in fees**. Price impact eats it instantly: a $1,000 trade into the relevant
$130k pool costs ~77bps. **The edge survives only up to about $91 of size.**
The deepest names are the tightest (NVDA 0.09%), exactly as an efficient market
should look. Bots have this.

### 3. Premium mean-reversion — an artifact, and it fooled me first

The headline looked strong:

```
b = -0.728   corr = -0.603   half-life = 1.0 days   (n=365)
```

It was **one bad day**. On 2026-08-31, MSTR printed a +89.44% premium and HIMS
+74.31% — two unrelated stocks spiking together, which is a data glitch, not a
market event. Removing that single day flips the sign:

| Sample | b | corr | tercile spread |
|---|---|---|---|
| All | −0.728 | −0.603 | +0.86% (0.14 sd) |
| **Excl. 2026-08-31** | **+0.222** | +0.126 | +0.02% (0.00 sd) |
| Excl. \|prem\|>5% | +0.122 | +0.029 | −0.26% |

And the memecoin-quoted subset — where the theory actually applies — shows
corr −0.082 and a 0.01 sd spread. Nothing. The strongest apparent effect sits
in the **non-memecoin control group** (0.74 sd), which is backwards from the
theory and is just bid/ask oscillation in tightly-tracking tokens.

**Conclusion: the premium is a persistent level difference, not a tradeable
signal.** It is a cost to disclose, not a convergence to trade.

---

## If you build on this data, read this first

DEX Screener's raw output for this chain is not usable as-is.

- **A pool reported $1.16bn of liquidity while holding zero units** and doing $8
  of daily volume — an implied $1.5 trillion per share. Validation cut total
  reported liquidity from **$1.18bn to $20.6M**, a 98% correction.
- **Pool discovery is non-deterministic.** Term search varies between runs and
  `/token-pairs/v1` caps at 30 pairs, so live pools drop out of enumeration. On
  the first diff this produced a phantom "AAPL concentration collapsed 90%"
  alert; the pool was verifiably still live with $627k in it. A persistent
  registry is a correctness requirement, not an optimisation.
- **Symbol collisions are everywhere.** Memecoins name themselves after the
  ticker they quote against — there is a memecoin called `SPY` quoted against
  tokenized `NVDA`, and `GME/GME` pools. Aggregating by symbol instead of
  contract address produced HOOD at 4873% of float.
- **Robinhood Chain runs Uniswap v4.** Pool IDs are 32 bytes, not addresses;
  `balanceOf(pool)` is meaningless because tokens sit in the singleton
  PoolManager. Reserves must come from an indexer.
- The public RPC **403s on JSON-RPC batch requests** and is **not an archive
  node** (no historical state).

## Limitations

- Robinhood Chain launched 2026-07-01; some tokens listed later. The sample is
  short and the tokens with the largest premiums (IBM, HIMS) have the fewest
  observations (24–26 days).
- CoinGecko daily points are UTC-midnight snapshots, so this cannot see
  convergence at the 09:30 ET open. That question is open.
- Overlapping forward windows make observations non-independent. Treat any
  single statistic as indicative.
- Only tokens CoinGecko lists today are included — survivorship.
- One documented data glitch (2026-08-31) is present in the raw series and is
  excluded from the robustness cuts rather than silently deleted.

## Reproduce it

```bash
python3 collect.py            # snapshot pools + float concentration
python3 report.py             # validated concentration table
python3 premium.py            # live premium vs real share prices
python3 backtest_premium.py   # the mean-reversion test, incl. the artifact
```

Data sources: DEX Screener (pools/reserves), CoinGecko (token prices), the
public Robinhood Chain RPC (`totalSupply`). All free, no keys.

## Not investment advice

This is measurement, published because it is interesting. Everything tradeable
in it was tested and failed. The pools involved are thin, the tokens are
memecoins, and the equity tokens are unregistered instruments issued offshore
that carry no shareholder rights.
