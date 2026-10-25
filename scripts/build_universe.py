"""Build data/universe.csv: the five largest S&P 500 companies per GICS sector.

Sources
- Index membership, GICS sector and CIK: Wikipedia "List of S&P 500 companies"
- Market capitalisation: Yahoo Finance (via yfinance)

Usage
    python scripts/build_universe.py
"""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_universe import (  # noqa: E402
    GICS_SECTORS,
    REQUIRED_COLUMNS,
    UNIVERSE_PATH,
    merge_extra_holdings,
    select_top_by_sector,
    to_yahoo_ticker,
)

CONSTITUENTS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-analytics-dashboard universe builder)"}
REQUEST_TIMEOUT_SECONDS = 30
MARKET_CAP_WORKERS = 8
MIN_CONSTITUENTS = 490
MAX_MISSING_MARKET_CAP_SHARE = 0.05

# Holdings kept in the universe regardless of their sector rank.
# TSM is a US-listed ADR, so it is not an S&P 500 member.
EXTRA_HOLDINGS = {
    "TSM": ("Taiwan Semiconductor Manufacturing (ADR)", "Information Technology"),
    "ETN": ("Eaton Corporation", "Industrials"),
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("build_universe")


def fetch_constituents():
    response = requests.get(CONSTITUENTS_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    table = pd.read_html(StringIO(response.text), attrs={"id": "constituents"})[0]
    constituents = pd.DataFrame({
        "ticker": table["Symbol"].map(to_yahoo_ticker),
        "name": table["Security"].str.strip(),
        "sector": table["GICS Sector"].str.strip(),
        "cik": table["CIK"],
    })

    if len(constituents) < MIN_CONSTITUENTS:
        raise RuntimeError(f"Only {len(constituents)} constituents parsed; the source page layout may have changed")
    unknown_sectors = set(constituents["sector"]) - set(GICS_SECTORS)
    if unknown_sectors:
        raise RuntimeError(f"Unexpected GICS sectors in source: {sorted(unknown_sectors)}")

    return constituents


def fetch_market_cap(ticker):
    try:
        return float(yf.Ticker(ticker).fast_info["marketCap"])
    except Exception as error:  # yfinance raises many unrelated exception types
        log.warning("No market cap for %s: %s", ticker, error)
        return None


def fetch_market_caps(tickers):
    with ThreadPoolExecutor(max_workers=MARKET_CAP_WORKERS) as pool:
        return dict(zip(tickers, pool.map(fetch_market_cap, tickers)))


def build_universe():
    constituents = fetch_constituents()
    log.info("Parsed %d S&P 500 constituents", len(constituents))

    tickers = sorted(set(constituents["ticker"]) | set(EXTRA_HOLDINGS))
    market_caps = fetch_market_caps(tickers)

    missing = [ticker for ticker, cap in market_caps.items() if cap is None]
    if len(missing) > MAX_MISSING_MARKET_CAP_SHARE * len(tickers):
        raise RuntimeError(f"Market cap missing for {len(missing)} tickers, aborting: {missing[:20]}")

    with_caps = constituents.assign(market_cap_usd=constituents["ticker"].map(market_caps))
    top = select_top_by_sector(with_caps).assign(in_sp500=True)

    extras = pd.DataFrame([
        {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "market_cap_usd": market_caps[ticker],
            "in_sp500": ticker in set(constituents["ticker"]),
        }
        for ticker, (name, sector) in EXTRA_HOLDINGS.items()
    ])

    return (
        merge_extra_holdings(top, extras)
        .assign(as_of=date.today().isoformat())
        .sort_values(["sector", "market_cap_usd"], ascending=[True, False], kind="stable")
        [REQUIRED_COLUMNS]
    )


def main():
    universe = build_universe()
    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(UNIVERSE_PATH, index=False, float_format="%.0f")
    log.info("Wrote %d stocks across %d sectors to %s", len(universe), universe["sector"].nunique(), UNIVERSE_PATH)


if __name__ == "__main__":
    main()
