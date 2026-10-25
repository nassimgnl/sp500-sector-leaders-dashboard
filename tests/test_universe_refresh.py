import pandas as pd
import pytest

import universe_refresh
from stock_universe import REQUIRED_COLUMNS, load_universe
from universe_refresh import refresh_universe, universe_changes

TODAY = "2026-11-02"


def make_universe(rows, as_of="2026-10-25"):
    return pd.DataFrame(
        [{"ticker": ticker, "name": ticker, "sector": sector, "market_cap_usd": cap, "as_of": as_of}
         for ticker, sector, cap in rows],
        columns=REQUIRED_COLUMNS,
    )


CURRENT = make_universe([
    ("XOM", "Energy", 700e9),
    ("CVX", "Energy", 450e9),
    ("NEE", "Utilities", 170e9),
])


@pytest.fixture
def universe_file(tmp_path):
    path = tmp_path / "universe.csv"
    CURRENT.to_csv(path, index=False)
    return path


def test_universe_changes_lists_added_and_removed_tickers():
    candidate = make_universe([("XOM", "Energy", 1.0), ("COP", "Energy", 1.0), ("NEE", "Utilities", 1.0)])

    assert universe_changes(CURRENT, candidate) == (("COP",), ("CVX",))


def test_refresh_keeps_file_untouched_when_only_market_caps_and_order_change(universe_file):
    original = universe_file.read_bytes()
    candidate = make_universe([("CVX", "Energy", 900e9), ("XOM", "Energy", 800e9), ("NEE", "Utilities", 1e9)], TODAY)

    result = refresh_universe(universe_file, build=lambda: candidate)

    assert not result.changed
    assert result.as_of == "2026-10-25"
    assert universe_file.read_bytes() == original


def test_refresh_writes_new_universe_when_a_company_enters_the_top(universe_file):
    candidate = make_universe([("XOM", "Energy", 1.0), ("COP", "Energy", 1.0), ("NEE", "Utilities", 1.0)], TODAY)

    result = refresh_universe(universe_file, build=lambda: candidate)

    assert result.changed
    assert (result.added, result.removed) == (("COP",), ("CVX",))
    assert result.as_of == TODAY
    assert set(load_universe(universe_file)["ticker"]) == {"XOM", "COP", "NEE"}


def test_refresh_detects_a_sector_reclassification(universe_file):
    candidate = make_universe([("XOM", "Energy", 1.0), ("CVX", "Materials", 1.0), ("NEE", "Utilities", 1.0)], TODAY)

    result = refresh_universe(universe_file, build=lambda: candidate)

    assert result.changed
    assert (result.added, result.removed) == ((), ())
    assert load_universe(universe_file).set_index("ticker").at["CVX", "sector"] == "Materials"


def test_refresh_keeps_current_file_when_the_build_fails(universe_file):
    original = universe_file.read_bytes()

    def failing_build():
        raise RuntimeError("source unavailable")

    with pytest.raises(RuntimeError, match="source unavailable"):
        refresh_universe(universe_file, build=failing_build)

    assert universe_file.read_bytes() == original


def test_refresh_rejects_an_invalid_candidate_without_writing(universe_file):
    original = universe_file.read_bytes()
    candidate = pd.concat([CURRENT, CURRENT.iloc[[0]]]).assign(as_of=TODAY)

    with pytest.raises(ValueError, match="duplicate tickers"):
        refresh_universe(universe_file, build=lambda: candidate)

    assert universe_file.read_bytes() == original


def test_refresh_uses_the_live_builder_by_default(universe_file, monkeypatch):
    candidate = make_universe([("XOM", "Energy", 1.0), ("COP", "Energy", 1.0), ("NEE", "Utilities", 1.0)], TODAY)
    monkeypatch.setattr(universe_refresh, "build_universe", lambda: candidate)

    assert refresh_universe(universe_file).changed


def test_refresh_returns_the_new_universe_even_when_it_cannot_be_saved(universe_file, monkeypatch):
    original = universe_file.read_bytes()
    candidate = make_universe([("XOM", "Energy", 1.0), ("COP", "Energy", 1.0), ("NEE", "Utilities", 1.0)], TODAY)

    def read_only_save(universe, path):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(universe_refresh, "save_universe", read_only_save)

    result = refresh_universe(universe_file, build=lambda: candidate)

    assert result.changed
    assert not result.saved
    assert set(result.universe["ticker"]) == {"XOM", "COP", "NEE"}
    assert universe_file.read_bytes() == original


def test_refresh_result_carries_the_active_universe(universe_file):
    candidate = make_universe([("XOM", "Energy", 1.0), ("COP", "Energy", 1.0), ("NEE", "Utilities", 1.0)], TODAY)

    changed = refresh_universe(universe_file, build=lambda: candidate)
    unchanged = refresh_universe(universe_file, build=lambda: candidate)

    assert changed.saved
    assert set(changed.universe["ticker"]) == {"XOM", "COP", "NEE"}
    assert not unchanged.changed
    assert set(unchanged.universe["ticker"]) == {"XOM", "COP", "NEE"}
