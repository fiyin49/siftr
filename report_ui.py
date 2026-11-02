"""AI Report interface and session persistence, separate from prices and prompts.

Public Yahoo evidence is cached briefly. Paid generation is reused only inside
the current session and can run only in response to the explicit report button.
Credentials remain local to the server-side call, never in stored report state.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
import re

import streamlit as st

from market_data import CACHE_TTL_SECONDS, parse_symbols
from research_data import CompanyEvidence, fetch_company_evidence
from reporting import (
    CompanyReport, ReportConfig, ReportConfigurationError, ReportGenerationError,
    generate_company_report, get_report_config,
)


@dataclass(frozen=True)
class ReportInputs:
    symbols: tuple[str, ...]
    start: date
    end: date
    model: str


@dataclass(frozen=True)
class CompanyOutcome:
    symbol: str
    report: CompanyReport | None
    evidence: CompanyEvidence | None
    error: str | None = None
    reused: bool = False


@dataclass(frozen=True)
class WatchlistReport:
    inputs: ReportInputs
    completed_at: datetime
    outcomes: tuple[CompanyOutcome, ...]

    @property
    def success_count(self) -> int:
        return sum(outcome.report is not None for outcome in self.outcomes)


class EvidenceRequestFailed(Exception):
    """Keep provider failures out of the successful-evidence cache."""

    def __init__(self, evidence: CompanyEvidence):
        self.evidence = evidence
        super().__init__("Yahoo returned a company-information or news retrieval error.")


@st.cache_data(ttl=CACHE_TTL_SECONDS, max_entries=100, show_spinner=False)
def cached_company_evidence(symbol: str, start: date, end: date) -> CompanyEvidence:
    evidence = fetch_company_evidence(symbol, start, end)
    if evidence.info_status == "error" or evidence.news_status == "error":
        raise EvidenceRequestFailed(evidence)
    return evidence


def initialize_report_state() -> None:
    for key, value in {
        "report_lookback_days": 7,
        "report_completed": None,
        "report_last_attempt": None,
        "report_generation_cache": {},
    }.items():
        if key not in st.session_state:
            st.session_state[key] = value


def news_window(days: int, *, today: date | None = None) -> tuple[date, date]:
    """Today plus the preceding days, using UTC calendar dates, not trading days."""
    if not 1 <= days <= 30:
        raise ValueError("Choose a news lookback between 1 and 30 calendar days.")
    end = today or datetime.now(timezone.utc).date()
    return end - timedelta(days=days - 1), end


def evidence_key(evidence: CompanyEvidence, inputs: ReportInputs) -> str:
    payload = {
        "evidence": asdict(evidence), "model": inputs.model,
        "start": inputs.start.isoformat(), "end": inputs.end.isoformat(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def generate_watchlist(inputs: ReportInputs, config: ReportConfig) -> WatchlistReport:
    """Bounded per-company work; an individual failure never discards other results."""
    outcomes: list[CompanyOutcome] = []
    progress = st.progress(0, text="Preparing watchlist research…")
    cache = st.session_state.report_generation_cache
    for index, symbol in enumerate(inputs.symbols):
        evidence = None
        progress.progress(index / len(inputs.symbols), text=f"{symbol}: retrieving company information and news…")
        try:
            try:
                evidence = cached_company_evidence(symbol, inputs.start, inputs.end)
            except EvidenceRequestFailed as failure:
                evidence = failure.evidence
            key = evidence_key(evidence, inputs)
            reused = key in cache
            if reused:
                report = cache[key]
            else:
                progress.progress(index / len(inputs.symbols), text=f"{symbol}: generating a grounded briefing…")
                report = generate_company_report(evidence, config)
                cache[key] = report
                while len(cache) > 50:
                    del cache[next(iter(cache))]
            outcomes.append(CompanyOutcome(symbol, report, evidence, reused=reused))
            st.success(f"{symbol}: {'reused the completed briefing' if reused else 'briefing generated'}.")
            if evidence.info_status == "error" or evidence.news_status == "error":
                st.warning(f"{symbol}: some Yahoo retrieval failed; the briefing identifies these coverage gaps.")
            elif not evidence.articles:
                st.warning(f"{symbol}: no relevant news was retrieved for this window. This does not establish that no developments occurred.")
        except ReportGenerationError as error:
            outcomes.append(CompanyOutcome(symbol, None, evidence, str(error)))
            st.error(f"{symbol}: {error}")
        except Exception:
            # Never expose provider exception bodies, request headers, or credentials.
            message = "The briefing could not be completed. Check the server configuration and provider availability, then retry."
            outcomes.append(CompanyOutcome(symbol, None, evidence, message))
            st.error(f"{symbol}: {message}")
        progress.progress((index + 1) / len(inputs.symbols), text=f"Completed {index + 1} of {len(inputs.symbols)} companies")
    return WatchlistReport(inputs, datetime.now(timezone.utc), tuple(outcomes))


def _plain_markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value.replace("<", "&lt;").replace(">", "&gt;"))


def export_watchlist_report(snapshot: WatchlistReport) -> str:
    inputs = snapshot.inputs
    lines = [
        "# SIFTR watchlist research briefing", "",
        f"Generated/completed: {snapshot.completed_at:%Y-%m-%d %H:%M:%S UTC}",
        f"Watchlist: {', '.join(_plain_markdown(symbol) for symbol in inputs.symbols)}",
        f"News window: {inputs.start} through {inputs.end}, inclusive UTC calendar dates; future timestamps excluded at retrieval.",
        f"Model: {_plain_markdown(inputs.model)}",
        f"Successful briefings: {snapshot.success_count}/{len(snapshot.outcomes)}", "",
        "Coverage: Yahoo's latest-item feed is limited and is not a complete news archive. "
        "No relevant news retrieved does not mean that nothing happened.", "",
    ]
    for outcome in snapshot.outcomes:
        lines.extend([f"## {_plain_markdown(outcome.symbol)}", ""])
        if outcome.report is not None:
            lines.extend([outcome.report.markdown, ""])
        else:
            lines.extend([f"**Report generation failed:** {_plain_markdown(outcome.error or 'Unknown failure')}", ""])
            if outcome.evidence is not None:
                lines.append(f"Company information retrieval: {outcome.evidence.info_status}. News retrieval: {outcome.evidence.news_status}.")
                lines.extend(f"- {_plain_markdown(message)}" for message in outcome.evidence.messages)
                lines.append("")
    return "\n".join(lines)


def _render_snapshot(snapshot: WatchlistReport) -> None:
    inputs = snapshot.inputs
    st.caption(f"Generated/completed: {snapshot.completed_at:%Y-%m-%d %H:%M:%S UTC} · Model: {inputs.model}")
    st.text(f"Report watchlist: {', '.join(inputs.symbols)}")
    st.caption(f"News window: {inputs.start} through {inputs.end}, inclusive UTC calendar dates. "
               "Articles dated after their retrieval time are excluded.")
    st.caption(f"{snapshot.success_count} of {len(snapshot.outcomes)} company briefings generated. "
               "Opening this report or changing views does not call OpenAI.")
    for outcome in snapshot.outcomes:
        title = outcome.symbol
        if outcome.evidence is not None and outcome.evidence.company.name:
            title += f" — {outcome.evidence.company.name}"
        with st.expander(title, expanded=len(snapshot.outcomes) == 1):
            if outcome.report is not None:
                st.success("Completed briefing" + (" · reused from this session" if outcome.reused else ""))
                st.caption(f"Company briefing generated: {outcome.report.generated_at:%Y-%m-%d %H:%M:%S UTC}")
                st.markdown(outcome.report.markdown)
            else:
                st.error(outcome.error or "Report generation failed.")
                if outcome.evidence is not None:
                    st.caption(f"Company information: {outcome.evidence.info_status} · News: {outcome.evidence.news_status}")
                    for message in outcome.evidence.messages:
                        st.caption(message)
    st.download_button(
        "Download complete report as Markdown", data=export_watchlist_report(snapshot),
        file_name=f"siftr_watchlist_briefing_{inputs.start}_{inputs.end}.md",
        mime="text/markdown", on_click="ignore", key="download_watchlist_report",
    )


def report_view() -> None:
    initialize_report_state()
    st.subheader("AI Report")
    st.write("Generate a concise company-background and recent-news briefing for every symbol in your current watchlist.")
    days = int(st.number_input(
        "News lookback (calendar days)", min_value=1, max_value=30,
        value=st.session_state.report_lookback_days, step=1, key="news_lookback_widget",
    ))
    st.session_state.report_lookback_days = days
    start, end = news_window(days)
    st.caption(f"Selected news window: {start} through {end}, inclusive UTC calendar dates "
               "(today plus the preceding days). This is independent of the price-history period.")
    symbols = None
    try:
        symbols = parse_symbols(st.session_state.get("watchlist", ""))
        st.text(f"Current watchlist: {', '.join(symbols)}")
    except ValueError as error:
        st.error(str(error))
    config = None
    try:
        config = get_report_config()
    except ReportConfigurationError as error:
        st.warning(str(error))
        st.info("Server setup: set OPENAI_API_KEY in the server environment. Optionally set OPENAI_MODEL "
                "to a model supporting the Responses API and structured outputs. On Streamlit Community Cloud, "
                "use the app's Settings → Secrets with those names as root-level entries. "
                "Keep the key server-side; do not put it in the watchlist or repository.")
    model = config.model if config else (os.environ.get("OPENAI_MODEL", "").strip() or "gpt-5.4-mini")
    st.caption(f"Configured model: {model}. Generation may incur OpenAI API charges. "
               "Public Yahoo evidence is cached for 15 minutes; identical successful generation is reused in this session.")
    st.caption("Coverage: at most five dated articles per company from Yahoo's latest 20 items; "
               "the feed may contain descriptions or headlines only and cannot establish complete coverage. "
               "Screener rules and stock rankings are not part of this briefing.")
    inputs = ReportInputs(symbols, start, end, model) if symbols is not None else None
    clicked = st.button("Generate watchlist report", type="primary", key="generate_watchlist_report",
                        disabled=config is None or inputs is None)
    if clicked and config is not None and inputs is not None:
        attempt = generate_watchlist(inputs, config)
        st.session_state.report_last_attempt = attempt
        if attempt.success_count:
            st.session_state.report_completed = attempt

    completed = st.session_state.report_completed
    attempt = st.session_state.report_last_attempt
    if attempt is not None and not attempt.success_count:
        st.error("The latest attempt did not generate any company briefings. Review the per-company errors and retry when the issue is resolved.")
        for outcome in attempt.outcomes:
            st.error(f"{outcome.symbol}: {outcome.error}")
        if completed is not None:
            st.warning("Retained report · The latest generation attempt failed. The report below is the previous completed report.")
    if completed is None:
        st.info("No completed watchlist report yet. Configure OpenAI, then select Generate watchlist report. "
                "No retrieval or paid generation runs simply by opening this view.")
        return
    if inputs != completed.inputs:
        st.warning("Previous inputs · This retained report belongs to the watchlist, news window, or model shown below. "
                   "The current settings differ; select Generate watchlist report to apply them.")
    _render_snapshot(completed)
