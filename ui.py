"""Streamlit interface, session state, request caching, charts, and CSV export.

Only the two explicit sidebar actions call the reusable Yahoo data layer.
Session data survives navigation; the in-memory request cache expires in 15 min.
"""

from datetime import date, datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from market_data import (
    ADJUSTMENT_POLICY, CACHE_TTL_SECONDS, DEFAULT_SYMBOLS, MAX_SYMBOLS,
    PROVIDER, FetchRequest, FetchResult, fetch_market_data, parse_symbols,
)


VIEWS = ("Market Data", "Screener", "Stock Details", "AI Report")
PRESETS = ("1 month", "3 months", "6 months", "1 year", "Year to date", "Custom")


class FetchFailed(Exception):
    """Prevent an unsuccessful attempt from entering the successful-data cache."""

    def __init__(self, result: FetchResult):
        self.result = result
        super().__init__("No usable data returned by Yahoo.")


@st.cache_data(ttl=CACHE_TTL_SECONDS, max_entries=32, show_spinner=False)
def cached_fetch(request: FetchRequest, _executed: list | None = None) -> FetchResult:
    """Cache successful snapshots; excluded probe records whether the body ran."""
    if _executed is not None:
        _executed.append(True)
    result = fetch_market_data(request)
    if not result.has_data:
        raise FetchFailed(result)
    return result


def preset_dates(preset: str, today: date) -> tuple[date, date]:
    if preset == "Year to date":
        return today.replace(month=1, day=1), today
    months = {"1 month": 1, "3 months": 3, "6 months": 6, "1 year": 12}
    return (pd.Timestamp(today) - pd.DateOffset(months=months.get(preset, 6))).date(), today


def initialize_state() -> None:
    start, end = preset_dates("6 months", date.today())
    defaults = {
        "watchlist": ", ".join(DEFAULT_SYMBOLS), "period_choice": "6 months",
        "previous_preset": "6 months", "start_date": start, "end_date": end,
        "active_result": None, "last_attempt": None, "selected_symbol": None,
        "delivery": "", "retained_after_failure": False, "input_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def retrieve(request: FetchRequest, refresh: bool) -> None:
    """Replace the active snapshot only on success; retain and label old data."""
    if refresh:
        cached_fetch.clear(request)
    executed: list[bool] = []
    try:
        result = cached_fetch(request, _executed=executed)
    except FetchFailed as error:
        st.session_state.last_attempt = error.result
        st.session_state.retained_after_failure = st.session_state.active_result is not None
        return
    st.session_state.active_result = result
    st.session_state.last_attempt = result
    st.session_state.retained_after_failure = False
    st.session_state.delivery = "Fresh Yahoo download" if executed else "Application cache"
    available = result.data["symbol"].unique().tolist()
    if st.session_state.selected_symbol not in available:
        st.session_state.selected_symbol = available[0]


def sidebar() -> tuple[str, FetchRequest | None]:
    with st.sidebar:
        st.markdown("## SIFTR")
        st.caption("Market research, with a clearer starting point.")
        view = st.radio("Workspace", VIEWS, key="view")
        st.divider()
        st.markdown("### Your watchlist")
        st.text_area("Yahoo symbols", key="watchlist", height=80,
                     help="Comma-separated. Examples are editable and are not stakeholder screening rules.")
        st.caption(f"Up to {MAX_SYMBOLS} symbols · daily history · up to 5 years")
        st.selectbox("Historical period", PRESETS, key="period_choice")
        preset = st.session_state.period_choice
        if preset != st.session_state.previous_preset:
            if preset != "Custom":
                st.session_state.start_date, st.session_state.end_date = preset_dates(preset, date.today())
            st.session_state.previous_preset = preset
        st.date_input("Start date", key="start_date", disabled=preset != "Custom")
        st.date_input("End date (inclusive)", key="end_date", disabled=preset != "Custom")
        st.caption("Both dates are included when Yahoo has trading observations. Weekends and holidays may be empty.")
        fetch = st.button("Fetch market data", type="primary", width="stretch", key="fetch")
        refresh = st.button("Refresh from Yahoo", width="stretch", key="refresh",
                            help="Bypass the matching application cache and download the displayed watchlist and period again.")
        st.caption("No automatic downloads. Successful requests are cached for 15 minutes.")
        request = None
        try:
            request = FetchRequest(parse_symbols(st.session_state.watchlist),
                                   st.session_state.start_date, st.session_state.end_date)
            if fetch or refresh:
                st.session_state.input_error = None
                with st.spinner("Retrieving daily history from Yahoo…"):
                    retrieve(request, refresh=refresh)
        except ValueError as error:
            if fetch or refresh:
                st.session_state.input_error = str(error)
        if st.session_state.input_error:
            st.error(st.session_state.input_error)
        st.divider()
        st.caption("FIRST STAGE · Research prototype")
        st.caption("Screening and AI reports are planned.")
    return view, request


def status_frame(result: FetchResult) -> pd.DataFrame:
    return pd.DataFrame([{
        "Symbol": item.symbol, "Status": item.status.title(), "Daily rows": item.rows,
        "First observation": item.first_date, "Latest observation": item.last_date,
        "Details": item.message,
    } for item in result.statuses])


def snapshot_context(result: FetchResult) -> None:
    """Label the snapshot's own request, rather than any edited pending inputs."""
    requested = result.request
    actual_start = result.data["date"].min().date()
    actual_end = result.data["date"].max().date()
    st.caption(f"SOURCE · {PROVIDER}  |  DAILY OBSERVATIONS · not real-time quotes")
    st.markdown(f"**Requested:** {requested.start.isoformat()} → {requested.end.isoformat()} (inclusive)  "
                f"\n**Available across retrieved symbols:** {actual_start.isoformat()} → {actual_end.isoformat()}")
    st.caption(f"{ADJUSTMENT_POLICY}. Prices are in each instrument's native quote units; cross-currency comparison is not supported.")
    fetched = result.fetched_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    age_minutes = max(0, int((datetime.now(timezone.utc) - result.fetched_at).total_seconds() // 60))
    delivery = st.session_state.delivery or "Retained session snapshot"
    st.caption(f"Last successful fetch: {fetched} · {delivery} · fetched {age_minutes} min ago. "
               "Fetch time is separate from the market observation dates above.")
    if age_minutes >= CACHE_TTL_SECONDS // 60:
        st.warning("This retained snapshot is older than the 15-minute application cache window. Use Refresh from Yahoo for a new attempt.")


def notices(result: FetchResult | None, pending: FetchRequest | None) -> None:
    attempt = st.session_state.last_attempt
    if attempt is not None and not attempt.has_data:
        st.error("Yahoo returned no usable data for the latest attempt. Review each symbol's status below.")
        st.caption(f"Failed attempt: {', '.join(attempt.request.symbols)} · "
                   f"{attempt.request.start} → {attempt.request.end} · "
                   f"{attempt.fetched_at:%Y-%m-%d %H:%M:%S UTC}")
        st.dataframe(status_frame(attempt), hide_index=True, width="stretch")
    if result is None:
        return
    if st.session_state.retained_after_failure:
        st.warning("STALE RETAINED DATA · The latest fetch failed. Charts, preview, and download below still use the previous successful snapshot and its original period.")
    elif pending is None or pending != result.request:
        st.info("The sidebar settings differ from the retrieved snapshot. Fetch market data to apply them; the displayed data and export still use the period shown below.")
    failed = [item.symbol for item in result.statuses if not item.rows]
    limited = [item.symbol for item in result.statuses if item.rows and item.status != "available"]
    if failed:
        st.warning(f"Partial success · No usable data for {', '.join(failed)}. Successfully retrieved symbols remain available.")
    elif not st.session_state.retained_after_failure:
        st.success(f"Daily history available for {result.data['symbol'].nunique()} symbols.")
    if limited:
        st.warning(f"Incomplete or insufficient history for {', '.join(limited)}. See the availability table. Missing values are kept blank.")


def price_volume_chart(history: pd.DataFrame, symbol: str) -> go.Figure:
    """Shared axes keep adjusted close and provider volume aligned by market day."""
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.08, row_heights=[0.74, 0.26])
    figure.add_trace(go.Scatter(
        x=history["date"], y=history["close"], mode="lines+markers" if len(history) < 3 else "lines",
        name="Adjusted close", line={"color": "#007f80", "width": 2.5},
        connectgaps=False, hovertemplate="%{x|%b %d, %Y}<br>Adjusted close: %{y:,.2f}<extra></extra>",
    ), row=1, col=1)
    figure.add_trace(go.Bar(
        x=history["date"], y=history["volume"], name="Reported volume",
        marker_color="#9bbac6", hovertemplate="%{x|%b %d, %Y}<br>Volume: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)
    figure.update_layout(height=510, template="plotly_white", showlegend=False,
                         margin={"l": 16, "r": 16, "t": 20, "b": 16}, hovermode="x unified",
                         font={"family": "Arial, sans-serif", "color": "#12263d"},
                         title={"text": f"{symbol} · daily adjusted close & volume", "font": {"size": 15}})
    figure.update_yaxes(title_text="Adjusted price (native units)", row=1, col=1, fixedrange=False)
    figure.update_yaxes(title_text="Volume", row=2, col=1, rangemode="tozero")
    figure.update_xaxes(title_text="Market date", row=2, col=1)
    return figure


def stock_inspector(result: FetchResult) -> None:
    symbols = result.data["symbol"].unique().tolist()
    chosen = st.session_state.selected_symbol
    index = symbols.index(chosen) if chosen in symbols else 0
    symbol = st.selectbox("Inspect symbol", symbols, index=index, key="chart_symbol")
    st.session_state.selected_symbol = symbol
    history = result.data.loc[result.data["symbol"] == symbol].sort_values("date")
    latest = history.iloc[-1]
    left, center, right = st.columns(3)
    left.metric("Latest adjusted close", f"{latest['close']:,.2f}")
    center.metric("Daily observations", f"{len(history):,}")
    right.metric("Latest market observation", latest["date"].date().isoformat())
    st.caption("Daily observations may be delayed or incomplete for the current trading session. Quote currency is not inferred from the symbol.")
    if len(history) < 2:
        st.info("Only one observation is available. More history is needed to inspect a trend.")
    if history["volume"].isna().any():
        st.caption("Some provider volume values are missing and are left as gaps.")
    st.plotly_chart(price_volume_chart(history, symbol), width="stretch",
                    config={"displaylogo": False}, key="price_volume")


def export_csv(result: FetchResult) -> bytes:
    """CSV includes provenance on every row and keeps absent values blank."""
    exported = result.data.copy()
    exported["date"] = exported["date"].dt.strftime("%Y-%m-%d")
    exported["provider"] = PROVIDER
    exported["adjustment_policy"] = ADJUSTMENT_POLICY
    exported["requested_start"] = result.request.start.isoformat()
    exported["requested_end_inclusive"] = result.request.end.isoformat()
    exported["fetched_at_utc"] = result.fetched_at.isoformat()
    return exported.to_csv(index=False, na_rep="").encode("utf-8")


def market_view(result: FetchResult | None) -> None:
    st.subheader("Market Data")
    st.write("Build a watchlist, retrieve daily market history, and inspect what is actually available.")
    if result is None:
        st.info("Start with AAPL, MSFT, and NVDA, or edit the symbols and period in the sidebar. Select Fetch market data to retrieve Yahoo history.")
        return
    snapshot_context(result)
    st.markdown("#### Availability by symbol")
    st.dataframe(status_frame(result), hide_index=True, width="stretch")
    st.markdown("#### Explore history")
    stock_inspector(result)
    st.markdown("#### Retrieved dataset")
    st.caption("Daily OHLC values are split- and dividend-adjusted. The preview shows up to 100 recent rows; the CSV includes every retrieved row and provenance columns.")
    preview = result.data.sort_values(["date", "symbol"], ascending=[False, True]).head(100)
    st.dataframe(preview, hide_index=True, width="stretch",
                  column_config={"date": st.column_config.DateColumn("Market date", format="YYYY-MM-DD")})
    st.download_button("Download retrieved CSV", data=export_csv(result), mime="text/csv",
                       file_name=f"siftr_adjusted_daily_{result.request.start}_{result.request.end}.csv",
                       on_click="ignore", key="download")
    st.caption(f"Download source: {PROVIDER} · requested {result.request.start} → {result.request.end} inclusive · {ADJUSTMENT_POLICY}")


def planned_view(view: str, result: FetchResult | None) -> None:
    st.subheader(view)
    st.info("Planned functionality · This view is not implemented in the first stage.")
    if view == "Screener":
        st.write("The next stage will add configurable screening rules, deterministic Python calculations, and a results table explaining each pass or failure.")
        st.caption("Kehinde Adesina's exact rules have not been supplied. The example watchlist does not reproduce his screening process.")
    else:
        st.write("A later stage will generate downloadable research summaries from selected screening results and retrieved data.")
        st.caption("No AI model is called in this prototype. Future reports will explain supplied facts; news, sentiment, and reputation claims require supporting sources.")
    if result is not None:
        st.markdown("#### Your retained market snapshot")
        snapshot_context(result)
        st.caption(f"Selected symbol: {st.session_state.selected_symbol}")


def main() -> None:
    st.set_page_config(page_title="SIFTR | Market workspace", page_icon="↗", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #f6f8fb; color: #12263d; }
        [data-testid="stSidebar"] { background-color: #edf2f7; }
        .block-container { max-width: 1400px; padding-top: 2rem; }
        h1, h2, h3 { color: #12263d; letter-spacing: -.025em; }
        [data-testid="stMetric"] { background: white; border: 1px solid #dce5ed;
            border-radius: 10px; padding: 16px; }
        [data-testid="stMetricValue"] { font-size: 1.7rem; }
        @media (max-width: 720px) { .block-container { padding: 1rem; }
            [data-testid="stMetricValue"] { font-size: 1.25rem; } }
        </style>""", unsafe_allow_html=True)
    initialize_state()
    view, pending = sidebar()
    st.title("SIFTR")
    st.caption("YOUR MARKET RESEARCH WORKSPACE · FIRST STAGE")
    result = st.session_state.active_result
    notices(result, pending)
    if view == "Market Data":
        market_view(result)
    elif view == "Stock Details":
        st.subheader("Stock Details")
        if result is None:
            st.info("Fetch daily history from the sidebar to inspect a stock's adjusted prices and volume.")
        else:
            snapshot_context(result)
            stock_inspector(result)
            st.caption("Screening metrics and explanations are planned for a later stage.")
    else:
        planned_view(view, result)
