import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date

from metrics import beta, correlation, information_ratio, tracking_error
from stock_universe import load_universe, stocks_in_sector
from universe_refresh import refresh_universe

DEFAULT_TICKER = "NVDA"
BENCHMARK = "^SP500TR"
BENCHMARK_NAME = "S&P 500 Total Return"
CACHE_TTL_SECONDS = 3600
# Network failures (requests errors are OSError subclasses), source layout changes and invalid data.
REFRESH_ERRORS = (OSError, RuntimeError, ValueError)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_prices(ticker, start, end):
    prices = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(prices.columns, pd.MultiIndex):
        return prices.droplevel(1, axis=1)
    return prices


st.set_page_config(page_title="Stock Analytics", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>

.stApp {
    background-color: #0B0B0B;
    color: white;
}

.block-container {
    padding-top: 45px;
    padding-bottom: 15px;
    padding-left: 35px;
    padding-right: 35px;
    max-width: 1600px;
}

[data-testid="stSidebar"] {
    background-color: #111111;
    border-right: 1px solid #292929;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #171717, #121212);
    border: 1px solid #2A2A2A;
    padding: 13px 18px;
    border-radius: 12px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.20);
}

[data-testid="stMetricLabel"] {
    color: #A5A5A5 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
}

[data-testid="stMetricValue"] {
    color: #76B900 !important;
    font-size: 28px !important;
    font-weight: 650 !important;
}

[data-testid="stPlotlyChart"] {
    background-color: #151515;
    border: 1px solid #292929;
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="column"] {
    padding-top: 4px;
}

</style>
""", unsafe_allow_html=True)

try:
    # An update that could not be saved (e.g. read-only hosting) still applies to the visitor's session.
    universe = st.session_state.get("unsaved_universe")
    if universe is None:
        universe = load_universe()
except (OSError, ValueError) as error:
    st.error(f"Could not load the stock universe ({error}). Run `python scripts/build_universe.py` to rebuild it.")
    st.stop()

companies = universe.set_index("ticker")
sectors = sorted(universe["sector"].unique())


def select_sector_leader():
    st.session_state["ticker"] = stocks_in_sector(universe, st.session_state["sector"])["ticker"].iloc[0]


def stock_label(symbol):
    label = f"{companies.at[symbol, 'name']} ({symbol})"
    return label if companies.at[symbol, "in_sp500"] else f"{label} · not in S&P 500"


def refresh_message(result):
    if not result.changed:
        return "info", (f"Checked on {date.today():%Y-%m-%d}: the top 5 per sector has not changed. "
                        f"Universe dated {result.as_of} kept.")
    if result.added or result.removed:
        summary = (f"Universe updated on {result.as_of}. "
                   f"Added: {', '.join(result.added) or 'none'}. Removed: {', '.join(result.removed) or 'none'}.")
    else:
        summary = f"Universe updated on {result.as_of}: sector classification changed."
    if not result.saved:
        return "warning", f"{summary} Shown for this session only: the update could not be saved on this server."
    return "success", summary


def refresh_universe_data():
    try:
        with st.spinner("Downloading S&P 500 constituents and market caps…"):
            result = refresh_universe()
    except REFRESH_ERRORS as error:
        st.session_state["refresh_feedback"] = ("error", f"Update failed, the current universe was kept: {error}")
        return

    st.session_state["refresh_feedback"] = refresh_message(result)
    if result.changed and not result.saved:
        st.session_state["unsaved_universe"] = result.universe
    else:
        st.session_state.pop("unsaved_universe", None)

    sector_stocks_after = stocks_in_sector(result.universe, st.session_state["sector"])["ticker"]
    if st.session_state.get("ticker") not in set(sector_stocks_after):
        st.session_state["ticker"] = sector_stocks_after.iloc[0]


header = st.empty()

_, sector_picker, stock_picker, refresh_column = st.columns([1, 1, 1, 1], vertical_alignment="bottom")
sector = sector_picker.selectbox(
    "Sector",
    options=sectors,
    index=sectors.index(companies.at[DEFAULT_TICKER, "sector"]),
    key="sector",
    on_change=select_sector_leader,
)
sector_stocks = stocks_in_sector(universe, sector)["ticker"].tolist()
ticker = stock_picker.selectbox(
    "Stock (compared with the S&P 500)",
    options=sector_stocks,
    index=sector_stocks.index(DEFAULT_TICKER) if DEFAULT_TICKER in sector_stocks else 0,
    format_func=stock_label,
    key="ticker",
)
company = companies.at[ticker, "name"]
universe_date = universe["as_of"].iloc[0]

refresh_column.button(
    "Update S&P 500 data",
    key="refresh_universe",
    on_click=refresh_universe_data,
    help="Recompute the 5 largest companies of each sector from today's S&P 500 data. "
         "The list changes only if a company entered or left the top 5.",
)

st.markdown(f"""
<div style="text-align:center; font-size:12px; color:#8A8A8A; margin:2px 0 14px;">
    Universe: 5 largest S&P 500 companies per GICS sector by market cap · as of {universe_date}
</div>
""", unsafe_allow_html=True)

feedback = st.session_state.pop("refresh_feedback", None)
if feedback is not None:
    level, message = feedback
    {"info": st.info, "success": st.success, "warning": st.warning, "error": st.error}[level](message)

start_date = st.sidebar.date_input("Start date", pd.to_datetime("2021-01-01"))
end_date = st.sidebar.date_input("End date", date.today())

ma50 = st.sidebar.checkbox("50-day moving average", True)
ma200 = st.sidebar.checkbox("200-day moving average", True)

header.markdown(f"""
<div style="text-align:center; margin-bottom:22px;">
    <div style="font-size:34px; line-height:1.25; font-weight:700; color:#FFFFFF; letter-spacing:-0.8px;">
        {company} Analytics
    </div>
    <div style="font-size:14px; color:#A0A0A0; margin-top:7px;">
        Market Performance Dashboard · {ticker} · {sector}
    </div>
    <div style="font-size:12px; font-weight:600; color:#76B900; margin-top:5px;">
        {start_date:%B %Y} — Present
    </div>
</div>
""", unsafe_allow_html=True)

stock = load_prices(ticker, start_date, end_date)
sp500 = load_prices(BENCHMARK, start_date, end_date)

if stock.empty:
    st.warning(f"No data available for {company} ({ticker}) in this date range.")
    st.stop()

stock["Return"] = stock["Close"].pct_change()
stock["MA50"] = stock["Close"].rolling(50).mean()
stock["MA200"] = stock["Close"].rolling(200).mean()

current_price = stock["Close"].iloc[-1]
start_price = stock["Close"].iloc[0]

total_return = (current_price / start_price - 1) * 100
volatility = stock["Return"].std() * np.sqrt(252) * 100
annual_return = ((1 + stock["Return"].mean()) ** 252 - 1) * 100
sharpe = (annual_return / 100 - 0.04) / (volatility / 100)

rolling_max = stock["Close"].cummax()
drawdown = stock["Close"] / rolling_max - 1
max_drawdown = drawdown.min() * 100

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Current Price", f"${current_price:.2f}")
col2.metric("Period Return", f"{total_return:.1f}%")
col3.metric("Annual Volatility", f"{volatility:.1f}%")
col4.metric("Sharpe Ratio", f"{sharpe:.2f}")
col5.metric("Max Drawdown", f"{max_drawdown:.1f}%")

benchmark_returns = sp500["Close"].pct_change()

rel1, rel2, rel3, rel4 = st.columns(4)

rel1.metric("Beta", f"{beta(stock['Return'], benchmark_returns):.2f}",
            help=f"Sensitivity of daily returns to the {BENCHMARK_NAME}")
rel2.metric("Correlation", f"{correlation(stock['Return'], benchmark_returns):.2f}",
            help=f"Correlation of daily returns with the {BENCHMARK_NAME}")
rel3.metric("Tracking Error", f"{tracking_error(stock['Return'], benchmark_returns) * 100:.1f}%",
            help="Annualised volatility of daily returns in excess of the benchmark")
rel4.metric("Information Ratio", f"{information_ratio(stock['Return'], benchmark_returns):.2f}",
            help="Annualised excess return over the benchmark divided by tracking error")

left, right = st.columns(2, gap="medium")

with left:

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=stock.index,
        y=stock["Close"],
        name=ticker,
        line=dict(color="#76B900", width=2.3)
    ))

    if ma50:
        fig.add_trace(go.Scatter(
            x=stock.index,
            y=stock["MA50"],
            name="50-day MA",
            line=dict(color="#FFFFFF", width=1.3)
        ))

    if ma200:
        fig.add_trace(go.Scatter(
            x=stock.index,
            y=stock["MA200"],
            name="200-day MA",
            line=dict(color="#666666", width=1.3)
        ))

    fig.update_layout(
        title=dict(text="Stock Performance", font=dict(size=17, color="#FFFFFF"), x=0.04),
        template="plotly_dark",
        paper_bgcolor="#151515",
        plot_bgcolor="#151515",
        height=300,
        margin=dict(l=50, r=20, t=55, b=40),
        font=dict(size=12, color="#B5B5B5"),
        yaxis_title="Price ($)",
        legend=dict(orientation="h", y=-0.17, x=0.02, font=dict(size=11))
    )

    fig.update_xaxes(gridcolor="#252525", tickfont=dict(size=11))
    fig.update_yaxes(gridcolor="#252525", tickfont=dict(size=11), title_font=dict(size=12))

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with right:

    comparison = pd.DataFrame()
    comparison[ticker] = stock["Close"] / stock["Close"].iloc[0] * 100
    comparison[BENCHMARK_NAME] = sp500["Close"] / sp500["Close"].iloc[0] * 100
    comparison = comparison.dropna()

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        x=comparison.index,
        y=comparison[ticker],
        name=ticker,
        line=dict(color="#76B900", width=2.3)
    ))

    fig2.add_trace(go.Scatter(
        x=comparison.index,
        y=comparison[BENCHMARK_NAME],
        name=BENCHMARK_NAME,
        line=dict(color="#C0C0C0", width=1.5)
    ))

    fig2.update_layout(
        title=dict(
            text=f"Performance vs {BENCHMARK_NAME}<br><sup>Growth of $100 invested, dividends reinvested</sup>",
            font=dict(size=17, color="#FFFFFF"),
            x=0.04
        ),
        template="plotly_dark",
        paper_bgcolor="#151515",
        plot_bgcolor="#151515",
        height=300,
        margin=dict(l=55, r=20, t=55, b=40),
        font=dict(size=12, color="#B5B5B5"),
        yaxis_title="Value ($)",
        legend=dict(orientation="h", y=-0.17, x=0.02, font=dict(size=11))
    )

    fig2.update_xaxes(gridcolor="#252525", tickfont=dict(size=11))
    fig2.update_yaxes(gridcolor="#252525", tickfont=dict(size=11), title_font=dict(size=12))

    st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})

bottom1, bottom2, bottom3 = st.columns(3, gap="medium")

monthly_returns = stock["Close"].resample("ME").last().pct_change() * 100

monthly = pd.DataFrame()
monthly["Date"] = monthly_returns.index
monthly["Return"] = monthly_returns.values
monthly = monthly.dropna()

colors = []

for value in monthly["Return"]:
    if value >= 0:
        colors.append("#76B900")
    else:
        colors.append("#666666")

with bottom1:

    fig3 = go.Figure()

    fig3.add_trace(go.Bar(
        x=monthly["Date"],
        y=monthly["Return"],
        marker_color=colors
    ))

    fig3.update_layout(
        title=dict(text="Monthly Returns", font=dict(size=16, color="#FFFFFF"), x=0.05),
        template="plotly_dark",
        paper_bgcolor="#151515",
        plot_bgcolor="#151515",
        height=245,
        margin=dict(l=45, r=15, t=50, b=35),
        font=dict(size=11, color="#B5B5B5"),
        yaxis_title="Return (%)",
        showlegend=False
    )

    fig3.update_xaxes(gridcolor="#252525", tickfont=dict(size=10))
    fig3.update_yaxes(gridcolor="#252525", tickfont=dict(size=10))

    st.plotly_chart(fig3, width="stretch", config={"displayModeBar": False})

with bottom2:

    returns = stock["Return"].dropna() * 100

    fig4 = go.Figure()

    fig4.add_trace(go.Histogram(
        x=returns,
        nbinsx=45,
        marker_color="#76B900"
    ))

    fig4.update_layout(
        title=dict(
            text="Daily Return Distribution<br><sup>Frequency of daily price changes</sup>",
            font=dict(size=16, color="#FFFFFF"),
            x=0.05
        ),
        template="plotly_dark",
        paper_bgcolor="#151515",
        plot_bgcolor="#151515",
        height=245,
        margin=dict(l=45, r=15, t=50, b=35),
        font=dict(size=11, color="#B5B5B5"),
        xaxis_title="Daily Return (%)",
        showlegend=False
    )

    fig4.update_xaxes(gridcolor="#252525", tickfont=dict(size=10))
    fig4.update_yaxes(gridcolor="#252525", tickfont=dict(size=10))

    st.plotly_chart(fig4, width="stretch", config={"displayModeBar": False})

with bottom3:

    drawdown_data = pd.DataFrame()
    drawdown_data["Date"] = stock.index
    drawdown_data["Drawdown"] = drawdown.values * 100

    fig5 = go.Figure()

    fig5.add_trace(go.Scatter(
        x=drawdown_data["Date"],
        y=drawdown_data["Drawdown"],
        line=dict(color="#76B900", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(118,185,0,0.18)"
    ))

    fig5.update_layout(
        title=dict(
            text="Drawdown<br><sup>Decline from previous market peak</sup>",
            font=dict(size=16, color="#FFFFFF"),
            x=0.05
        ),
        template="plotly_dark",
        paper_bgcolor="#151515",
        plot_bgcolor="#151515",
        height=245,
        margin=dict(l=45, r=15, t=50, b=35),
        font=dict(size=11, color="#B5B5B5"),
        yaxis_title="Drawdown (%)",
        showlegend=False
    )

    fig5.update_xaxes(gridcolor="#252525", tickfont=dict(size=10))
    fig5.update_yaxes(gridcolor="#252525", tickfont=dict(size=10))

    st.plotly_chart(fig5, width="stretch", config={"displayModeBar": False})