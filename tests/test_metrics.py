import math

import numpy as np
import pandas as pd
import pytest

from metrics import TRADING_DAYS, align_returns, beta, correlation, information_ratio, tracking_error


@pytest.fixture
def benchmark_returns():
    rng = np.random.default_rng(seed=42)
    dates = pd.bdate_range("2024-01-01", periods=500)
    return pd.Series(rng.normal(0.0004, 0.01, len(dates)), index=dates)


def test_beta_and_correlation_of_a_leveraged_benchmark(benchmark_returns):
    stock_returns = 2 * benchmark_returns

    assert beta(stock_returns, benchmark_returns) == pytest.approx(2.0)
    assert correlation(stock_returns, benchmark_returns) == pytest.approx(1.0)


def test_tracking_error_is_annualised_std_of_active_returns(benchmark_returns):
    stock_returns = 2 * benchmark_returns

    expected = benchmark_returns.std() * math.sqrt(TRADING_DAYS)

    assert tracking_error(stock_returns, benchmark_returns) == pytest.approx(expected)


def test_information_ratio_is_annualised_active_return_over_tracking_error(benchmark_returns):
    rng = np.random.default_rng(seed=7)
    active = pd.Series(rng.normal(0.0002, 0.005, len(benchmark_returns)), index=benchmark_returns.index)
    stock_returns = benchmark_returns + active

    expected = active.mean() * TRADING_DAYS / (active.std() * math.sqrt(TRADING_DAYS))

    assert information_ratio(stock_returns, benchmark_returns) == pytest.approx(expected)


def test_information_ratio_is_nan_when_stock_replicates_benchmark(benchmark_returns):
    assert math.isnan(information_ratio(benchmark_returns, benchmark_returns))


def test_align_returns_keeps_only_common_dates_without_gaps(benchmark_returns):
    stock_returns = benchmark_returns.iloc[10:].copy()
    stock_returns.iloc[0] = np.nan

    stock, benchmark = align_returns(stock_returns, benchmark_returns)

    assert len(stock) == len(benchmark) == len(benchmark_returns) - 11
    assert stock.index.equals(benchmark.index)


def test_metrics_do_not_mutate_inputs(benchmark_returns):
    stock_returns = 2 * benchmark_returns
    snapshot = stock_returns.copy()

    tracking_error(stock_returns, benchmark_returns)

    pd.testing.assert_series_equal(stock_returns, snapshot)
