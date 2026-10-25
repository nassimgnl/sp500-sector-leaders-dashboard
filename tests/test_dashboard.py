from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from stock_universe import GICS_SECTORS, load_universe

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT_SECONDS = 90
EXPECTED_METRICS = [
    "Current Price", "Period Return", "Annual Volatility", "Sharpe Ratio", "Max Drawdown",
    "Beta", "Correlation", "Tracking Error", "Information Ratio",
]
UNIVERSE = load_universe()


def run_app(sector=None, ticker=None):
    app = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT_SECONDS).run()
    if sector is not None:
        app.selectbox(key="sector").select(sector).run()
    if ticker is not None:
        app.selectbox(key="ticker").select(ticker).run()
    return app


def page_text(app):
    return " ".join(str(block.value) for block in app.markdown)


def test_defaults_to_nvidia_in_information_technology():
    app = run_app()

    assert not app.exception
    assert app.selectbox(key="sector").value == "Information Technology"
    assert app.selectbox(key="ticker").value == "NVDA"
    assert [metric.label for metric in app.metric] == EXPECTED_METRICS
    assert "NVDA" in page_text(app)


def test_sector_dropdown_lists_every_gics_sector():
    app = run_app()

    assert sorted(app.selectbox(key="sector").options) == sorted(GICS_SECTORS)


def test_stock_dropdown_lists_sector_members_by_market_cap():
    app = run_app(sector="Financials")

    expected = UNIVERSE[UNIVERSE["sector"] == "Financials"].sort_values("market_cap_usd", ascending=False)
    labels = app.selectbox(key="ticker").options

    assert not app.exception
    assert len(labels) == len(expected)
    assert all(f"({ticker})" in label for ticker, label in zip(expected["ticker"], labels))


def test_switching_sector_selects_its_largest_company():
    app = run_app(sector="Energy")

    largest = UNIVERSE[UNIVERSE["sector"] == "Energy"].nlargest(1, "market_cap_usd")["ticker"].item()

    assert not app.exception
    assert app.selectbox(key="ticker").value == largest


@pytest.mark.parametrize("sector, ticker", [
    ("Information Technology", "TSM"),
    ("Information Technology", "AAPL"),
    ("Industrials", "ETN"),
])
def test_selecting_a_stock_updates_the_dashboard(sector, ticker):
    app = run_app(sector=sector, ticker=ticker)

    assert not app.exception
    assert [metric.label for metric in app.metric] == EXPECTED_METRICS
    assert ticker in page_text(app)
    assert "NVDA" not in page_text(app)


def test_benchmark_is_the_sp500_total_return_index():
    app = run_app()

    chart_specs = " ".join(chart.proto.spec for chart in app.get("plotly_chart"))

    assert "S&P 500 Total Return" in chart_specs
