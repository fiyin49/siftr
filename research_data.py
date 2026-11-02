"""Bounded Yahoo company/news evidence, without article scraping or AI calls.

Yahoo's latest-news feed is not a date-search archive. A successful response is
still a limited sample, and Yahoo's ticker association does not prove relevance.
Provider text is untrusted source material, never executable instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from html import unescape
import logging
import re
from typing import Callable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import yfinance as yf

from market_data import _ProviderMessages, configure_yfinance_cache, parse_symbols


MAX_NEWS_REQUEST = 20
MAX_ARTICLES = 5
MAX_NEWS_DAYS = 30
MAX_DESCRIPTION_CHARS = 4_000
MAX_FULL_TEXT_CHARS = 8_000
NEWS_COVERAGE_NOTE = (
    "Yahoo supplies only its latest 20 ticker-associated news items, not an archive or complete coverage "
    "of the selected dates. Up to 5 dated, deduplicated articles are retained. Syndicated items may "
    "mention multiple companies; ticker association does not establish relevance. No article links were opened or scraped."
)


@dataclass(frozen=True)
class CompanyInfo:
    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    business_description: str | None = None
    website: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class NewsArticle:
    source_id: str
    headline: str
    publisher: str | None
    published_at: datetime
    url: str
    text: str | None
    evidence_type: str


@dataclass(frozen=True)
class CompanyEvidence:
    company: CompanyInfo
    articles: tuple[NewsArticle, ...]
    info_status: str
    news_status: str
    messages: tuple[str, ...]
    retrieved_at: datetime


def _utc_now(now: datetime | None) -> datetime:
    instant = datetime.now(timezone.utc) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Research retrieval time must include a timezone.")
    return instant.astimezone(timezone.utc)


def _validate_window(start: date, end: date, now: datetime) -> None:
    if (
        not isinstance(start, date) or not isinstance(end, date)
        or isinstance(start, datetime) or isinstance(end, datetime)
    ):
        raise ValueError("Choose calendar dates for the research window.")
    if start > end:
        raise ValueError("Research start date must be on or before its end date.")
    if (end - start).days >= MAX_NEWS_DAYS:
        raise ValueError(f"Choose no more than {MAX_NEWS_DAYS} inclusive days for news research.")
    if end > now.date():
        raise ValueError("Research end date cannot be after today's UTC date.")


def _plain(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", unescape(value))).strip()
    return text if text and text.lower() not in {"n/a", "none", "null", "nan"} else None


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    if any(character.isspace() or ord(character) < 32 for character in url):
        return None
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
        ):
            return None
        parsed.port  # Validate malformed ports before creating a clickable source.
    except ValueError:
        return None
    return url


def _profile_url(symbol: str) -> str:
    return f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/profile/"


def normalize_company_info(symbol: str, payload: object) -> tuple[CompanyInfo, tuple[str, ...]]:
    """Keep only supplied profile fields; never infer company facts from a ticker."""
    symbols = parse_symbols(symbol)
    if len(symbols) != 1:
        raise ValueError("Company research requires exactly one symbol per retrieval.")
    symbol = symbols[0]
    if not isinstance(payload, dict):
        raise ValueError("Yahoo company profile response was not an object.")
    messages: list[str] = []
    description = _plain(payload.get("longBusinessSummary"))
    if description and len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS]
        messages.append(f"Company business description was truncated to {MAX_DESCRIPTION_CHARS} characters.")
    website = _safe_url(payload.get("website"))
    if payload.get("website") and website is None:
        messages.append("Yahoo supplied an invalid company website URL; it was excluded.")
    company = CompanyInfo(
        symbol=symbol,
        name=_plain(payload.get("longName")) or _plain(payload.get("shortName")),
        sector=_plain(payload.get("sector")),
        industry=_plain(payload.get("industry")),
        business_description=description,
        website=website,
        source_url=_profile_url(symbol),
    )
    missing = [
        label for label, value in (
            ("company name", company.name), ("sector", company.sector),
            ("industry", company.industry), ("business description", company.business_description),
            ("website", company.website),
        ) if value is None
    ]
    if missing:
        messages.append("Yahoo company profile did not supply usable " + ", ".join(missing) + ".")
    return company, tuple(messages)


def _publication_time(value: object) -> datetime | None:
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        else:
            return None
        # An undated/zone-less provider time cannot establish a UTC publication day.
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _url_value(value: object) -> object:
    return value.get("url") if isinstance(value, dict) else value


def _identity_url(url: str) -> str:
    """Drop known tracking parameters for deduplication, retaining article identity."""
    parsed = urlsplit(url)
    tracking = {"guccounter", "guce_referrer", "guce_referrer_sig", "ncid", "soc_src", "soc_trk", "fbclid", "gclid"}
    query = [
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking
    ]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(sorted(query)), ""))


def normalize_news(
    payload: object, start: date, end: date, *, now: datetime | None = None
) -> tuple[tuple[NewsArticle, ...], tuple[str, ...]]:
    """Normalize modern ``content`` and legacy Yahoo items into bounded evidence.

    The returned source IDs are assigned after date filtering and deduplication.
    Source links retain the original validated canonical URL when provided.
    Only explicit ``fullText``/``full_text`` fields count as full article text;
    summaries and descriptions never imply the underlying article was read.
    """
    instant = _utc_now(now)
    _validate_window(start, end, instant)
    if not isinstance(payload, list):
        raise ValueError("Yahoo news response was not an article list.")
    messages: list[str] = [NEWS_COVERAGE_NOTE]
    if not payload:
        return (), tuple(messages + ["Yahoo returned an empty latest-news list. This does not establish that no company events occurred."])

    lower = datetime.combine(start, time.min, timezone.utc)
    upper = datetime.combine(end + timedelta(days=1), time.min, timezone.utc)
    exclusions = {"malformed": 0, "undated": 0, "outside_window": 0, "future": 0, "invalid_url": 0, "missing_headline": 0, "advertisement": 0}
    candidates: list[tuple[NewsArticle, str | None, bool]] = []
    for item in payload[:MAX_NEWS_REQUEST]:
        if not isinstance(item, dict):
            exclusions["malformed"] += 1
            continue
        if item.get("ad"):
            exclusions["advertisement"] += 1
            continue
        content = item.get("content", item)
        recognized_fields = {
            "title", "headline", "pubDate", "providerPublishTime", "canonicalUrl", "clickThroughUrl",
            "link", "url", "summary", "description", "provider", "publisher", "fullText", "full_text",
        }
        if not isinstance(content, dict) or not (recognized_fields & content.keys()):
            exclusions["malformed"] += 1
            continue
        headline = _plain(content.get("title")) or _plain(content.get("headline"))
        if not headline:
            exclusions["missing_headline"] += 1
            continue
        published = _publication_time(
            content.get("pubDate") or content.get("providerPublishTime") or item.get("providerPublishTime")
        )
        if published is None:
            exclusions["undated"] += 1
            continue
        if published > instant:
            exclusions["future"] += 1
            continue
        if not lower <= published < upper:
            exclusions["outside_window"] += 1
            continue
        url = next((
            candidate for value in (
                content.get("canonicalUrl"), content.get("clickThroughUrl"),
                content.get("link"), content.get("url"), item.get("link"),
            ) if (candidate := _safe_url(_url_value(value))) is not None
        ), None)
        if url is None:
            exclusions["invalid_url"] += 1
            continue
        provider = content.get("provider")
        publisher = (
            _plain(provider.get("displayName")) or _plain(provider.get("name"))
            if isinstance(provider, dict) else _plain(provider)
        ) or _plain(content.get("publisher")) or _plain(item.get("publisher"))
        full_text = _plain(content.get("fullText")) or _plain(content.get("full_text"))
        description = _plain(content.get("summary")) or _plain(content.get("description"))
        evidence_type = "full_text" if full_text else "description" if description else "headline_only"
        text = full_text or description
        cap = MAX_FULL_TEXT_CHARS if full_text else MAX_DESCRIPTION_CHARS
        truncated = bool(text and len(text) > cap)
        text = text[:cap] if text else None
        provider_id = _plain(content.get("id")) or _plain(item.get("id")) or _plain(item.get("uuid"))
        candidates.append((NewsArticle("", headline, publisher, published, url, text, evidence_type), provider_id, truncated))

    if exclusions["malformed"] == min(len(payload), MAX_NEWS_REQUEST):
        raise ValueError("Yahoo news list contained only malformed article records.")
    candidates.sort(key=lambda candidate: candidate[0].published_at, reverse=True)
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    articles: list[NewsArticle] = []
    duplicates = 0
    for article, provider_id, truncated in candidates:
        identity = _identity_url(article.url)
        title_key = (article.headline.casefold(), (article.publisher or "").casefold())
        if (provider_id and provider_id in seen_ids) or identity in seen_urls or title_key in seen_titles:
            duplicates += 1
            continue
        if provider_id:
            seen_ids.add(provider_id)
        seen_urls.add(identity)
        seen_titles.add(title_key)
        if len(articles) >= MAX_ARTICLES:
            continue
        article = replace(article, source_id=f"N{len(articles) + 1}")
        articles.append(article)
        if truncated:
            messages.append(f"{article.source_id}: provider {article.evidence_type} text was truncated to {len(article.text)} characters.")
        if article.evidence_type == "headline_only":
            messages.append(f"{article.source_id}: Yahoo supplied only a headline; article text was not retrieved.")
        if article.publisher is None:
            messages.append(f"{article.source_id}: Yahoo did not supply a publisher.")

    for reason, count in exclusions.items():
        if count:
            messages.append(f"Excluded {count} news item(s): {reason.replace('_', ' ')}.")
    if duplicates:
        messages.append(f"Removed {duplicates} duplicate news item(s) by provider ID, URL, or headline/publisher.")
    if len(payload) > MAX_NEWS_REQUEST:
        messages.append(f"Yahoo returned more than requested; only the first {MAX_NEWS_REQUEST} items were inspected.")
    if len(candidates) - duplicates > MAX_ARTICLES:
        messages.append(f"Retained only the latest {MAX_ARTICLES} unique articles in the selected window.")
    if not articles:
        messages.append("No usable dated article sources remained in the selected window; this is a coverage gap, not proof of no events.")
    return tuple(articles), tuple(messages)


def _retrieval_error(label: str, detail: str) -> str:
    lowered = detail.lower()
    if any(term in lowered for term in ("ratelimit", "rate limit", "too many requests", "throttl", "429")):
        return f"Yahoo throttled the {label} request. Wait several minutes before refreshing."
    if any(term in lowered for term in ("connection", "timeout", "timed out", "curl", "network", "resolve", "ssl")):
        return f"Yahoo {label} retrieval failed because of a connection or timeout problem. Check connectivity and retry."
    return f"Yahoo {label} retrieval failed or returned malformed evidence. Check the symbol and provider availability, then retry."


def fetch_company_evidence(
    symbol: str, start: date, end: date, *, ticker_factory: Callable | None = None,
    now: datetime | None = None,
) -> CompanyEvidence:
    """Independently retrieve a company profile and at most 20 latest news items.

    Injecting ``ticker_factory`` and ``now`` enables deterministic tests. Neither
    provider failures nor missing fields are replaced with invented evidence.
    """
    instant = _utc_now(now)
    _validate_window(start, end, instant)
    symbols = parse_symbols(symbol)
    if len(symbols) != 1:
        raise ValueError("Research retrieval requires exactly one symbol.")
    symbol = symbols[0]
    company = CompanyInfo(symbol, source_url=_profile_url(symbol))
    articles: tuple[NewsArticle, ...] = ()
    messages: list[str] = []
    logger = logging.getLogger("yfinance")
    try:
        if ticker_factory is None:
            configure_yfinance_cache()
        ticker = (yf.Ticker if ticker_factory is None else ticker_factory)(symbol)
    except Exception as error:
        return CompanyEvidence(
            company, articles, "error", "error",
            ("Yahoo client initialization failed. " + _retrieval_error("company/news", str(error)), NEWS_COVERAGE_NOTE),
            _utc_now(now),
        )

    statuses: dict[str, str] = {}
    for label, retrieve in (("company profile", ticker.get_info), ("news", lambda: ticker.get_news(count=MAX_NEWS_REQUEST, tab="news"))):
        captured = _ProviderMessages()
        logger.addHandler(captured)
        try:
            payload = retrieve()
            if captured.messages and not payload:
                raise RuntimeError(" ".join(captured.messages))
            if label == "company profile":
                company, notes = normalize_company_info(symbol, payload)
                statuses[label] = "success" if any((company.name, company.sector, company.industry, company.business_description, company.website)) else "empty"
            else:
                articles, notes = normalize_news(payload, start, end, now=_utc_now(now))
                statuses[label] = "success" if articles else "empty"
            messages.extend(notes)
            if captured.messages:
                messages.append(f"Yahoo logged errors while retrieving {label}; returned evidence may be incomplete.")
        except Exception as error:
            statuses[label] = "error"
            messages.append(_retrieval_error(label, f"{type(error).__name__}: {error}"))
            if label == "news":
                messages.append(NEWS_COVERAGE_NOTE)
        finally:
            logger.removeHandler(captured)

    return CompanyEvidence(
        company, articles, statuses["company profile"], statuses["news"],
        tuple(messages), _utc_now(now),
    )
