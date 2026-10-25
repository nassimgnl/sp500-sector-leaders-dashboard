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
    ("Information Technology", "AAPL"),
    ("Industrials", "CAT"),
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


@pytest.fixture
def isolated_universe(tmp_path, monkeypatch):
    """Point the app at a copy of the universe file so refresh tests never touch the real one."""
    import stock_universe

    path = tmp_path / "universe.csv"
    path.write_bytes(stock_universe.UNIVERSE_PATH.read_bytes())
    monkeypatch.setattr(stock_universe, "UNIVERSE_PATH", path)
    return path


def use_builder(monkeypatch, build):
    import universe_refresh

    monkeypatch.setattr(universe_refresh, "build_universe", build)


def click_refresh(app):
    return app.button(key="refresh_universe").click().run()


def test_refresh_button_shows_the_universe_date(isolated_universe):
    app = run_app()

    assert not app.exception
    assert app.button(key="refresh_universe").label == "Update S&P 500 data"
    assert UNIVERSE["as_of"].iloc[0] in page_text(app)


def test_refresh_keeps_universe_when_top_five_is_unchanged(isolated_universe, monkeypatch):
    original = isolated_universe.read_bytes()
    use_builder(monkeypatch, lambda: UNIVERSE.assign(market_cap_usd=UNIVERSE["market_cap_usd"] * 1.1, as_of="2026-11-02"))

    app = click_refresh(run_app())

    assert not app.exception
    assert any("has not changed" in message.value for message in app.info)
    assert isolated_universe.read_bytes() == original


def test_refresh_updates_dropdown_when_a_company_enters_the_top_five(isolated_universe, monkeypatch):
    replaced = UNIVERSE["ticker"] == "VLO"
    candidate = UNIVERSE.assign(
        ticker=UNIVERSE["ticker"].where(~replaced, "OXY"),
        name=UNIVERSE["name"].where(~replaced, "Occidental Petroleum"),
        as_of="2026-11-02",
    )
    use_builder(monkeypatch, lambda: candidate)

    app = click_refresh(run_app(sector="Energy", ticker="VLO"))

    assert not app.exception
    message = " ".join(success.value for success in app.success)
    assert "OXY" in message and "VLO" in message
    assert any("(OXY)" in label for label in app.selectbox(key="ticker").options)
    assert app.selectbox(key="ticker").value != "VLO"
    assert "2026-11-02" in page_text(app)


def test_refresh_failure_keeps_universe_and_reports_error(isolated_universe, monkeypatch):
    original = isolated_universe.read_bytes()

    def failing_build():
        raise RuntimeError("source unavailable")

    use_builder(monkeypatch, failing_build)

    app = click_refresh(run_app())

    assert not app.exception
    assert any("source unavailable" in error.value for error in app.error)
    assert isolated_universe.read_bytes() == original


def test_refresh_updates_the_dashboard_even_when_saving_is_impossible(isolated_universe, monkeypatch):
    import universe_refresh

    original = isolated_universe.read_bytes()
    replaced = UNIVERSE["ticker"] == "VLO"
    candidate = UNIVERSE.assign(
        ticker=UNIVERSE["ticker"].where(~replaced, "OXY"),
        name=UNIVERSE["name"].where(~replaced, "Occidental Petroleum"),
        as_of="2026-11-02",
    )
    use_builder(monkeypatch, lambda: candidate)

    def read_only_save(universe, path):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(universe_refresh, "save_universe", read_only_save)

    app = click_refresh(run_app(sector="Energy"))

    assert not app.exception
    assert any("this session" in message.value for message in app.warning)

    app.run()  # the session keeps the unsaved update on later interactions

    assert any("(OXY)" in label for label in app.selectbox(key="ticker").options)
    assert "2026-11-02" in page_text(app)
    assert isolated_universe.read_bytes() == original
