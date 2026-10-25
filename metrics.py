"""Benchmark-relative risk metrics computed from daily simple returns."""

import math

import pandas as pd

TRADING_DAYS = 252


def align_returns(stock_returns, benchmark_returns):
    """Restrict both return series to the dates where both have a value."""
    paired = pd.concat([stock_returns, benchmark_returns], axis=1, join="inner").dropna()
    return paired.iloc[:, 0], paired.iloc[:, 1]


def beta(stock_returns, benchmark_returns):
    """Sensitivity of the stock to the benchmark: cov(stock, benchmark) / var(benchmark)."""
    stock, benchmark = align_returns(stock_returns, benchmark_returns)
    return stock.cov(benchmark) / benchmark.var()


def correlation(stock_returns, benchmark_returns):
    stock, benchmark = align_returns(stock_returns, benchmark_returns)
    return stock.corr(benchmark)


def _active_returns(stock_returns, benchmark_returns):
    stock, benchmark = align_returns(stock_returns, benchmark_returns)
    return stock - benchmark


def tracking_error(stock_returns, benchmark_returns):
    """Annualised standard deviation of daily active returns (stock minus benchmark)."""
    return _active_returns(stock_returns, benchmark_returns).std() * math.sqrt(TRADING_DAYS)


def information_ratio(stock_returns, benchmark_returns):
    """Annualised mean active return divided by tracking error; NaN when tracking error is zero."""
    active = _active_returns(stock_returns, benchmark_returns)
    annual_tracking_error = active.std() * math.sqrt(TRADING_DAYS)
    if annual_tracking_error == 0:
        return math.nan
    return active.mean() * TRADING_DAYS / annual_tracking_error
