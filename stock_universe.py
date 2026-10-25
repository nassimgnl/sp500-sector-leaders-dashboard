"""Investable universe: the largest S&P 500 companies in each GICS sector.

The universe is built offline by ``scripts/build_universe.py`` and stored in
``data/universe.csv`` so the dashboard stays fast and its stock list is
reproducible and dated.
"""

from pathlib import Path

import pandas as pd

UNIVERSE_PATH = Path(__file__).resolve().parent / "data" / "universe.csv"
TOP_N_PER_SECTOR = 5
NON_MEMBER_MARK = "\\*"  # escaped asterisk, rendered as "*" in Markdown
REQUIRED_COLUMNS = ["ticker", "name", "sector", "market_cap_usd", "in_sp500", "as_of"]
GICS_SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]


def to_yahoo_ticker(symbol):
    """Convert an exchange symbol (e.g. ``BRK.B``) to Yahoo Finance format (``BRK-B``)."""
    return symbol.strip().upper().replace(".", "-")


def select_top_by_sector(constituents, n=TOP_N_PER_SECTOR):
    """Return the ``n`` largest companies per sector, one share class per company.

    ``constituents`` needs ``ticker``, ``sector``, ``cik`` and ``market_cap_usd``.
    Companies with several listed share classes (e.g. GOOGL / GOOG) share a CIK;
    only the first listed class is kept so a company never takes two slots.
    """
    return (
        constituents
        .dropna(subset=["market_cap_usd"])
        .drop_duplicates(subset="cik", keep="first")
        .sort_values("market_cap_usd", ascending=False, kind="stable")
        .groupby("sector", group_keys=False)
        .head(n)
        .sort_values(["sector", "market_cap_usd"], ascending=[True, False], kind="stable")
        .reset_index(drop=True)
    )


def merge_extra_holdings(top, extras):
    """Append hand-picked holdings that are not already in ``top``."""
    new_rows = extras[~extras["ticker"].isin(top["ticker"])]
    return pd.concat([top, new_rows], ignore_index=True)


def render_universe_table(universe):
    """Markdown summary of the universe (one row per sector, largest company first) for the README."""
    as_of = pd.Timestamp(universe["as_of"].iloc[0])
    def label(row):
        return row.ticker if row.in_sp500 else f"{row.ticker}{NON_MEMBER_MARK}"

    rows = [
        f"| {sector} | {', '.join(label(row) for row in stocks_in_sector(universe, sector).itertuples())} |"
        for sector in sorted(universe["sector"].unique())
    ]
    return "\n".join([
        f"Universe as of **{as_of.day} {as_of:%B %Y}** (sorted by market capitalisation within each sector):",
        "",
        "| GICS sector | Companies |",
        "|---|---|",
        *rows,
        "",
        f"{NON_MEMBER_MARK} Not an S&P 500 constituent.",
    ])


def stocks_in_sector(universe, sector):
    """Return the universe members of ``sector``, largest market cap first."""
    return universe[universe["sector"] == sector].sort_values("market_cap_usd", ascending=False, kind="stable")


def validate_universe(universe, source="Universe"):
    """Raise ``ValueError`` if ``universe`` does not have the expected shape."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(universe.columns))
    if missing:
        raise ValueError(f"{source} is missing columns: {missing}")
    if universe.empty:
        raise ValueError(f"{source} is empty")

    duplicates = universe.loc[universe["ticker"].duplicated(), "ticker"].unique().tolist()
    if duplicates:
        raise ValueError(f"{source} has duplicate tickers: {duplicates}")
    if universe["in_sp500"].dtype != bool:
        raise ValueError(f"{source} has non-boolean values in 'in_sp500'")

    return universe


def load_universe(path=None):
    """Load and validate the universe file (``UNIVERSE_PATH`` by default)."""
    path = path or UNIVERSE_PATH
    return validate_universe(pd.read_csv(path), source=f"Universe file {path}")
