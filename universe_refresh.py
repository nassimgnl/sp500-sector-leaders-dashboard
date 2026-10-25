"""Rebuild the stock universe from live sources and save it only when its composition changes.

Sources
- Index membership, GICS sector and CIK: Wikipedia "List of S&P 500 companies"
- Market capitalisation: Yahoo Finance (via yfinance)
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

import stock_universe
from stock_universe import (
    GICS_SECTORS,
    REQUIRED_COLUMNS,
    select_top_by_sector,
    to_yahoo_ticker,
    validate_universe,
)

CONSTITUENTS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-analytics-dashboard universe builder)"}
REQUEST_TIMEOUT_SECONDS = 30
MARKET_CAP_WORKERS = 8
MIN_CONSTITUENTS = 490
MAX_MISSING_MARKET_CAP_SHARE = 0.05

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshResult:
    changed: bool
    added: tuple
    removed: tuple
    as_of: str
    universe: pd.DataFrame
    saved: bool = True


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
    """Download today's constituents and market caps and return the candidate universe."""
    constituents = fetch_constituents()
    log.info("Parsed %d S&P 500 constituents", len(constituents))

    tickers = sorted(constituents["ticker"])
    market_caps = fetch_market_caps(tickers)

    missing = [ticker for ticker, cap in market_caps.items() if cap is None]
    if len(missing) > MAX_MISSING_MARKET_CAP_SHARE * len(tickers):
        raise RuntimeError(f"Market cap missing for {len(missing)} tickers, aborting: {missing[:20]}")

    with_caps = constituents.assign(market_cap_usd=constituents["ticker"].map(market_caps))
    return select_top_by_sector(with_caps).assign(as_of=date.today().isoformat())[REQUIRED_COLUMNS]


def composition(universe):
    """The part of the universe that matters for a refresh: which company sits in which sector."""
    return set(zip(universe["ticker"], universe["sector"]))


def universe_changes(current, candidate):
    """Return ``(added, removed)`` tickers, each sorted alphabetically."""
    current_tickers, candidate_tickers = set(current["ticker"]), set(candidate["ticker"])
    return tuple(sorted(candidate_tickers - current_tickers)), tuple(sorted(current_tickers - candidate_tickers))


def save_universe(universe, path):
    """Write the universe atomically so a failure never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    universe.to_csv(temporary, index=False, float_format="%.0f")
    os.replace(temporary, path)


def refresh_universe(path=None, build=None):
    """Rebuild the universe and overwrite ``path`` only if its composition changed.

    Changes in market caps or in the ranking inside the top five are ignored:
    the file is rewritten only when a company enters or leaves the universe,
    or moves to another sector.
    """
    path = Path(path or stock_universe.UNIVERSE_PATH)
    candidate = validate_universe((build or build_universe)(), source="Rebuilt universe")
    current = stock_universe.load_universe(path) if path.exists() else candidate.iloc[0:0]

    if composition(candidate) == composition(current):
        return RefreshResult(changed=False, added=(), removed=(), as_of=str(current["as_of"].iloc[0]), universe=current)

    added, removed = universe_changes(current, candidate)
    try:
        save_universe(candidate, path)
        saved = True
    except OSError as error:
        # Hosted deployments may have a read-only or ephemeral disk: the update still applies in memory.
        log.warning("Universe changed but could not be saved to %s: %s", path, error)
        saved = False

    return RefreshResult(changed=True, added=added, removed=removed, as_of=str(candidate["as_of"].iloc[0]),
                         universe=candidate, saved=saved)
