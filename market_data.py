"""Reusable daily Yahoo data access; no Streamlit, screening, or AI dependencies.

Dates in this module are exchange-local calendar dates. ``FetchRequest.end`` is
inclusive; the provider's exclusive end is advanced by one day. Prices use
``auto_adjust=True`` throughout, while volume is the provider-reported value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import logging
import os
from pathlib import Path
import platform
import tempfile
import threading
from typing import Callable

import pandas as pd
import yfinance as yf


DEFAULT_SYMBOLS = ("AAPL", "MSFT", "NVDA")
MAX_SYMBOLS = 10
CACHE_TTL_SECONDS = 15 * 60
PROVIDER = "Yahoo Finance via yfinance"
ADJUSTMENT_POLICY = (
    "Split- and dividend-adjusted OHLC (auto_adjust=True); provider-reported volume"
)
DATA_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume")
NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")


def parse_symbols(text: str) -> tuple[str, ...]:
    """Normalize a comma-separated watchlist without stripping symbol punctuation.

    Validation intentionally avoids an equities-only symbol grammar: Yahoo also
    uses punctuation in index, currency, class-share, and exchange-qualified IDs.
    The provider determines whether a syntactically accepted symbol exists.
    """
    symbols = tuple(dict.fromkeys(part.strip().upper() for part in text.split(",") if part.strip()))
    if not symbols:
        raise ValueError("Enter at least one comma-separated Yahoo symbol.")
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"Use at most {MAX_SYMBOLS} unique symbols per request.")
    for symbol in symbols:
        if len(symbol) > 32 or any(character.isspace() or ord(character) < 32 for character in symbol):
            raise ValueError(f"Check symbol {symbol!r}: use a Yahoo symbol without embedded whitespace (32 characters maximum).")
    return symbols


@dataclass(frozen=True)
class FetchRequest:
    """A bounded daily request, with both start and end included."""

    symbols: tuple[str, ...]
    start: date
    end: date

    def __post_init__(self) -> None:
        if not isinstance(self.start, date) or not isinstance(self.end, date):
            raise ValueError("Choose a start date and an end date.")
        if isinstance(self.start, datetime) or isinstance(self.end, datetime):
            raise ValueError("Use calendar dates rather than timestamps for daily history.")
        if self.start > self.end:
            raise ValueError("Start date must be on or before end date.")
        if self.end > date.today():
            raise ValueError("End date cannot be in the future.")
        if self.end - self.start > timedelta(days=5 * 366):
            raise ValueError("Choose a period of no more than five years for this prototype.")
        object.__setattr__(self, "symbols", parse_symbols(",".join(self.symbols)))


@dataclass(frozen=True)
class SymbolStatus:
    """Availability of one requested symbol, including its actual date coverage."""

    symbol: str
    status: str
    rows: int
    first_date: date | None
    last_date: date | None
    message: str


@dataclass
class FetchResult:
    """A completed attempt; callers retain prior successful data if this is empty.

    ``fetched_at`` records the attempt's completion in UTC, never a quote time.
    Only callers with ``has_data`` should label it a successful fetch time.
    """

    request: FetchRequest
    data: pd.DataFrame
    statuses: tuple[SymbolStatus, ...]
    fetched_at: datetime

    @property
    def has_data(self) -> bool:
        return not self.data.empty


def empty_data() -> pd.DataFrame:
    """Return the stable long-format schema, including when Yahoo returns nothing."""
    return pd.DataFrame({
        "date": pd.Series(dtype="datetime64[ns]"),
        "symbol": pd.Series(dtype="str"),
        **{column: pd.Series(dtype="float64") for column in NUMERIC_COLUMNS},
    })


def _daily_dates(values: object) -> pd.DatetimeIndex:
    """Remove timezone without shifting local market dates to another timezone."""
    dates: list[pd.Timestamp] = []
    for value in values:
        if isinstance(value, (int, float)):
            dates.append(pd.NaT)
            continue
        try:
            timestamp = pd.Timestamp(value)
            if pd.isna(timestamp):
                dates.append(pd.NaT)
            else:
                dates.append(timestamp.tz_localize(None).normalize())
        except (ValueError, TypeError, OverflowError):
            dates.append(pd.NaT)
    return pd.DatetimeIndex(dates)


def normalize_history(raw: pd.DataFrame, symbol: str, start: date, end: date) -> pd.DataFrame:
    """Convert flat or either MultiIndex orientation into one symbol's OHLCV.

    Missing and nonfinite numeric values stay missing. Nonpositive prices are
    unusable; rows without a positive close are removed. Zero volume is retained
    only when actually supplied by Yahoo. Duplicate daily observations keep the
    last provider row. The input frame is never modified.
    """
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty_data()

    symbol = symbol.strip().upper()
    selected: dict[str, object] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        # Identify the field axis first: real tickers such as LOW and OPEN can
        # themselves match OHLCV labels, so scanning every tuple part is unsafe.
        field_level = max(
            range(raw.columns.nlevels),
            key=lambda level: len({str(value).strip().lower() for value in raw.columns.get_level_values(level)} & set(NUMERIC_COLUMNS)),
        )
        for column in raw.columns:
            parts = [str(part).strip() for part in column]
            if symbol not in (part.upper() for level, part in enumerate(parts) if level != field_level):
                continue
            field = parts[field_level].lower()
            if field in NUMERIC_COLUMNS:
                selected.setdefault(field, column)
    else:
        for column in raw.columns:
            label = str(column).strip().lower()
            if label in NUMERIC_COLUMNS or label in ("date", "datetime"):
                selected.setdefault(label, column)

    if "close" not in selected:
        return empty_data()

    date_column = selected.get("date", selected.get("datetime"))
    dates = _daily_dates(raw[date_column] if date_column is not None else raw.index)
    result = empty_data().reindex(range(len(raw)))
    result["date"] = dates
    result["symbol"] = symbol
    for field in NUMERIC_COLUMNS:
        if field in selected:
            series = raw[selected[field]]
            # Repeated provider column labels are ambiguous; use the last copy.
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, -1]
            result[field] = pd.to_numeric(series, errors="coerce").to_numpy(dtype="float64", na_value=float("nan"))
            result[field] = result[field].replace([float("inf"), float("-inf")], float("nan"))
        if field == "volume":
            result.loc[result[field] < 0, field] = float("nan")
        else:
            result.loc[result[field] <= 0, field] = float("nan")

    usable = (
        result["date"].notna()
        & result["date"].between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
        & result["close"].notna()
    )
    return (
        result.loc[usable, list(DATA_COLUMNS)]
        .sort_values("date", kind="stable")
        .drop_duplicates(subset=["date", "symbol"], keep="last")
        .reset_index(drop=True)
    )


@lru_cache(maxsize=1)
def configure_yfinance_cache() -> Path:
    """Keep Yahoo's timezone/cookie SQLite caches outside application source.

    Windows defaults to a sibling ``.siftr-runtime/yfinance`` directory beside
    the course workspace or standalone application. Other hosts, including
    Streamlit Community Cloud, use ``<system temporary directory>/siftr-runtime/
    yfinance`` so the repository's parent need not be writable. Set
    ``SIFTR_CACHE_DIR`` to an alternative cache parent outside the source tree.
    Application data caching is handled separately by the interface.
    """
    source = Path(__file__).resolve()
    course_layout = source.parent.name == "prototype" and source.parent.parent.name == "supporting"
    source_root = source.parents[2] if course_layout else source.parent
    default_parent = (
        source_root.parent / ".siftr-runtime"
        if platform.system() == "Windows"
        else Path(tempfile.gettempdir()) / "siftr-runtime"
    )
    cache_parent = Path(os.environ.get("SIFTR_CACHE_DIR") or default_parent).expanduser().resolve()
    if cache_parent.is_relative_to(source_root):
        raise ValueError("SIFTR_CACHE_DIR must be outside the application or course submission folder.")
    cache_dir = cache_parent / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache_dir))
    return cache_dir


class _ProviderMessages(logging.Handler):
    """Capture only this request thread's errors: download often logs, then returns empty."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.thread_id = threading.get_ident()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread == self.thread_id:
            self.messages.append(record.getMessage())


def _failure_message(detail: str) -> tuple[str, str]:
    detail = detail.lower()
    if any(term in detail for term in ("rate limit", "ratelimit", "too many requests", "429", "throttl")):
        return "error", "Yahoo throttled this request. Wait several minutes before trying Refresh again."
    if any(term in detail for term in ("timed out", "timeout", "connection", "curl:", "resolve", "ssl", "network")):
        return "error", "Could not connect to Yahoo or the request timed out. Check network access, then retry."
    return "empty", (
        "Yahoo returned no usable daily prices. Check the symbol and period; the symbol may be unsupported, "
        "delisted, or have no trading observations in this range. Yahoo may also be temporarily unavailable."
    )


def fetch_market_data(request: FetchRequest, downloader: Callable | None = None) -> FetchResult:
    """Fetch symbols separately so a provider failure never discards other symbols.

    ``downloader`` is an explicit dependency injection boundary for deterministic
    tests; production always uses actual ``yf.download`` output. Requests have a
    10-second provider timeout, no provider threads, and no automatic retries.
    """
    frames: list[pd.DataFrame] = []
    statuses: list[SymbolStatus] = []
    logger = logging.getLogger("yfinance")
    default_downloader = downloader is None
    download = yf.download if default_downloader else downloader

    for symbol in request.symbols:
        messages = _ProviderMessages()
        logger.addHandler(messages)
        try:
            if default_downloader:
                configure_yfinance_cache()
            raw = download(
                tickers=symbol,
                start=request.start,
                end=request.end + timedelta(days=1),
                interval="1d",
                auto_adjust=True,
                actions=False,
                threads=False,
                progress=False,
                timeout=10,
                keepna=True,
                multi_level_index=True,
            )
            normalized = normalize_history(raw, symbol, request.start, request.end)
            if normalized.empty:
                status, message = _failure_message(" ".join(messages.messages))
                statuses.append(SymbolStatus(symbol, status, 0, None, None, message))
                continue

            frames.append(normalized)
            rows = len(normalized)
            incomplete = normalized[list(NUMERIC_COLUMNS)].isna().any().any()
            removed = isinstance(raw, pd.DataFrame) and len(raw) > rows
            if rows < 2:
                status = "insufficient"
                message = "Only one usable daily observation; insufficient history for trends or future screening."
                if incomplete:
                    message += " Some OHLCV fields are missing."
            elif incomplete or removed:
                status = "incomplete"
                message = "Usable prices retrieved; some fields or provider rows were missing, invalid, duplicated, or outside the requested range. Missing values remain blank."
            else:
                status = "available"
                message = "Daily adjusted prices retrieved. Actual coverage may differ from the requested calendar dates."
            statuses.append(SymbolStatus(
                symbol, status, rows,
                normalized["date"].iloc[0].date(),
                normalized["date"].iloc[-1].date(),
                message,
            ))
        except Exception as error:
            status, message = _failure_message(f"{type(error).__name__}: {error}")
            if status == "empty":
                status = "error"
                message = "Yahoo data retrieval or normalization failed. Check the symbol, connectivity, and provider availability, then retry."
            statuses.append(SymbolStatus(symbol, status, 0, None, None, message))
        finally:
            logger.removeHandler(messages)

    data = pd.concat(frames, ignore_index=True) if frames else empty_data()
    return FetchResult(request, data, tuple(statuses), datetime.now(timezone.utc))
