"""Report interaction tests; all company/news data and generated text are SYNTHETIC."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_data import CompanyEvidence, CompanyInfo, NewsArticle
from reporting import CompanyReport, ReportConfig, ReportConfigurationError, ReportGenerationError
import report_ui
import ui


APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def isolated_evidence_cache():
    report_ui.cached_company_evidence.clear()
    yield
    report_ui.cached_company_evidence.clear()


def synthetic_evidence(symbol, start, end):
    """Invented records exercise UI state; they are never supplied by production."""
    return CompanyEvidence(
        company=CompanyInfo(symbol=symbol, name=f"Synthetic {symbol}", sector="Synthetic sector",
                            business_description="Synthetic company description for tests only.",
                            source_url="https://example.com/synthetic-company"),
        articles=(NewsArticle(
            source_id="N1", headline="Synthetic test headline", publisher="Synthetic publisher",
            published_at=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
            url="https://example.com/synthetic-news", text="Synthetic news description.",
            evidence_type="description",
        ),),
        info_status="success", news_status="success", messages=(),
        retrieved_at=datetime.now(timezone.utc),
    )


def synthetic_company_report(evidence, config):
    return CompanyReport(
        evidence=evidence, model=config.model, generated_at=datetime.now(timezone.utc),
        markdown=f"### Company overview\nSynthetic report for {evidence.company.symbol}.\n"
                 "### Recent developments\nSynthetic development for UI tests only.\n"
                 "### Why these developments may matter\nInference: synthetic interpretation.\n"
                 "### Sources and coverage\n1. [Synthetic source](https://example.com/synthetic-news)\n",
    )


def assert_healthy(app):
    assert not app.exception, [error.message for error in app.exception]


def test_report_uses_shared_watchlist_survives_navigation_and_reuses_generation(monkeypatch):
    retrieved, generated = [], []
    config = ReportConfig(api_key="synthetic-key-for-tests-only", model="synthetic-model")

    def fake_retrieve(symbol, start, end):
        retrieved.append((symbol, start, end))
        return synthetic_evidence(symbol, start, end)

    def fake_generate(evidence, settings):
        generated.append(evidence.company.symbol)
        return synthetic_company_report(evidence, settings)

    def unexpected_price_fetch(*args, **kwargs):
        raise AssertionError("Report generation must not request price history")

    monkeypatch.setattr(report_ui, "get_report_config", lambda: config)
    monkeypatch.setattr(report_ui, "fetch_company_evidence", fake_retrieve)
    monkeypatch.setattr(report_ui, "generate_company_report", fake_generate)
    monkeypatch.setattr(ui, "fetch_market_data", unexpected_price_fetch)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.text_area(key="watchlist").set_value(" aapl, MSFT, aapl ").run()
    app.radio(key="view").set_value("AI Report").run()
    assert_healthy(app)
    assert app.number_input(key="news_lookback_widget").value == 7
    assert retrieved == generated == []
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    snapshot = app.session_state["report_completed"]
    assert snapshot.inputs.symbols == ("AAPL", "MSFT")
    assert (snapshot.inputs.end - snapshot.inputs.start).days == 6
    assert generated == ["AAPL", "MSFT"]
    assert len(retrieved) == 2
    assert len(app.expander) == 2
    assert app.get("download_button")
    downloaded = report_ui.export_watchlist_report(snapshot)
    assert "## AAPL" in downloaded and "## MSFT" in downloaded
    assert "Synthetic report" in downloaded and "UTC" in downloaded
    assert app.session_state["active_result"] is None

    for view in ("Market Data", "Stock Details", "Screener", "AI Report"):
        app.radio(key="view").set_value(view).run()
        assert_healthy(app)
        assert app.session_state["report_completed"].completed_at == snapshot.completed_at
        assert len(generated) == len(retrieved) == 2
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    assert len(generated) == len(retrieved) == 2  # No repeat paid generation or provider call.
    assert all(outcome.reused for outcome in app.session_state["report_completed"].outcomes)

    app.number_input(key="news_lookback_widget").set_value(14).run()
    assert any("Previous inputs" in warning.value for warning in app.warning)
    app.radio(key="view").set_value("Market Data").run()
    app.radio(key="view").set_value("AI Report").run()
    assert app.number_input(key="news_lookback_widget").value == 14
    app.text_area(key="watchlist").set_value("NVDA").run()
    assert any("Previous inputs" in warning.value for warning in app.warning)
    assert len(generated) == 2
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    assert app.session_state["report_completed"].inputs.symbols == ("NVDA",)
    assert generated == ["AAPL", "MSFT", "NVDA"]


def test_partial_generation_failure_then_total_failure_retains_old_report(monkeypatch):
    config = ReportConfig(api_key="synthetic-key-for-tests-only", model="synthetic-model")
    calls, fail_all = [], [False]
    monkeypatch.setattr(report_ui, "get_report_config", lambda: config)
    monkeypatch.setattr(report_ui, "fetch_company_evidence", synthetic_evidence)

    def fake_generate(evidence, settings):
        calls.append(evidence.company.symbol)
        if evidence.company.symbol == "BROKEN" or fail_all[0]:
            raise ReportGenerationError("Synthetic generation failure for tests only.")
        return synthetic_company_report(evidence, settings)

    monkeypatch.setattr(report_ui, "generate_company_report", fake_generate)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.text_area(key="watchlist").set_value("AAPL, BROKEN").run()
    app.radio(key="view").set_value("AI Report").run()
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    original = app.session_state["report_completed"]
    assert original.success_count == 1
    assert original.outcomes[1].error
    exported = report_ui.export_watchlist_report(original)
    assert "## BROKEN" in exported and "Report generation failed" in exported
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    assert calls.count("AAPL") == 1
    assert calls.count("BROKEN") == 2  # Failures are retried on another explicit action.
    fail_all[0] = True
    app.number_input(key="news_lookback_widget").set_value(8).run()
    app.button(key="generate_watchlist_report").click().run()
    assert_healthy(app)
    assert app.session_state["report_last_attempt"].success_count == 0
    assert app.session_state["report_completed"].inputs == original.inputs
    assert any("Retained report" in warning.value for warning in app.warning)
    assert any("Previous inputs" in warning.value for warning in app.warning)
    assert app.get("download_button")


def test_missing_configuration_and_invalid_watchlist_do_not_call_providers(monkeypatch):
    calls = []

    def missing_configuration():
        raise ReportConfigurationError("OPENAI_API_KEY is missing (synthetic setup test).")

    def unexpected_call(*args, **kwargs):
        calls.append(True)
        raise AssertionError("No network call should be made")

    monkeypatch.setattr(report_ui, "get_report_config", missing_configuration)
    monkeypatch.setattr(report_ui, "fetch_company_evidence", unexpected_call)
    monkeypatch.setattr(report_ui, "generate_company_report", unexpected_call)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.radio(key="view").set_value("AI Report").run()
    assert_healthy(app)
    assert app.button(key="generate_watchlist_report").disabled
    assert any("OPENAI_API_KEY" in warning.value for warning in app.warning)
    app.text_area(key="watchlist").set_value(" , ").run()
    assert_healthy(app)
    assert app.button(key="generate_watchlist_report").disabled
    assert any("Enter at least one" in error.value for error in app.error)
    app.radio(key="view").set_value("Stock Details").run()
    assert_healthy(app)
    assert calls == []
