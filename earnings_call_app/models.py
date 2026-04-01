from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


AnalysisMode = Literal["Demo", "Free Data Only", "Free Data + OpenAI"]
SentimentLabel = Literal["Bullish", "Neutral", "Bearish"]


class TranscriptTurn(BaseModel):
    speaker: str
    title: str | None = None
    content: str
    section: Literal["prepared_remarks", "qa"] = "prepared_remarks"


class SourceLink(BaseModel):
    label: str
    url: str
    source_type: Literal["alpha_vantage", "sec", "openai", "demo", "app"]
    note: str | None = None


class FinancialMetric(BaseModel):
    label: str
    value: str
    unit: str | None = None
    period_end: str | None = None
    source_url: str | None = None


class SecVerification(BaseModel):
    company_name: str | None = None
    cik: str | None = None
    matched_form: str | None = None
    filing_date: str | None = None
    report_date: str | None = None
    filing_url: str | None = None
    companyfacts_url: str | None = None
    metrics: list[FinancialMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    summary: str
    signal_score: float = Field(ge=0, le=10)
    sentiment: SentimentLabel = Field(
        validation_alias=AliasChoices("sentiment", "recommendation")
    )
    sentiment_rationale: str = Field(
        validation_alias=AliasChoices("sentiment_rationale", "rating_rationale")
    )
    key_themes: list[str] = Field(default_factory=list)
    financial_highlights: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    qa_highlights: list[str] = Field(default_factory=list)
    tone: str
    sources: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)


class EarningsContext(BaseModel):
    symbol: str
    quarter: str
    resolved_quarter: str
    fiscal_date_ending: str | None = None
    reported_date: str | None = None
    reported_eps: str | None = None
    estimated_eps: str | None = None
    surprise: str | None = None
    surprise_percentage: str | None = None


class TranscriptInsights(BaseModel):
    prepared_remarks: list[TranscriptTurn] = Field(default_factory=list)
    qa: list[TranscriptTurn] = Field(default_factory=list)
    guidance_passages: list[str] = Field(default_factory=list)
    risk_passages: list[str] = Field(default_factory=list)
    key_quote_candidates: list[str] = Field(default_factory=list)
    speaker_counts: dict[str, int] = Field(default_factory=dict)
    condensed_context: str


class QuarterTrendPoint(BaseModel):
    quarter: str
    fiscal_date_ending: str | None = None
    reported_date: str | None = None
    reported_eps: str | None = None
    estimated_eps: str | None = None
    surprise_percentage: str | None = None
    signal_score: float | None = Field(default=None, ge=0, le=10)
    sentiment: SentimentLabel | Literal["Unavailable"] = Field(
        default="Unavailable",
        validation_alias=AliasChoices("sentiment", "recommendation"),
    )
    tone: str | None = None
    key_themes: list[str] = Field(default_factory=list)
    transcript_available: bool = True
    note: str | None = None


class TrendDashboard(BaseModel):
    points: list[QuarterTrendPoint] = Field(default_factory=list)
    repeated_themes: list[str] = Field(default_factory=list)
    momentum_flags: list[str] = Field(default_factory=list)
    note: str | None = None


class EarningsReport(BaseModel):
    ticker: str
    quarter: str
    requested_quarter: str
    company_name: str | None = None
    mode: AnalysisMode
    analysis_engine: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    transcript_turns: list[TranscriptTurn] = Field(default_factory=list)
    earnings_context: EarningsContext
    transcript_insights: TranscriptInsights
    analysis: AnalysisSummary
    trend_dashboard: TrendDashboard | None = None
    sec_verification: SecVerification | None = None
    sources: list[SourceLink] = Field(default_factory=list)
    app_notes: list[str] = Field(default_factory=list)
