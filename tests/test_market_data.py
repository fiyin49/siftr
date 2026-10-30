"""Deterministic provider tests. Every market observation here is SYNTHETIC."""

from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import market_data
from market_data import FetchRequest, fetch_market_data, normalize_history, parse_symbols


@pytest.fixture
def synthetic_history():
    """Invented OHLCV observations for tests only; never used by the app."""
    return pd.DataFrame(
        {
            "Open": [10.0, None, 12.0],
            "High": [12.0, 13.0, 14.0],
            "Low": [9.0, 10.0, 11.0],
            "Close": [11.0, 12.0, None],
            "Volume": [1000.0, None, 3000.0],
        },
        index=pd.DatetimeIndex(
            ["2024-01-02 23:30", "2024-01-03 23:30", "2024-01-04 23:30"],
            tz="America/New_York",
            name="Date",
        ),
    )


def test_symbols_are_normalized_without_destroying_yahoo_punctuation():
    assert parse_symbols(" aapl,MSFT,aapl, brk-b, ^gspc, btc-usd, EURUSD=X,0700.HK ") == (
        "AAPL", "MSFT", "BRK-B", "^GSPC", "BTC-USD", "EURUSD=X", "0700.HK"
    )
    with pytest.raises(ValueError):
        parse_symbols(" , , ")
    with pytest.raises(ValueError):
        parse_symbols(",".join(f"S{i}" for i in range(11)))


def test_flat_history_keeps_local_dates_and_missing_values(synthetic_history):
    result = normalize_history(
        synthetic_history, "AAPL", date(2024, 1, 2), date(2024, 1, 3)
    )
    assert list(result.columns) == [
        "date", "symbol", "open", "high", "low", "close", "volume"
    ]
    assert pd.to_datetime(result["date"]).dt.date.tolist() == [
        date(2024, 1, 2), date(2024, 1, 3)
    ]
    assert pd.to_datetime(result["date"]).dt.tz is None
    assert result["symbol"].tolist() == ["AAPL", "AAPL"]
    assert result["close"].tolist() == [11.0, 12.0]
    assert pd.isna(result.iloc[1]["open"])
    assert pd.isna(result.iloc[1]["volume"])


@pytest.mark.parametrize("ticker_first", [False, True])
def test_multiindex_history_selects_requested_symbol(synthetic_history, ticker_first):
    # Two invented symbols ensure normalization cannot accidentally select the first.
    raw = pd.concat(
        {"MSFT": synthetic_history * 10, "AAPL": synthetic_history}, axis=1
    )
    if not ticker_first:
        raw = raw.swaplevel(0, 1, axis=1)
    result = normalize_history(raw, "AAPL", date(2024, 1, 2), date(2024, 1, 4))
    assert result["symbol"].unique().tolist() == ["AAPL"]
    assert result["close"].tolist() == [11.0, 12.0]
    assert len(result) == 2  # The row with no usable close is not a market observation.


@pytest.mark.parametrize("empty_kind", ["no_rows", "missing_prices", "outside_range"])
def test_empty_and_unusable_history_stays_empty(synthetic_history, empty_kind):
    raw = synthetic_history.copy()
    if empty_kind == "no_rows":
        raw = pd.DataFrame()
    elif empty_kind == "missing_prices":
        raw["Close"] = [None, 0.0, -1.0]
    else:
        raw.index = raw.index - pd.DateOffset(years=1)
    result = normalize_history(raw, "AAPL", date(2024, 1, 2), date(2024, 1, 4))
    assert result.empty
    assert list(result.columns) == [
        "date", "symbol", "open", "high", "low", "close", "volume"
    ]


def test_partial_failure_preserves_good_data_and_explicit_request_policy(synthetic_history):
    calls = []

    def synthetic_downloader(tickers, **kwargs):
        calls.append((tickers, kwargs))
        if tickers == "BROKEN":
            raise ConnectionError("Synthetic connection failure for test only")
        if tickers == "EMPTY":
            return pd.DataFrame()
        return synthetic_history

    request = FetchRequest(
        symbols=("AAPL", "BROKEN", "EMPTY"),
        start=date(2024, 1, 2),
        end=date(2024, 1, 4),
    )
    result = fetch_market_data(request, downloader=synthetic_downloader)
    assert result.has_data
    assert result.data["symbol"].unique().tolist() == ["AAPL"]
    statuses = {item.symbol: item for item in result.statuses}
    assert statuses["AAPL"].rows == 2
    assert statuses["BROKEN"].status == "error"
    assert statuses["EMPTY"].status == "empty"
    assert statuses["BROKEN"].message
    assert statuses["EMPTY"].message
    assert result.fetched_at.tzinfo is not None
    assert len(calls) == 3
    for _, options in calls:
        assert pd.Timestamp(options["end"]).date() == request.end + timedelta(days=1)
        assert options["auto_adjust"] is True
        assert options["interval"] == "1d"
        assert options["threads"] is False


def test_failed_watchlist_returns_no_fabricated_rows():
    def empty_downloader(*args, **kwargs):
        return pd.DataFrame()

    result = fetch_market_data(
        FetchRequest(("EMPTY",), date(2024, 1, 2), date(2024, 1, 3)),
        downloader=empty_downloader,
    )
    assert not result.has_data
    assert result.data.empty
    assert result.statuses[0].status == "empty"


def test_invalid_ranges_are_rejected_and_one_day_is_supported():
    with pytest.raises(ValueError):
        FetchRequest(("AAPL",), date(2024, 1, 3), date(2024, 1, 2))
    with pytest.raises(ValueError):
        FetchRequest(("AAPL",), date(2010, 1, 1), date(2024, 1, 2))
    request = FetchRequest(("AAPL",), date(2024, 1, 2), date(2024, 1, 2))
    assert request.start == request.end


@pytest.fixture
def isolated_yahoo_cache(monkeypatch):
    """Do not alter Yahoo's real cache configuration or leave cached test state."""
    calls = []
    monkeypatch.delenv("SIFTR_CACHE_DIR", raising=False)
    monkeypatch.setattr(market_data.yf, "set_tz_cache_location", calls.append)
    market_data.configure_yfinance_cache.cache_clear()
    try:
        yield calls
    finally:
        market_data.configure_yfinance_cache.cache_clear()


@pytest.mark.parametrize(
    ("host", "course_layout"),
    [("Windows", True), ("Linux", True), ("Linux", False)],
)
def test_yahoo_cache_default_is_external_for_course_and_cloud(
    tmp_path, monkeypatch, isolated_yahoo_cache, host, course_layout
):
    source_root = tmp_path / "source"
    source_dir = source_root / "supporting" / "prototype" if course_layout else source_root
    monkeypatch.setattr(market_data, "__file__", str(source_dir / "market_data.py"))
    monkeypatch.setattr(market_data.platform, "system", lambda: host)
    monkeypatch.setattr(market_data.tempfile, "gettempdir", lambda: str(tmp_path / "temporary"))

    actual = market_data.configure_yfinance_cache()
    expected_parent = (
        tmp_path / ".siftr-runtime"
        if host == "Windows"
        else tmp_path / "temporary" / "siftr-runtime"
    )
    assert actual == expected_parent / "yfinance"
    assert actual.is_dir()
    assert not actual.is_relative_to(source_root)
    assert market_data.configure_yfinance_cache() == actual
    assert isolated_yahoo_cache == [str(actual)]


def test_yahoo_cache_accepts_external_override(tmp_path, monkeypatch, isolated_yahoo_cache):
    source_root = tmp_path / "cloud-source"
    cache_parent = tmp_path / "separate-runtime"
    monkeypatch.setattr(market_data, "__file__", str(source_root / "market_data.py"))
    monkeypatch.setenv("SIFTR_CACHE_DIR", str(cache_parent))

    actual = market_data.configure_yfinance_cache()
    assert actual == cache_parent / "yfinance"
    assert actual.is_dir()
    assert isolated_yahoo_cache == [str(actual)]


@pytest.mark.parametrize("course_layout", [True, False])
def test_yahoo_cache_rejects_override_inside_source(
    tmp_path, monkeypatch, isolated_yahoo_cache, course_layout
):
    source_root = tmp_path / "source"
    source_dir = source_root / "supporting" / "prototype" if course_layout else source_root
    monkeypatch.setattr(market_data, "__file__", str(source_dir / "market_data.py"))
    forbidden_parent = source_root / "runtime-cache"
    monkeypatch.setenv("SIFTR_CACHE_DIR", str(forbidden_parent))

    with pytest.raises(ValueError, match="outside"):
        market_data.configure_yfinance_cache()
    assert not forbidden_parent.exists()
    assert isolated_yahoo_cache == []
