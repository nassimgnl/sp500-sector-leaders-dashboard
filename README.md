# S&P 500 Sector Leaders — Equity Risk & Performance Dashboard

[![Live demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://sp500-sector-leaders.streamlit.app)
[![Tests](https://github.com/nassimgnl/sp500-sector-leaders-dashboard/actions/workflows/tests.yml/badge.svg)](https://github.com/nassimgnl/sp500-sector-leaders-dashboard/actions/workflows/tests.yml)
[![Universe update](https://github.com/nassimgnl/sp500-sector-leaders-dashboard/actions/workflows/update-universe.yml/badge.svg)](https://github.com/nassimgnl/sp500-sector-leaders-dashboard/actions/workflows/update-universe.yml)

**▶ [Open the live dashboard](https://sp500-sector-leaders.streamlit.app)**: no installation needed.

An interactive dashboard to analyse the risk and return profile of the largest U.S. companies in each GICS sector, benchmarked against the S&P 500 Total Return index.

Built with Python, pandas, Plotly and Streamlit, using publicly available market data.

**Author:** Nassim Goundoul

![Dashboard screenshot](docs/dashboard.png)

---

## Why this project

When a portfolio manager or fund selector reviews a stock, the first questions are always the same:

- How much did it return over the period, and **how much risk was taken** to get there?
- What was the **worst peak-to-trough loss** an investor actually had to sit through?
- Did it **outperform its benchmark** on a like-for-like (dividends included) basis?
- How were returns **distributed over time**: steady compounding or a few extreme months?

This dashboard answers these questions in a single screen for the market leaders of every sector of the S&P 500, so that companies can be compared on a consistent, reproducible methodology.

## Features

- **Sector-based stock selection**: pick one of the 11 GICS sectors, then one of its largest companies (ranked by market capitalisation).
- **Key risk & return metrics**: period total return, annualised volatility, Sharpe ratio and maximum drawdown.
- **Benchmark-relative metrics**, as used in fund selection: beta, correlation, tracking error and information ratio against the S&P 500 Total Return index.
- **Price chart** with optional 50-day and 200-day moving averages.
- **Benchmark comparison**: growth of $100 invested in the stock vs. the S&P 500 Total Return index, dividends reinvested on both sides.
- **Monthly returns**, **daily return distribution** and **drawdown** charts.
- **Adjustable analysis window** (start and end dates in the sidebar).
- **One-click universe update**: the *Update S&P 500 data* button recomputes the top five of each sector from the latest index membership and market caps, and updates the stock list only if it actually changed.

## Investment universe

The selectable universe is the **five largest S&P 500 constituents by market capitalisation in each of the 11 GICS sectors**, plus two hand-picked additions: Taiwan Semiconductor Manufacturing (TSM, an ADR that is not an S&P 500 member) and Eaton Corporation (ETN).

Construction rules (`universe_refresh.py`):

1. Download the current S&P 500 constituent list with each company's GICS sector.
2. Retrieve each constituent's market capitalisation.
3. Keep **one share class per company** (e.g. GOOGL but not GOOG) so a company never takes two slots in its sector.
4. Rank companies within each sector by market capitalisation and keep the top five.
5. Save the result, with its build date, to `data/universe.csv`.

<!-- universe:start -->
Universe as of **25 October 2026** (sorted by market capitalisation within each sector):

| GICS sector | Companies |
|---|---|
| Communication Services | GOOGL, META, NFLX, DIS, VZ |
| Consumer Discretionary | AMZN, TSLA, HD, MCD, TJX |
| Consumer Staples | WMT, COST, KO, PG, PM |
| Energy | XOM, CVX, COP, MPC, VLO |
| Financials | BRK-B, JPM, V, MA, BAC |
| Health Care | LLY, JNJ, ABBV, UNH, MRK |
| Industrials | CAT, GE, RTX, GEV, DE, ETN |
| Information Technology | NVDA, AAPL, MSFT, TSM\*, AVGO, MU |
| Materials | LIN, NEM, FCX, SHW, ECL |
| Real Estate | WELL, PLD, EQIX, AMT, SPG |
| Utilities | NEE, SO, DUK, CEG, AEP |

\* Not an S&P 500 constituent.
<!-- universe:end -->

Storing the universe in a versioned file, rather than recomputing it on every page load, keeps the dashboard fast and makes the stock list **reproducible and dated**.

### Updating the universe

Click **Update S&P 500 data** in the dashboard (or run `python scripts/build_universe.py`). The universe is rebuilt from the latest data and compared with the current one:

- **Composition unchanged**: if the same companies are in the same sectors, the file is left untouched and keeps its original date, even if market caps or the ranking inside the top five moved.
- **Composition changed**: if a company entered or left a sector's top five, or was reclassified to another sector, the new universe is saved with the current date and the dashboard lists the companies added and removed.
- **Download failure**: if a source is unreachable or returns unexpected data, nothing is written and the current universe stays in use.
- **Read-only hosting**: if the new universe cannot be saved on the server, it is still applied to the visitor's session, so the update is always visible.

The file is written atomically (temporary file, then rename), so an interrupted update can never leave a half-written universe.

### Automatic daily update

A scheduled GitHub Actions workflow ([`update-universe.yml`](.github/workflows/update-universe.yml)) runs the same update after every US trading day. When the composition changed, it commits the new `data/universe.csv` and regenerates the universe table of this README; the live dashboard then redeploys automatically from the repository. No local machine is involved.

## Data sources

| Data | Source | Notes |
|---|---|---|
| S&P 500 membership, GICS sector, CIK | [Wikipedia: List of S&P 500 companies](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies) | Publicly maintained mirror of the S&P Dow Jones Indices constituent list |
| Market capitalisation | Yahoo Finance, via [`yfinance`](https://github.com/ranaroussi/yfinance) | Used only to rank companies when building the universe |
| Daily stock prices | Yahoo Finance, via `yfinance` | Close prices **adjusted for splits and dividends** (`auto_adjust=True`) |
| Benchmark | Yahoo Finance: S&P 500 Total Return index (`^SP500TR`) | Dividends reinvested, consistent with the adjusted stock prices |

Using the **total return** version of the index is deliberate: comparing dividend-adjusted stock prices with the price-only S&P 500 (`^GSPC`) would overstate the stock's relative performance. Since January 2021 the gap between the two indices is roughly 18 percentage points.

Prices are cached for one hour in the app to limit calls to the data provider.

## Methodology

All metrics are computed from daily adjusted close prices $P_t$ over the selected window, assuming 252 trading days per year. Benchmark-relative metrics use only the dates on which both the stock and the benchmark have a return (`metrics.py`).

| Metric | Definition |
|---|---|
| Daily return | $r_t = P_t / P_{t-1} - 1$ |
| Period return | $P_T / P_0 - 1$ (total return, since prices include dividends) |
| Annualised return | $(1 + \bar{r})^{252} - 1$, where $\bar{r}$ is the mean daily return |
| Annualised volatility | $\sigma(r_t) \times \sqrt{252}$ |
| Sharpe ratio | (annualised return − 4%) / annualised volatility, with a constant 4% risk-free rate |
| Maximum drawdown | $\min_t \left( P_t / \max_{s \le t} P_s - 1 \right)$ |
| Beta | $\mathrm{Cov}(r^{s}, r^{b}) / \mathrm{Var}(r^{b})$, where $r^{s}$ and $r^{b}$ are the stock and benchmark daily returns |
| Correlation | Pearson correlation of $r^{s}$ and $r^{b}$ |
| Tracking error | $\sigma(r^{s} - r^{b}) \times \sqrt{252}$ |
| Information ratio | $252 \times \overline{(r^{s} - r^{b})}$ / tracking error |
| Moving averages | Simple 50-day and 200-day averages of the adjusted close |
| Monthly returns | Month-end to month-end change in the adjusted close |
| Growth of $100 | $100 \times P_t / P_0$ for both the stock and the benchmark |

## Limitations

These are known simplifications. They are acceptable for an exploratory tool and are listed here explicitly:

- **Look-ahead and survivorship bias**: the universe is selected using *today's* market capitalisations and applied to past periods. Today's sector leaders are, by construction, companies that did well, so historical results for this universe are flattering.
- **Constant risk-free rate**: the Sharpe ratio uses a flat 4% instead of the actual T-bill rate over the period.
- **Annualisation**: the annualised return compounds the arithmetic mean daily return, which is higher than the realised CAGR for volatile stocks.
- **Single benchmark**: every stock is compared with the broad S&P 500 rather than its own sector index.
- **Data provider**: Yahoo Finance is a free, unofficial source and is not suited to production use.

## Roadmap

- Further fund-selection metrics: **Jensen's alpha**, **up/down capture ratios**, batting average.
- **Sector benchmarks** (e.g. SPDR sector ETFs) in addition to the S&P 500.
- **Time-varying risk-free rate** (13-week T-bill, `^IRX`) for the Sharpe ratio and a **Sortino ratio**.
- **Rolling** volatility, Sharpe and correlation windows.
- Side-by-side comparison of several stocks.
- **Point-in-time universe** to remove look-ahead bias in historical analysis.

## Project structure

```
.
├── app.py                    # Streamlit dashboard
├── metrics.py                # Benchmark-relative metrics (beta, tracking error, ...)
├── stock_universe.py         # Universe selection rules and validation
├── universe_refresh.py       # Live rebuild of the universe, saved only if it changed
├── scripts/
│   └── build_universe.py     # Command-line universe update (also used by the scheduled workflow)
├── .github/workflows/       # CI tests and daily universe update
├── data/
│   └── universe.csv          # Dated stock universe used by the dashboard
├── tests/                    # Unit tests (universe rules) and app tests (Streamlit AppTest)
├── docs/
│   └── dashboard.png
├── .streamlit/config.toml    # Dark theme
├── requirements.txt
└── requirements-dev.txt
```

## Getting started

Requires Python 3.11 or later.

```bash
git clone https://github.com/nassimgnl/sp500-sector-leaders-dashboard.git
cd sp500-sector-leaders-dashboard

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

streamlit run app.py
```

The dashboard opens at http://localhost:8501.

To refresh the stock universe with current market capitalisations:

```bash
python scripts/build_universe.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite covers the benchmark-relative metrics (checked against synthetic return series with known answers), the universe selection rules (top-N ranking, share-class de-duplication, input validation), the update logic (file rewritten only when the composition changes, untouched on failure), the integrity of the shipped universe file, and the dashboard itself (default view, sector and stock selection, benchmark choice, update button) using Streamlit's `AppTest`. The app tests download live market data and therefore need an internet connection.

## Disclaimer

This project is for educational and portfolio purposes only. It does not constitute investment advice or a recommendation to buy or sell any security.
