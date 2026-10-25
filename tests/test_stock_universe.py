import pandas as pd
import pytest

from stock_universe import (
    GICS_SECTORS,
    REQUIRED_COLUMNS,
    TOP_N_PER_SECTOR,
    load_universe,
    merge_extra_holdings,
    render_universe_table,
    select_top_by_sector,
    to_yahoo_ticker,
)


def make_constituents(rows):
    return pd.DataFrame(rows, columns=["ticker", "name", "sector", "cik", "market_cap_usd"])


@pytest.mark.parametrize("raw, expected", [
    ("BRK.B", "BRK-B"),
    (" aapl ", "AAPL"),
    ("BF.B", "BF-B"),
])
def test_to_yahoo_ticker_normalizes_wikipedia_symbols(raw, expected):
    assert to_yahoo_ticker(raw) == expected


def test_select_top_by_sector_keeps_largest_companies_per_sector():
    constituents = make_constituents([
        ("A", "Alpha", "Energy", 1, 50.0),
        ("B", "Beta", "Energy", 2, 300.0),
        ("C", "Gamma", "Energy", 3, 100.0),
        ("D", "Delta", "Utilities", 4, 10.0),
    ])

    top = select_top_by_sector(constituents, n=2)

    assert top["ticker"].tolist() == ["B", "C", "D"]


def test_select_top_by_sector_keeps_one_share_class_per_company():
    constituents = make_constituents([
        ("GOOGL", "Alphabet Inc. (Class A)", "Communication Services", 1652044, 2000.0),
        ("GOOG", "Alphabet Inc. (Class C)", "Communication Services", 1652044, 2000.0),
        ("META", "Meta Platforms", "Communication Services", 1326801, 1500.0),
    ])

    top = select_top_by_sector(constituents, n=5)

    assert top["ticker"].tolist() == ["GOOGL", "META"]


def test_select_top_by_sector_ignores_missing_market_caps():
    constituents = make_constituents([
        ("A", "Alpha", "Energy", 1, None),
        ("B", "Beta", "Energy", 2, 10.0),
    ])

    top = select_top_by_sector(constituents, n=5)

    assert top["ticker"].tolist() == ["B"]


def test_select_top_by_sector_does_not_mutate_input():
    constituents = make_constituents([
        ("A", "Alpha", "Energy", 1, 50.0),
        ("B", "Beta", "Energy", 2, 300.0),
    ])
    snapshot = constituents.copy()

    select_top_by_sector(constituents, n=1)

    pd.testing.assert_frame_equal(constituents, snapshot)


def test_merge_extra_holdings_appends_only_new_tickers():
    top = pd.DataFrame({"ticker": ["NVDA"], "name": ["Nvidia"], "market_cap_usd": [4000.0]})
    extras = pd.DataFrame({"ticker": ["NVDA", "TSM"], "name": ["Duplicate", "TSMC"], "market_cap_usd": [1.0, 1000.0]})

    merged = merge_extra_holdings(top, extras)

    assert merged["ticker"].tolist() == ["NVDA", "TSM"]
    assert merged.loc[merged["ticker"] == "NVDA", "name"].item() == "Nvidia"


def test_load_universe_rejects_missing_columns(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame({"ticker": ["AAPL"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing columns"):
        load_universe(path)


def test_load_universe_rejects_duplicate_tickers(tmp_path):
    path = tmp_path / "universe.csv"
    row = {column: "x" for column in REQUIRED_COLUMNS}
    pd.DataFrame([{**row, "ticker": "AAPL"}, {**row, "ticker": "AAPL"}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate tickers"):
        load_universe(path)


def test_shipped_universe_covers_every_gics_sector_with_top_sp500_names():
    universe = load_universe()

    sp500_members = universe[universe["in_sp500"]]
    counts = sp500_members.groupby("sector")["ticker"].count()

    assert sorted(counts.index) == sorted(GICS_SECTORS)
    assert (counts >= TOP_N_PER_SECTOR).all()
    assert {"TSM", "ETN"} <= set(universe["ticker"])


def test_render_universe_table_lists_sectors_by_market_cap_and_flags_non_members():
    universe = pd.DataFrame([
        {"ticker": "CVX", "name": "Chevron", "sector": "Energy", "market_cap_usd": 400.0, "in_sp500": True, "as_of": "2026-11-02"},
        {"ticker": "XOM", "name": "Exxon", "sector": "Energy", "market_cap_usd": 700.0, "in_sp500": True, "as_of": "2026-11-02"},
        {"ticker": "TSM", "name": "TSMC", "sector": "Information Technology", "market_cap_usd": 2000.0, "in_sp500": False, "as_of": "2026-11-02"},
    ])

    table = render_universe_table(universe)

    assert "Universe as of **2 November 2026**" in table
    assert "| Energy | XOM, CVX |" in table
    assert "| Information Technology | TSM\\* |" in table
