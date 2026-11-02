"""Deterministic research tests; all company/news text is SYNTHETIC test data."""

from datetime import date, datetime, timedelta, timezone
import logging
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_data import (
    MAX_DESCRIPTION_CHARS, MAX_FULL_TEXT_CHARS, CompanyInfo,
    fetch_company_evidence, normalize_company_info, normalize_news,
)


NOW = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
START = date(2026, 10, 27)
END = date(2026, 11, 2)


def synthetic_article(identifier="one", published="2026-11-02T10:00:00Z", **changes):
    """Invented provider-shaped article, never production fallback data."""
    content = {
        "id": identifier,
        "title": f"Synthetic article {identifier}",
        "pubDate": published,
        "provider": {"displayName": "Synthetic Publisher"},
        "canonicalUrl": {"url": f"https://example.test/news/{identifier}"},
        "summary": "Synthetic provider description, not full article text.",
    }
    content.update(changes)
    return {"id": identifier, "content": content}


class SyntheticTicker:
    def __init__(self, info=None, news=None, info_error=None, news_error=None, news_log=None):
        self.info = {} if info is None else info
        self.news = [] if news is None else news
        self.info_error = info_error
        self.news_error = news_error
        self.news_log = news_log
        self.calls = []

    def get_info(self):
        self.calls.append(("info",))
        if self.info_error:
            raise self.info_error
        return self.info

    def get_news(self, count, tab):
        self.calls.append(("news", count, tab))
        if self.news_error:
            raise self.news_error
        if self.news_log:
            logging.getLogger("yfinance").error(self.news_log)
        return self.news


def test_company_profile_allowlist_preserves_missing_facts_and_encoded_source():
    company, messages = normalize_company_info(" ^gspc ", {
        "shortName": "Synthetic company",
        "longBusinessSummary": "<p>Synthetic business &amp; products.</p>",
        "website": "javascript:alert(1)",
        "marketCap": 999999999,  # Not part of the company evidence allowlist.
    })
    assert company.symbol == "^GSPC"
    assert company.name == "Synthetic company"
    assert company.business_description == "Synthetic business & products."
    assert company.sector is None and company.industry is None and company.website is None
    assert company.source_url == "https://finance.yahoo.com/quote/%5EGSPC/profile/"
    assert any("invalid company website" in message for message in messages)
    assert any("sector, industry" in message for message in messages)
    assert CompanyInfo("TEST").name is None


def test_nested_news_uses_canonical_source_and_labels_summary_as_description():
    item = synthetic_article(
        pubDate="2026-11-02T05:30:00-05:00",
        clickThroughUrl={"url": "https://other.example.test/tracking-link"},
        summary="<p>Synthetic <b>description</b> &amp; context.</p>",
        body="This ambiguous body field must not imply full text was read.",
    )
    articles, messages = normalize_news([item], START, END, now=NOW)
    article = articles[0]
    assert article.source_id == "N1"
    assert article.publisher == "Synthetic Publisher"
    assert article.published_at == datetime(2026, 11, 2, 10, 30, tzinfo=timezone.utc)
    assert article.url == "https://example.test/news/one"
    assert article.text == "Synthetic description & context."
    assert article.evidence_type == "description"
    assert any("not an archive" in message for message in messages)
    assert any("No article links were opened" in message for message in messages)


def test_legacy_news_timestamp_and_explicit_full_text_are_supported():
    timestamp = datetime(2026, 11, 1, 23, 59, tzinfo=timezone.utc)
    legacy = {
        "uuid": "synthetic-legacy-id",
        "title": "Synthetic legacy headline",
        "publisher": "Synthetic Legacy Publisher",
        "providerPublishTime": int(timestamp.timestamp()),
        "link": "https://example.test/legacy?article=17",
        "full_text": "Synthetic provider-supplied complete text.",
        "summary": "Synthetic short summary.",
    }
    articles, _ = normalize_news([legacy], START, END, now=NOW)
    assert articles[0].published_at == timestamp
    assert articles[0].text == "Synthetic provider-supplied complete text."
    assert articles[0].evidence_type == "full_text"


def test_utc_window_includes_end_day_and_excludes_future_or_undated_sources():
    payload = [
        synthetic_article("start", "2026-10-27T00:00:00Z"),
        synthetic_article("before", "2026-10-26T23:59:59Z"),
        synthetic_article("today", "2026-11-02T00:00:00Z"),
        synthetic_article("now", NOW.isoformat()),
        synthetic_article("offset", "2026-11-01T20:00:00-05:00"),
        synthetic_article("future", "2026-11-02T15:00:01Z"),
        synthetic_article("missing-date", None),
        synthetic_article("zone-less", "2026-11-02T01:00:00"),
    ]
    articles, messages = normalize_news(payload, START, END, now=NOW)
    assert [article.headline for article in articles] == [
        "Synthetic article now", "Synthetic article offset", "Synthetic article today", "Synthetic article start"
    ]
    assert all(article.published_at.tzinfo is timezone.utc for article in articles)
    assert any("future" in message for message in messages)
    assert any("undated" in message for message in messages)
    assert any("outside window" in message for message in messages)


def test_news_dedup_drops_tracking_but_preserves_identity_query_parameters():
    payload = [
        synthetic_article("id1", canonicalUrl={"url": "https://example.test/story?story=101&utm_source=alpha"}),
        synthetic_article("id2", canonicalUrl={"url": "https://example.test/story?utm_source=beta&story=101"}),
        synthetic_article("id1", title="Different title with same provider ID", canonicalUrl={"url": "https://example.test/another"}),
        synthetic_article("id3", canonicalUrl={"url": "https://example.test/story?story=102&utm_source=alpha"}),
    ]
    articles, messages = normalize_news(payload, START, END, now=NOW)
    assert len(articles) == 2
    assert articles[0].url == "https://example.test/story?story=101&utm_source=alpha"
    assert articles[1].url == "https://example.test/story?story=102&utm_source=alpha"
    assert any("2 duplicate" in message for message in messages)


def test_only_latest_five_unique_articles_receive_stable_ids():
    payload = [
        synthetic_article(str(index), (NOW - timedelta(hours=index)).isoformat())
        for index in range(7, 0, -1)
    ]
    articles, messages = normalize_news(payload, START, END, now=NOW)
    assert [article.source_id for article in articles] == ["N1", "N2", "N3", "N4", "N5"]
    assert [article.headline for article in articles] == [f"Synthetic article {index}" for index in range(1, 6)]
    assert any("latest 5" in message for message in messages)


def test_headline_only_and_missing_publisher_are_explicit():
    articles, messages = normalize_news([
        synthetic_article(provider=None, summary=None, body="Unrecognized body is not verified full text.")
    ], START, END, now=NOW)
    assert articles[0].text is None
    assert articles[0].publisher is None
    assert articles[0].evidence_type == "headline_only"
    assert any("only a headline" in message for message in messages)
    assert any("did not supply a publisher" in message for message in messages)


def test_invalid_article_links_are_excluded_without_opening_them():
    articles, messages = normalize_news([
        synthetic_article("unsafe", canonicalUrl={"url": "javascript:alert(1)"}),
        synthetic_article("credentials", canonicalUrl={"url": "https://name:password@example.test/article"}),
        synthetic_article("valid", canonicalUrl={"url": "https://example.test/valid"}),
    ], START, END, now=NOW)
    assert len(articles) == 1
    assert articles[0].headline == "Synthetic article valid"
    assert any("2 news item(s): invalid url" in message for message in messages)


@pytest.mark.parametrize("field,cap,evidence_type", [
    ("summary", MAX_DESCRIPTION_CHARS, "description"),
    ("fullText", MAX_FULL_TEXT_CHARS, "full_text"),
])
def test_provider_text_limits_are_reported(field, cap, evidence_type):
    articles, messages = normalize_news([
        synthetic_article(**{field: "S" * (cap + 1)})
    ], START, END, now=NOW)
    assert len(articles[0].text) == cap
    assert articles[0].evidence_type == evidence_type
    assert any("truncated" in message for message in messages)


@pytest.mark.parametrize("payload,status", [
    ([], "empty"), ({}, "error"), ([{}], "error"),
    ([{"unexpected_provider_shape": True}], "error"), (["malformed"], "error"),
])
def test_empty_news_is_distinct_from_malformed_response(payload, status):
    ticker = SyntheticTicker(info={"longName": "Synthetic Company"}, news=payload)
    evidence = fetch_company_evidence("TEST", START, END, ticker_factory=lambda symbol: ticker, now=NOW)
    assert evidence.info_status == "success"
    assert evidence.news_status == status
    assert evidence.articles == ()
    assert evidence.retrieved_at == NOW
    assert ("news", 20, "news") in ticker.calls
    if status == "empty":
        assert any("does not establish" in message for message in evidence.messages)


@pytest.mark.parametrize("failed_part", ["info", "news"])
def test_company_and_news_fail_independently_without_discarding_other_evidence(failed_part):
    ticker = SyntheticTicker(
        info={"longName": "Synthetic Company"}, news=[synthetic_article()],
        info_error=ConnectionError("Synthetic network failure") if failed_part == "info" else None,
        news_error=RuntimeError("Synthetic rate limit 429") if failed_part == "news" else None,
    )
    evidence = fetch_company_evidence("test", START, END, ticker_factory=lambda symbol: ticker, now=NOW)
    assert evidence.company.symbol == "TEST"
    assert evidence.info_status == ("error" if failed_part == "info" else "success")
    assert evidence.news_status == ("error" if failed_part == "news" else "success")
    assert bool(evidence.articles) == (failed_part == "info")
    assert bool(evidence.company.name) == (failed_part == "news")


def test_missing_company_info_is_not_inferred_and_logged_news_failure_is_error():
    ticker = SyntheticTicker(info={}, news=[], news_log="Synthetic Yahoo connection failure")
    evidence = fetch_company_evidence("TEST", START, END, ticker_factory=lambda symbol: ticker, now=NOW)
    assert evidence.info_status == "empty"
    assert evidence.company.name is None and evidence.company.business_description is None
    assert evidence.news_status == "error"
    assert any("connection" in message for message in evidence.messages)


def test_research_window_validation_rejects_future_dates_and_oversized_requests():
    for start, end in ((END, START), (START, END + timedelta(days=1)), (END - timedelta(days=30), END)):
        with pytest.raises(ValueError):
            normalize_news([], start, end, now=NOW)
    with pytest.raises(ValueError, match="timezone"):
        normalize_news([], START, END, now=NOW.replace(tzinfo=None))
