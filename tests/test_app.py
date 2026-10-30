"""Streamlit interaction regressions using explicitly SYNTHETIC market data."""

from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
import sys

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data import ADJUSTMENT_POLICY, PROVIDER, FetchResult, SymbolStatus, empty_data
import ui


APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def clean_application_cache():
    ui.cached_fetch.clear()
    yield
    ui.cached_fetch.clear()


def synthetic_result(request, *, failed=False):
    """Invented observations test state and export behavior, never Yahoo accuracy."""
    if failed:
        return FetchResult(
            request, empty_data(),
            tuple(SymbolStatus(symbol, "error", 0, None, None,
                               "Synthetic connection failure for test only")
                  for symbol in request.symbols),
            datetime.now(timezone.utc),
        )
    dates = pd.date_range(request.start, periods=2, freq="D")
    rows = []
    statuses = []
    for symbol in request.symbols:
        rows.extend([
            {"date": dates[0], "symbol": symbol, "open": 10.0, "high": 12.0,
             "low": 9.0, "close": 11.0, "volume": float("nan")},
            {"date": dates[1], "symbol": symbol, "open": 11.0, "high": 13.0,
             "low": 10.0, "close": 12.0, "volume": 1000.0},
        ])
        statuses.append(SymbolStatus(symbol, "incomplete", 2, dates[0].date(),
                                     dates[1].date(), "Synthetic missing volume for test only"))
    return FetchResult(request, pd.DataFrame(rows), tuple(statuses), datetime.now(timezone.utc))


def assert_no_app_errors(app):
    assert not app.exception, [error.message for error in app.exception]


def test_explicit_fetch_export_and_navigation_preserve_snapshot(monkeypatch):
    calls = []

    def fake_fetch(request):
        calls.append(request)
        return synthetic_result(request)

    monkeypatch.setattr(ui, "fetch_market_data", fake_fetch)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert_no_app_errors(app)
    assert calls == []
    assert app.session_state["active_result"] is None

    watchlist = " aapl, msft, aapl "
    app.text_area(key="watchlist").set_value(watchlist).run()
    assert calls == []
    app.button(key="fetch").click().run()
    assert_no_app_errors(app)
    assert len(calls) == 1
    assert calls[0].symbols == ("AAPL", "MSFT")
    snapshot = app.session_state["active_result"]
    assert app.get("download_button")
    assert app.get("plotly_chart")

    exported = pd.read_csv(StringIO(ui.export_csv(snapshot).decode("utf-8")))
    assert exported["symbol"].tolist() == ["AAPL", "AAPL", "MSFT", "MSFT"]
    assert exported["date"].tolist() == snapshot.data["date"].dt.strftime("%Y-%m-%d").tolist()
    assert exported["provider"].eq(PROVIDER).all()
    assert exported["adjustment_policy"].eq(ADJUSTMENT_POLICY).all()
    assert exported["requested_start"].eq(snapshot.request.start.isoformat()).all()
    assert exported["requested_end_inclusive"].eq(snapshot.request.end.isoformat()).all()
    assert exported["volume"].isna().sum() == 2
    assert exported["fetched_at_utc"].str.endswith("+00:00").all()

    app.selectbox(key="chart_symbol").select("MSFT").run()
    for view in ("Screener", "Stock Details", "AI Report", "Market Data"):
        app.radio(key="view").set_value(view).run()
        assert_no_app_errors(app)
        retained = app.session_state["active_result"]
        assert retained.request == snapshot.request
        assert retained.data.equals(snapshot.data)
        assert app.session_state["selected_symbol"] == "MSFT"
        assert app.session_state["watchlist"] == watchlist
        assert len(calls) == 1
        if view in ("Screener", "AI Report"):
            assert any("Planned functionality" in message.value for message in app.info)
    assert app.selectbox(key="chart_symbol").value == "MSFT"


def test_matching_cache_refresh_and_failed_refresh_retention(monkeypatch):
    calls = []
    fail_next = [False]

    def fake_fetch(request):
        calls.append(request)
        return synthetic_result(request, failed=fail_next[0])

    monkeypatch.setattr(ui, "fetch_market_data", fake_fetch)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.button(key="fetch").click().run()
    assert_no_app_errors(app)
    snapshot = app.session_state["active_result"]
    assert len(calls) == 1
    app.button(key="fetch").click().run()
    assert_no_app_errors(app)
    assert len(calls) == 1
    assert app.session_state["delivery"] == "Application cache"

    app.button(key="refresh").click().run()
    assert_no_app_errors(app)
    assert len(calls) == 2
    assert app.session_state["delivery"] == "Fresh Yahoo download"
    snapshot = app.session_state["active_result"]

    fail_next[0] = True
    app.button(key="refresh").click().run()
    assert_no_app_errors(app)
    assert len(calls) == 3
    assert app.session_state["retained_after_failure"] is True
    assert app.session_state["active_result"].data.equals(snapshot.data)
    assert app.session_state["active_result"].fetched_at == snapshot.fetched_at
    assert any("STALE RETAINED DATA" in message.value for message in app.warning)
    assert any("no usable data" in message.value for message in app.error)
    assert app.get("download_button")

    # A failed attempt must not replace the successful-data cache with an empty result.
    fail_next[0] = False
    app.button(key="fetch").click().run()
    assert_no_app_errors(app)
    assert len(calls) == 4
    assert app.session_state["retained_after_failure"] is False


def test_reversed_custom_dates_are_rejected_before_provider_call(monkeypatch):
    calls = []

    def fake_fetch(request):
        calls.append(request)
        return synthetic_result(request)

    monkeypatch.setattr(ui, "fetch_market_data", fake_fetch)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.selectbox(key="period_choice").select("Custom").run()
    app.date_input(key="start_date").set_value(date(2024, 1, 3))
    app.date_input(key="end_date").set_value(date(2024, 1, 2))
    app.button(key="fetch").click().run()
    assert_no_app_errors(app)
    assert calls == []
    assert app.session_state["active_result"] is None
    assert any("Start date must be on or before end date" in message.value for message in app.error)
