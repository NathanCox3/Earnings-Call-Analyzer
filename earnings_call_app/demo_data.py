from __future__ import annotations

from earnings_call_app.models import (
    AnalysisSummary,
    EarningsContext,
    EarningsReport,
    QuarterTrendPoint,
    SecVerification,
    SourceLink,
    TranscriptInsights,
    TranscriptTurn,
    TrendDashboard,
)


def build_demo_trend_dashboard() -> TrendDashboard:
    points = [
        QuarterTrendPoint(
            quarter="2024Q1",
            fiscal_date_ending="2024-03-31",
            reported_date="2024-04-24",
            reported_eps="1.68",
            estimated_eps="1.60",
            surprise_percentage="5.0",
            signal_score=7.2,
            sentiment="Bullish",
            tone="Constructive but measured",
            key_themes=["AI / Product momentum", "Margins / profitability", "Demand / pipeline"],
        ),
        QuarterTrendPoint(
            quarter="2023Q4",
            fiscal_date_ending="2023-12-31",
            reported_date="2024-01-24",
            reported_eps="3.87",
            estimated_eps="3.75",
            surprise_percentage="3.2",
            signal_score=6.8,
            sentiment="Neutral",
            tone="Constructive",
            key_themes=["AI / Product momentum", "Demand / pipeline", "Guidance / outlook"],
        ),
        QuarterTrendPoint(
            quarter="2023Q3",
            fiscal_date_ending="2023-09-30",
            reported_date="2023-10-25",
            reported_eps="2.20",
            estimated_eps="2.13",
            surprise_percentage="3.3",
            signal_score=6.4,
            sentiment="Neutral",
            tone="Balanced / mixed",
            key_themes=["Margins / profitability", "Demand / pipeline", "Macro / risks"],
        ),
        QuarterTrendPoint(
            quarter="2023Q2",
            fiscal_date_ending="2023-06-30",
            reported_date="2023-07-19",
            reported_eps="2.18",
            estimated_eps="2.01",
            surprise_percentage="8.5",
            signal_score=6.0,
            sentiment="Neutral",
            tone="Balanced / mixed",
            key_themes=["Margins / profitability", "Guidance / outlook", "Macro / risks"],
        ),
    ]
    return TrendDashboard(
        points=points,
        repeated_themes=["AI / Product momentum", "Demand / pipeline", "Margins / profitability"],
        momentum_flags=[
            "Sentiment score is up 0.4 points versus the prior quarter.",
            "Sentiment changed from Neutral to Bullish.",
            "New focus areas versus last quarter: AI / Product momentum.",
        ],
        note="Demo trend data is bundled locally to keep the dashboard testable without live API calls.",
    )


def build_demo_report(requested_ticker: str, requested_quarter: str | None) -> EarningsReport:
    ticker = requested_ticker.upper() or "IBM"
    quarter = requested_quarter or "2024Q1"

    transcript_turns = [
        TranscriptTurn(
            speaker="Olympia McNerney",
            title="Global Head of Investor Relations",
            section="prepared_remarks",
            content=(
                "Welcome to IBM's first quarter 2024 earnings presentation. "
                "We will review the quarter, our strategic progress, and the outlook."
            ),
        ),
        TranscriptTurn(
            speaker="Arvind Krishna",
            title="Chairman and Chief Executive Officer",
            section="prepared_remarks",
            content=(
                "Demand for hybrid cloud and AI remained healthy, consulting execution improved, "
                "and management reiterated its full-year free cash flow outlook."
            ),
        ),
        TranscriptTurn(
            speaker="Jim Kavanaugh",
            title="Senior Vice President and Chief Financial Officer",
            section="prepared_remarks",
            content=(
                "Software mix and productivity actions supported margin expansion. "
                "Management expects continued revenue growth, but noted a cautious macro backdrop."
            ),
        ),
        TranscriptTurn(
            speaker="Operator",
            title=None,
            section="qa",
            content="We will now begin the question-and-answer session. Our first question comes from Amit Daryanani.",
        ),
        TranscriptTurn(
            speaker="Amit Daryanani",
            title="Evercore ISI",
            section="qa",
            content=(
                "Can you talk about the pace of generative AI bookings and whether that changes the second-half outlook?"
            ),
        ),
        TranscriptTurn(
            speaker="Arvind Krishna",
            title="Chairman and Chief Executive Officer",
            section="qa",
            content=(
                "The AI pipeline continues to expand, and while we are encouraged by demand, "
                "we are staying disciplined about what we include in formal guidance."
            ),
        ),
    ]

    transcript_insights = TranscriptInsights(
        prepared_remarks=[turn for turn in transcript_turns if turn.section == "prepared_remarks"],
        qa=[turn for turn in transcript_turns if turn.section == "qa"],
        guidance_passages=[
            "Management reiterated its full-year free cash flow outlook.",
            "Management expects continued revenue growth, but noted a cautious macro backdrop.",
        ],
        risk_passages=[
            "Management expects continued revenue growth, but noted a cautious macro backdrop.",
            "We are staying disciplined about what we include in formal guidance.",
        ],
        key_quote_candidates=[
            "Demand for hybrid cloud and AI remained healthy.",
            "The AI pipeline continues to expand.",
        ],
        speaker_counts={
            "Olympia McNerney": 1,
            "Arvind Krishna": 2,
            "Jim Kavanaugh": 1,
            "Operator": 1,
            "Amit Daryanani": 1,
        },
        condensed_context=(
            "Ticker: IBM\nQuarter: 2024Q1\nPrepared remarks emphasized hybrid cloud, AI demand, "
            "margin support, and reiterated free cash flow guidance. Q&A focused on AI bookings and guidance discipline."
        ),
    )

    analysis = AnalysisSummary(
        summary=(
            "Demo mode shows a balanced quarter where management emphasized resilient software and AI demand, "
            "supported margins, and reiterated full-year cash flow expectations while still acknowledging macro caution."
        ),
        signal_score=7.2,
        sentiment="Bullish",
        sentiment_rationale=(
            "The heuristic lands in moderately bullish territory because management commentary stayed constructive, "
            "the EPS setup was favorable, and growth themes outweighed the macro caution."
        ),
        key_themes=[
            "AI and hybrid cloud remained the centerpiece of management's narrative.",
            "Margin improvement was framed as a mix and productivity story rather than pure topline acceleration.",
            "Guidance stayed constructive, but leadership kept a conservative tone around the macro environment.",
        ],
        financial_highlights=[
            "Demo context points to stable growth and reiterated free cash flow expectations.",
            "Prepared remarks highlighted margin support from software mix and productivity actions.",
        ],
        guidance=[
            "Management reiterated its full-year free cash flow outlook.",
            "Leadership signaled continued revenue growth expectations.",
        ],
        risks=[
            "Macro caution remained visible in management commentary.",
            "Leadership was careful not to over-commit fast-moving AI demand into formal guidance.",
        ],
        qa_highlights=[
            "Analysts pressed on AI bookings and how quickly pipeline momentum should influence guidance.",
            "Management responded positively on demand but stayed conservative on formal forecast changes.",
        ],
        tone="Constructive but measured",
        sources=[
            "Bundled IBM-inspired demo transcript",
            "Bundled SEC verification sample",
        ],
        confidence_notes=[
            "This is local demo data intended to exercise the UI without any network or API dependency.",
            "The 0-10 score and bullish/bearish sentiment label are heuristic summaries of call tone, not investment advice or a price target.",
        ],
    )

    sec_verification = SecVerification(
        company_name="International Business Machines Corporation",
        cik="51143",
        matched_form="10-Q",
        filing_date="2024-05-03",
        report_date="2024-03-31",
        filing_url="https://www.sec.gov/Archives/edgar/data/51143/000005114324000014/ibm-20240331.htm",
        companyfacts_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000051143.json",
        metrics=[],
        notes=["Demo SEC verification is illustrative and bundled with the app."],
    )

    return EarningsReport(
        ticker=ticker,
        quarter="2024Q1",
        requested_quarter=quarter,
        company_name="International Business Machines Corporation",
        mode="Demo",
        analysis_engine="Bundled demo data",
        earnings_context=EarningsContext(
            symbol=ticker,
            quarter=quarter,
            resolved_quarter="2024Q1",
            fiscal_date_ending="2024-03-31",
            reported_date="2024-04-24",
            reported_eps="1.68",
            estimated_eps="1.60",
            surprise="0.08",
            surprise_percentage="5.0",
        ),
        transcript_turns=transcript_turns,
        transcript_insights=transcript_insights,
        analysis=analysis,
        trend_dashboard=build_demo_trend_dashboard(),
        sec_verification=sec_verification,
        sources=[
            SourceLink(
                label="Bundled demo transcript",
                url="https://www.alphavantage.co/documentation/",
                source_type="demo",
                note="Used only in Demo mode.",
            ),
            SourceLink(
                label="Bundled SEC sample",
                url="https://www.sec.gov/os/accessing-edgar-data",
                source_type="demo",
                note="Used only in Demo mode.",
            ),
        ],
        app_notes=[
            "Demo mode always renders a local IBM-style quarter so the UI remains testable without live credentials.",
            "The displayed sentiment score and label are informational heuristics based on call tone, not investment advice.",
        ],
    )
