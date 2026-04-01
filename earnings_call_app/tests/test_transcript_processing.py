from __future__ import annotations

from earnings_call_app.analysis import (
    build_heuristic_analysis,
    build_transcript_insights,
    build_trend_dashboard,
    build_trend_point,
    split_transcript_sections,
)
from earnings_call_app.models import EarningsContext, QuarterTrendPoint, SecVerification, TranscriptTurn


def _turns_from_fixture(payload: dict) -> list[TranscriptTurn]:
    return [
        TranscriptTurn(
            speaker=item["speaker"],
            title=item.get("title"),
            content=item["content"],
        )
        for item in payload["transcript"]
    ]


def test_split_transcript_sections_detects_qa(alpha_vantage_transcript_fixture: dict) -> None:
    turns = _turns_from_fixture(alpha_vantage_transcript_fixture)
    prepared, qa = split_transcript_sections(turns)
    assert prepared
    assert qa
    assert prepared[0].section == "prepared_remarks"
    assert qa[0].section == "qa"


def test_transcript_insights_extract_guidance_and_risk(alpha_vantage_transcript_fixture: dict) -> None:
    turns = _turns_from_fixture(alpha_vantage_transcript_fixture)
    insights = build_transcript_insights(
        turns=turns,
        earnings_context=EarningsContext(
            symbol="IBM",
            quarter="2024Q1",
            resolved_quarter="2024Q1",
            fiscal_date_ending="2024-03-31",
            reported_date="2024-04-24",
            reported_eps="1.68",
        ),
        sec_verification=SecVerification(matched_form="10-Q", filing_date="2024-05-03"),
    )
    assert insights.guidance_passages
    assert insights.risk_passages
    assert "Ticker: IBM" in insights.condensed_context


def test_heuristic_analysis_generates_signal(alpha_vantage_transcript_fixture: dict) -> None:
    turns = _turns_from_fixture(alpha_vantage_transcript_fixture)
    context = EarningsContext(
        symbol="IBM",
        quarter="2024Q1",
        resolved_quarter="2024Q1",
        fiscal_date_ending="2024-03-31",
        reported_date="2024-04-24",
        reported_eps="1.68",
        estimated_eps="1.60",
        surprise="0.08",
        surprise_percentage="5.0",
    )
    sec = SecVerification(matched_form="10-Q", filing_date="2024-05-03")
    insights = build_transcript_insights(turns=turns, earnings_context=context, sec_verification=sec)
    analysis = build_heuristic_analysis(
        turns=turns,
        insights=insights,
        earnings_context=context,
        sec_verification=sec,
    )
    assert 0 <= analysis.signal_score <= 10
    assert analysis.sentiment in {"Bullish", "Neutral", "Bearish"}
    assert analysis.sentiment_rationale


def test_trend_dashboard_generates_flags(alpha_vantage_transcript_fixture: dict) -> None:
    turns = _turns_from_fixture(alpha_vantage_transcript_fixture)
    current_context = EarningsContext(
        symbol="IBM",
        quarter="2024Q1",
        resolved_quarter="2024Q1",
        fiscal_date_ending="2024-03-31",
        reported_date="2024-04-24",
        reported_eps="1.68",
        estimated_eps="1.60",
        surprise="0.08",
        surprise_percentage="5.0",
    )
    previous_context = EarningsContext(
        symbol="IBM",
        quarter="2023Q4",
        resolved_quarter="2023Q4",
        fiscal_date_ending="2023-12-31",
        reported_date="2024-01-24",
        reported_eps="3.87",
        estimated_eps="3.75",
        surprise="0.12",
        surprise_percentage="3.2",
    )
    sec = SecVerification(matched_form="10-Q", filing_date="2024-05-03")
    current_analysis = build_heuristic_analysis(
        turns=turns,
        insights=build_transcript_insights(turns, current_context, sec),
        earnings_context=current_context,
        sec_verification=sec,
    )
    previous_point = QuarterTrendPoint(
        quarter="2023Q4",
        signal_score=6.0,
        sentiment="Neutral",
        key_themes=["Guidance / outlook", "Demand / pipeline"],
    )
    dashboard = build_trend_dashboard(
        [
            build_trend_point(current_context, current_analysis, transcript_available=True),
            previous_point,
        ]
    )
    assert dashboard.momentum_flags
    assert dashboard.repeated_themes
