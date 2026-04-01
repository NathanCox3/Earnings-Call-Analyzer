from __future__ import annotations

import traceback

import pandas as pd
import streamlit as st

from earnings_call_app.alpha_vantage import (
    AlphaVantageError,
    get_transcript,
    list_recent_quarter_contexts,
    normalize_quarter_code,
    resolve_quarter,
)
from earnings_call_app.analysis import (
    build_heuristic_analysis,
    build_transcript_insights,
    build_trend_dashboard,
    build_trend_point,
    run_openai_analysis,
)
from earnings_call_app.config import get_config
from earnings_call_app.demo_data import build_demo_report
from earnings_call_app.models import EarningsReport, SourceLink
from earnings_call_app.reporting import pretty_source_payload, report_to_json, report_to_markdown
from earnings_call_app.sec import SecApiError, build_sec_verification

st.set_page_config(
    page_title="Earnings Call Analyzer",
    page_icon=":bar_chart:",
    layout="wide",
)


def _can_use_bundled_ibm_fallback(ticker: str, requested_quarter: str | None, has_alpha_key: bool) -> bool:
    if has_alpha_key:
        return False
    if ticker.upper() != "IBM":
        return False
    if not requested_quarter:
        return True
    try:
        return normalize_quarter_code(requested_quarter) == "2024Q1"
    except ValueError:
        return False


def _build_bundled_fallback_report(ticker: str, requested_quarter: str | None, mode: str, note: str) -> EarningsReport:
    config = get_config()
    report = build_demo_report(ticker, requested_quarter).model_copy(deep=True)
    report.mode = mode
    report.requested_quarter = requested_quarter or "Latest available"
    report.app_notes.insert(0, note)
    report.app_notes.append(
        "The displayed sentiment score and label are informational heuristics based on call tone, not investment advice."
    )
    report.sources.append(
        SourceLink(
            label="Alpha Vantage demo limitation note",
            url="https://www.alphavantage.co/documentation/",
            source_type="app",
            note="Bundled fallback was used because the public demo transcript path was unavailable.",
        )
    )

    if mode == "Free Data Only":
        report.analysis = build_heuristic_analysis(
            report.transcript_turns,
            report.transcript_insights,
            report.earnings_context,
            report.sec_verification,
        )
        report.analysis_engine = "Bundled IBM fallback + local heuristic analysis"
        return report

    if mode == "Free Data + OpenAI" and config.openai_api_key:
        heuristic = build_heuristic_analysis(
            report.transcript_turns,
            report.transcript_insights,
            report.earnings_context,
            report.sec_verification,
        )
        report.analysis, report.analysis_engine = run_openai_analysis(
            api_key=config.openai_api_key,
            model=config.openai_model,
            insights=report.transcript_insights,
            earnings_context=report.earnings_context,
            sec_verification=report.sec_verification,
            fallback=heuristic,
        )
        return report

    report.analysis_engine = "Bundled IBM fallback (OpenAI key missing)"
    return report


def build_live_report(ticker: str, requested_quarter: str | None, mode: str) -> EarningsReport:
    config = get_config()
    try:
        earnings_context = resolve_quarter(ticker, requested_quarter, config.alpha_vantage_api_key)
        transcript_turns = get_transcript(ticker, earnings_context.resolved_quarter, config.alpha_vantage_api_key)
    except AlphaVantageError as exc:
        if _can_use_bundled_ibm_fallback(ticker, requested_quarter, bool(config.alpha_vantage_api_key)):
            return _build_bundled_fallback_report(
                ticker,
                requested_quarter,
                mode,
                note=(
                    "Alpha Vantage's public demo transcript route was unavailable during this run, "
                    "so the app used the bundled IBM 2024Q1 fallback instead."
                ),
            )
        raise exc

    app_notes = []
    app_notes.append(
        "The displayed sentiment score and label are informational heuristics based on call tone, not investment advice."
    )
    if not config.alpha_vantage_api_key:
        app_notes.append(
            "Alpha Vantage is using its public demo key. Live transcript retrieval is generally only reliable for IBM demo cases until you add your own API key."
        )

    sec_verification = None
    try:
        sec_verification = build_sec_verification(ticker, earnings_context.resolved_quarter, config.sec_user_agent)
    except SecApiError as exc:
        app_notes.append(f"SEC verification was unavailable: {exc}")

    transcript_insights = build_transcript_insights(transcript_turns, earnings_context, sec_verification)
    heuristic_analysis = build_heuristic_analysis(
        transcript_turns,
        transcript_insights,
        earnings_context,
        sec_verification,
    )
    analysis = heuristic_analysis
    analysis_engine = "Local heuristic analysis"

    if mode == "Free Data + OpenAI":
        if config.openai_api_key:
            analysis, analysis_engine = run_openai_analysis(
                api_key=config.openai_api_key,
                model=config.openai_model,
                insights=transcript_insights,
                earnings_context=earnings_context,
                sec_verification=sec_verification,
                fallback=heuristic_analysis,
            )
        else:
            app_notes.append(
                "OPENAI_API_KEY is missing, so the app fell back to local heuristic analysis."
            )
            analysis_engine = "Local heuristic analysis (OpenAI key missing)"

    trend_points = [
        build_trend_point(
            earnings_context=earnings_context,
            analysis=heuristic_analysis,
            transcript_available=True,
        )
    ]
    try:
        recent_contexts = list_recent_quarter_contexts(ticker, config.alpha_vantage_api_key, limit=4)
        for context in recent_contexts:
            if context.resolved_quarter == earnings_context.resolved_quarter:
                continue
            try:
                quarter_turns = get_transcript(
                    ticker,
                    context.resolved_quarter,
                    config.alpha_vantage_api_key,
                )
                quarter_sec = None
                quarter_note = None
                try:
                    quarter_sec = build_sec_verification(
                        ticker,
                        context.resolved_quarter,
                        config.sec_user_agent,
                    )
                except SecApiError as exc:
                    quarter_note = f"SEC verification unavailable for {context.resolved_quarter}: {exc}"
                quarter_insights = build_transcript_insights(quarter_turns, context, quarter_sec)
                quarter_analysis = build_heuristic_analysis(
                    quarter_turns,
                    quarter_insights,
                    context,
                    quarter_sec,
                )
                trend_points.append(
                    build_trend_point(
                        earnings_context=context,
                        analysis=quarter_analysis,
                        transcript_available=True,
                        note=quarter_note,
                    )
                )
            except AlphaVantageError as exc:
                trend_points.append(
                    build_trend_point(
                        earnings_context=context,
                        analysis=None,
                        transcript_available=False,
                        note=str(exc),
                    )
                )
    except AlphaVantageError as exc:
        app_notes.append(f"Historical trend data was unavailable: {exc}")

    trend_dashboard = build_trend_dashboard(
        points=trend_points,
        note="Historical dashboard uses local heuristic scoring across quarters for consistency and cost control.",
    )

    sources = [
        SourceLink(
            label="Alpha Vantage documentation",
            url="https://www.alphavantage.co/documentation/",
            source_type="alpha_vantage",
            note="Transcript and earnings metadata source.",
        )
    ]
    if sec_verification and sec_verification.filing_url:
        sources.append(
            SourceLink(
                label="SEC filing",
                url=sec_verification.filing_url,
                source_type="sec",
                note="Matched filing for the requested quarter.",
            )
        )
    if sec_verification and sec_verification.companyfacts_url:
        sources.append(
            SourceLink(
                label="SEC company facts",
                url=sec_verification.companyfacts_url,
                source_type="sec",
                note="Quarterly numeric verification source.",
            )
        )
    if mode == "Free Data + OpenAI":
        sources.append(
            SourceLink(
                label="OpenAI API",
                url="https://openai.com/api/pricing/",
                source_type="openai",
                note="Used only for the narrative synthesis layer.",
            )
        )

    return EarningsReport(
        ticker=ticker.upper(),
        quarter=earnings_context.resolved_quarter,
        requested_quarter=requested_quarter or "Latest available",
        company_name=sec_verification.company_name if sec_verification else None,
        mode=mode,
        analysis_engine=analysis_engine,
        transcript_turns=transcript_turns,
        earnings_context=earnings_context,
        transcript_insights=transcript_insights,
        analysis=analysis,
        trend_dashboard=trend_dashboard,
        sec_verification=sec_verification,
        sources=sources,
        app_notes=app_notes,
    )


def render_report(report: EarningsReport) -> None:
    header_left, header_right = st.columns([3, 2])
    with header_left:
        st.title(f"{report.ticker} Earnings Call Analyzer")
        if report.company_name:
            st.caption(report.company_name)
    with header_right:
        st.metric("Quarter", report.quarter)
        st.metric("Analysis Engine", report.analysis_engine)

    metrics_cols = st.columns(5)
    metrics_cols[0].metric("Sentiment Score", f"{report.analysis.signal_score:.1f}/10")
    metrics_cols[1].metric("Sentiment", report.analysis.sentiment)
    metrics_cols[2].metric("Prepared Remarks Turns", str(len(report.transcript_insights.prepared_remarks)))
    metrics_cols[3].metric("Q&A Turns", str(len(report.transcript_insights.qa)))
    metrics_cols[4].metric("Reported EPS", report.earnings_context.reported_eps or "n/a")
    filing_label = (
        f"{report.sec_verification.matched_form} on {report.sec_verification.filing_date}"
        if report.sec_verification and report.sec_verification.matched_form and report.sec_verification.filing_date
        else "Not matched"
    )
    st.caption(
        "Sentiment Score is a 0-10 heuristic where 0 is most bearish, 5 is neutral, and 10 is most bullish. "
        "It summarizes call tone only and is not investment advice."
    )
    st.metric("SEC Filing", filing_label)

    for note in report.app_notes:
        st.info(note)

    tab_summary, tab_trend, tab_qa, tab_sec, tab_sources = st.tabs(
        ["Executive Summary", "Trend Dashboard", "Themes & Q&A", "Filing Check", "Sources"]
    )

    with tab_summary:
        st.subheader("Summary")
        st.write(report.analysis.summary)
        st.subheader("Sentiment")
        st.write(
            f"**{report.analysis.sentiment}** at **{report.analysis.signal_score:.1f}/10**"
        )
        st.write(report.analysis.sentiment_rationale)
        st.subheader("Tone")
        st.write(report.analysis.tone)
        st.subheader("Key Themes")
        for item in report.analysis.key_themes:
            st.markdown(f"- {item}")
        st.subheader("Financial Highlights")
        for item in report.analysis.financial_highlights:
            st.markdown(f"- {item}")
        st.subheader("Guidance")
        for item in report.analysis.guidance:
            st.markdown(f"- {item}")
        st.subheader("Risks")
        for item in report.analysis.risks:
            st.markdown(f"- {item}")

    with tab_trend:
        st.subheader("Last 4 Quarters")
        if report.trend_dashboard and report.trend_dashboard.note:
            st.caption(report.trend_dashboard.note)
        if report.trend_dashboard:
            for flag in report.trend_dashboard.momentum_flags:
                st.markdown(f"- {flag}")
            if report.trend_dashboard.repeated_themes:
                st.write(
                    "**Repeated themes:** "
                    + ", ".join(report.trend_dashboard.repeated_themes)
                )

            chart_points = [
                {
                    "Quarter": point.quarter,
                    "Sentiment Score": point.signal_score,
                }
                for point in reversed(report.trend_dashboard.points)
                if point.signal_score is not None
            ]
            if chart_points:
                st.line_chart(pd.DataFrame(chart_points), x="Quarter", y="Sentiment Score")

            trend_rows = [
                {
                    "Quarter": point.quarter,
                    "Sentiment Score": f"{point.signal_score:.1f}/10" if point.signal_score is not None else "n/a",
                    "Sentiment": point.sentiment,
                    "EPS Surprise %": point.surprise_percentage or "n/a",
                    "Themes": ", ".join(point.key_themes[:2]) if point.key_themes else "n/a",
                    "Note": point.note or "",
                }
                for point in report.trend_dashboard.points
            ]
            st.dataframe(pd.DataFrame(trend_rows), use_container_width=True, hide_index=True)
        else:
            st.warning("Historical trend data is not available for this report.")

    with tab_qa:
        st.subheader("Q&A Highlights")
        for item in report.analysis.qa_highlights:
            st.markdown(f"- {item}")
        st.subheader("Speaker Activity")
        st.json(report.transcript_insights.speaker_counts)
        with st.expander("Transcript Excerpts"):
            for turn in report.transcript_turns[:12]:
                st.markdown(
                    f"**{turn.speaker}**"
                    + (f" ({turn.title})" if turn.title else "")
                    + f" [{turn.section.replace('_', ' ')}]"
                )
                st.write(turn.content)

    with tab_sec:
        if report.sec_verification:
            st.json(report.sec_verification.model_dump())
        else:
            st.warning("No SEC verification was available for this run.")

    with tab_sources:
        for source in report.sources:
            st.markdown(f"- **{source.source_type}**: [{source.label}]({source.url})")
            if source.note:
                st.caption(source.note)
        st.subheader("Source Payload")
        st.code(pretty_source_payload(report), language="json")

    st.divider()
    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "Download JSON",
        data=report_to_json(report),
        file_name=f"{report.ticker.lower()}-{report.quarter.lower()}-earnings-report.json",
        mime="application/json",
    )
    download_col2.download_button(
        "Download Markdown",
        data=report_to_markdown(report),
        file_name=f"{report.ticker.lower()}-{report.quarter.lower()}-earnings-report.md",
        mime="text/markdown",
    )


def main() -> None:
    config = get_config()
    st.sidebar.title("Controls")
    mode = st.sidebar.radio(
        "Mode",
        options=["Demo", "Free Data Only", "Free Data + OpenAI"],
        index=0,
    )
    ticker = st.sidebar.text_input("Ticker", value="IBM")
    quarter = st.sidebar.text_input("Quarter", value="2024Q1")

    st.sidebar.caption("Leave quarter blank to resolve the latest available quarter from Alpha Vantage.")

    if mode == "Free Data + OpenAI" and not config.openai_api_key:
        st.sidebar.warning("OPENAI_API_KEY is not configured. The app will fall back to local heuristics.")
    if mode != "Demo" and not config.alpha_vantage_api_key:
        st.sidebar.info("ALPHA_VANTAGE_API_KEY is not configured. The app will use Alpha Vantage's public demo key.")

    analyze = st.sidebar.button("Analyze", type="primary", use_container_width=True)

    if not analyze:
        st.title("Earnings Call Analyzer")
        st.write(
            "Analyze an earnings transcript with free Alpha Vantage and SEC data, "
            "then optionally add a low-cost OpenAI synthesis layer."
        )
        st.markdown("- `Demo` keeps the UI fully testable offline.")
        st.markdown("- `Free Data Only` uses Alpha Vantage plus SEC verification and local heuristics.")
        st.markdown("- `Free Data + OpenAI` adds a structured narrative layer on top.")
        return

    try:
        if mode == "Demo":
            report = build_demo_report(ticker, quarter)
        else:
            report = build_live_report(ticker, quarter or None, mode)
        render_report(report)
    except (AlphaVantageError, SecApiError, ValueError) as exc:
        st.error(str(exc))
        with st.expander("Technical details"):
            st.code(traceback.format_exc(), language="text")
    except Exception as exc:  # pragma: no cover
        st.error(f"Unexpected application error: {exc}")
        with st.expander("Technical details"):
            st.code(traceback.format_exc(), language="text")


if __name__ == "__main__":
    main()
