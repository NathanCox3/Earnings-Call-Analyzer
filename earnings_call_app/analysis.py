from __future__ import annotations

import json
import re
from collections import Counter
from math import copysign

from openai import APIError, OpenAI, RateLimitError

from earnings_call_app.models import (
    AnalysisSummary,
    EarningsContext,
    QuarterTrendPoint,
    SecVerification,
    TranscriptInsights,
    TranscriptTurn,
    TrendDashboard,
)

QA_MARKERS = (
    "question-and-answer session",
    "first question",
    "our first question",
    "we will now take questions",
    "we will now begin the question-and-answer",
    "we will now begin the question and answer",
)

GUIDANCE_KEYWORDS = ("guidance", "outlook", "expect", "expects", "forecast", "reaffirm", "raise", "lower")
RISK_KEYWORDS = ("risk", "risks", "headwind", "pressure", "uncertain", "uncertainty", "macro", "competition", "regulatory")

THEME_KEYWORDS = {
    "AI / Product momentum": ("ai", "artificial intelligence", "product", "platform", "innovation", "gen ai"),
    "Demand / pipeline": ("demand", "pipeline", "bookings", "orders", "backlog", "consumption"),
    "Margins / profitability": ("margin", "profit", "expense", "cash flow", "efficiency", "operating leverage"),
    "Guidance / outlook": GUIDANCE_KEYWORDS,
    "Macro / risks": RISK_KEYWORDS,
}


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_transcript_sections(turns: list[TranscriptTurn]) -> tuple[list[TranscriptTurn], list[TranscriptTurn]]:
    prepared: list[TranscriptTurn] = []
    qa: list[TranscriptTurn] = []
    in_qa = False

    for turn in turns:
        content = turn.content.lower()
        speaker = turn.speaker.lower()
        if any(marker in content for marker in QA_MARKERS) or (
            speaker == "operator" and "question" in content
        ):
            in_qa = True

        section = "qa" if in_qa else "prepared_remarks"
        updated_turn = turn.model_copy(update={"section": section})
        if in_qa:
            qa.append(updated_turn)
        else:
            prepared.append(updated_turn)

    if not qa and len(turns) > 2:
        split_point = max(1, int(len(turns) * 0.7))
        prepared = [turn.model_copy(update={"section": "prepared_remarks"}) for turn in turns[:split_point]]
        qa = [turn.model_copy(update={"section": "qa"}) for turn in turns[split_point:]]

    return prepared, qa


def extract_keyword_passages(turns: list[TranscriptTurn], keywords: tuple[str, ...], limit: int = 3) -> list[str]:
    scored_passages: list[tuple[int, str]] = []
    for turn in turns:
        normalized = _normalize_whitespace(turn.content)
        lowered = normalized.lower()
        score = sum(lowered.count(keyword) for keyword in keywords)
        if score:
            scored_passages.append((score, normalized))

    scored_passages.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    unique_passages: list[str] = []
    seen: set[str] = set()
    for _, passage in scored_passages:
        if passage in seen:
            continue
        seen.add(passage)
        unique_passages.append(passage)
        if len(unique_passages) == limit:
            break
    return unique_passages


def build_transcript_insights(turns: list[TranscriptTurn], earnings_context: EarningsContext, sec_verification: SecVerification | None) -> TranscriptInsights:
    prepared, qa = split_transcript_sections(turns)
    guidance = extract_keyword_passages(turns, GUIDANCE_KEYWORDS)
    risks = extract_keyword_passages(turns, RISK_KEYWORDS)
    key_quotes = []
    for turn in prepared[:2] + qa[:2]:
        snippet = _normalize_whitespace(turn.content)
        if snippet:
            key_quotes.append(snippet[:280])

    speaker_counts = dict(Counter(turn.speaker for turn in turns))

    context_parts = [
        f"Ticker: {earnings_context.symbol}",
        f"Quarter: {earnings_context.resolved_quarter}",
    ]
    if earnings_context.reported_eps:
        context_parts.append(f"Reported EPS: {earnings_context.reported_eps}")
    if earnings_context.surprise_percentage:
        context_parts.append(f"EPS surprise %: {earnings_context.surprise_percentage}")
    if sec_verification and sec_verification.matched_form and sec_verification.filing_date:
        context_parts.append(
            f"SEC matched filing: {sec_verification.matched_form} filed {sec_verification.filing_date}"
        )
    if guidance:
        context_parts.append("Guidance passages:\n- " + "\n- ".join(guidance))
    if risks:
        context_parts.append("Risk passages:\n- " + "\n- ".join(risks))
    if prepared:
        context_parts.append("Prepared remarks excerpts:\n- " + "\n- ".join(_normalize_whitespace(turn.content)[:320] for turn in prepared[:4]))
    if qa:
        context_parts.append("Q&A excerpts:\n- " + "\n- ".join(_normalize_whitespace(turn.content)[:320] for turn in qa[:4]))

    return TranscriptInsights(
        prepared_remarks=prepared,
        qa=qa,
        guidance_passages=guidance,
        risk_passages=risks,
        key_quote_candidates=key_quotes,
        speaker_counts=speaker_counts,
        condensed_context="\n".join(context_parts),
    )


def _detect_theme_hits(turns: list[TranscriptTurn]) -> list[str]:
    joined = " ".join(turn.content.lower() for turn in turns)
    theme_scores = []
    for theme, keywords in THEME_KEYWORDS.items():
        score = sum(joined.count(keyword) for keyword in keywords)
        if score:
            theme_scores.append((score, theme))
    theme_scores.sort(reverse=True)
    return [theme for _, theme in theme_scores[:3]]


def _tone_label(turns: list[TranscriptTurn], earnings_context: EarningsContext) -> str:
    positive = 0
    negative = 0
    corpus = " ".join(turn.content.lower() for turn in turns)
    for keyword in ("strong", "healthy", "improved", "growth", "momentum", "expanded", "reiterated"):
        positive += corpus.count(keyword)
    for keyword in ("pressure", "headwind", "uncertain", "cautious", "softness", "risk"):
        negative += corpus.count(keyword)
    if earnings_context.surprise and earnings_context.surprise.startswith("-"):
        negative += 1
    elif earnings_context.surprise:
        positive += 1
    if positive >= negative + 2:
        return "Constructive"
    if negative >= positive + 2:
        return "Cautious"
    return "Balanced / mixed"


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace("%", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def _score_sentiment(
    turns: list[TranscriptTurn],
    themes: list[str],
    guidance: list[str],
    risks: list[str],
    earnings_context: EarningsContext,
    sec_verification: SecVerification | None,
) -> tuple[float, str, str]:
    score = 5.0
    tone = _tone_label(turns, earnings_context)
    surprise_pct = _to_float(earnings_context.surprise_percentage)

    if tone == "Constructive":
        score += 1.4
    elif tone == "Cautious":
        score -= 1.4

    if surprise_pct is not None and surprise_pct != 0:
        score += copysign(min(abs(surprise_pct) / 5.0, 1.5), surprise_pct)

    if "AI / Product momentum" in themes:
        score += 0.6
    if "Demand / pipeline" in themes:
        score += 0.5
    if "Margins / profitability" in themes:
        score += 0.4
    if "Macro / risks" in themes:
        score -= 0.6

    score += min(len(guidance) * 0.35, 0.9)
    score -= min(len(risks) * 0.45, 1.35)

    if sec_verification and sec_verification.metrics:
        score += 0.25
    if sec_verification and sec_verification.notes:
        score -= 0.2

    score = round(_clamp(score), 1)

    if score >= 7.0:
        sentiment = "Bullish"
    elif score <= 3.0:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral"

    rationale_parts = [f"The heuristic sentiment lands at {score}/10 based on {tone.lower()} earnings commentary"]
    if surprise_pct is not None:
        direction = "positive" if surprise_pct >= 0 else "negative"
        rationale_parts.append(f"a {direction} EPS surprise")
    if guidance:
        rationale_parts.append("management guidance language")
    if risks:
        rationale_parts.append("risk commentary that tempers the tone")
    rationale = ", ".join(rationale_parts) + "."
    return score, sentiment, rationale


def build_heuristic_analysis(
    turns: list[TranscriptTurn],
    insights: TranscriptInsights,
    earnings_context: EarningsContext,
    sec_verification: SecVerification | None,
) -> AnalysisSummary:
    themes = _detect_theme_hits(turns)
    financial_highlights = []
    if earnings_context.reported_eps:
        eps_line = f"Reported EPS was {earnings_context.reported_eps}"
        if earnings_context.estimated_eps:
            eps_line += f" versus an estimate of {earnings_context.estimated_eps}"
        if earnings_context.surprise_percentage:
            eps_line += f" ({earnings_context.surprise_percentage} surprise)."
        else:
            eps_line += "."
        financial_highlights.append(eps_line)
    if sec_verification and sec_verification.metrics:
        for metric in sec_verification.metrics:
            unit = f" {metric.unit}" if metric.unit else ""
            financial_highlights.append(
                f"SEC company facts matched {metric.label.lower()} of {metric.value}{unit} for period end {metric.period_end}."
            )
    if not financial_highlights:
        financial_highlights.append("Live numeric verification was limited, so this view leans more heavily on transcript commentary.")

    guidance = insights.guidance_passages or [
        "No explicit guidance passage was detected with the local heuristic rules."
    ]
    risks = insights.risk_passages or [
        "No strong risk passage was detected with the local heuristic rules."
    ]

    qa_highlights = []
    for turn in insights.qa[:3]:
        if turn.speaker.lower() == "operator":
            continue
        qa_highlights.append(f"{turn.speaker}: {_normalize_whitespace(turn.content)[:220]}")
    if not qa_highlights:
        qa_highlights.append("The transcript did not expose a clearly segmented Q&A portion.")

    summary = (
        f"{earnings_context.symbol} {earnings_context.resolved_quarter} commentary centered on "
        f"{', '.join(theme.lower() for theme in themes) if themes else 'operational execution and outlook'}. "
        "The local analyzer combined transcript heuristics with SEC verification where available."
    )

    sources = ["Alpha Vantage transcript", "Local heuristic analysis"]
    confidence_notes = [
        "Heuristic mode uses keyword extraction and transcript segmentation rather than full reasoning over the entire call."
    ]
    if sec_verification and sec_verification.filing_url:
        sources.append("SEC filing verification")
    else:
        confidence_notes.append("SEC verification could not fully match a filing for this quarter.")

    signal_score, sentiment, rationale = _score_sentiment(
        turns=turns,
        themes=themes,
        guidance=guidance,
        risks=risks,
        earnings_context=earnings_context,
        sec_verification=sec_verification,
    )
    confidence_notes.append(
        "The 0-10 score and bullish/bearish sentiment label are heuristic summaries of call tone, not investment advice or a price target."
    )

    return AnalysisSummary(
        summary=summary,
        signal_score=signal_score,
        sentiment=sentiment,
        sentiment_rationale=rationale,
        key_themes=themes or ["Operational execution / outlook"],
        financial_highlights=financial_highlights,
        guidance=guidance,
        risks=risks,
        qa_highlights=qa_highlights,
        tone=_tone_label(turns, earnings_context),
        sources=sources,
        confidence_notes=confidence_notes,
    )


def build_trend_point(
    earnings_context: EarningsContext,
    analysis: AnalysisSummary | None,
    transcript_available: bool,
    note: str | None = None,
) -> QuarterTrendPoint:
    if analysis is None:
        return QuarterTrendPoint(
            quarter=earnings_context.resolved_quarter,
            fiscal_date_ending=earnings_context.fiscal_date_ending,
            reported_date=earnings_context.reported_date,
            reported_eps=earnings_context.reported_eps,
            estimated_eps=earnings_context.estimated_eps,
            surprise_percentage=earnings_context.surprise_percentage,
            transcript_available=transcript_available,
            note=note,
        )

    return QuarterTrendPoint(
        quarter=earnings_context.resolved_quarter,
        fiscal_date_ending=earnings_context.fiscal_date_ending,
        reported_date=earnings_context.reported_date,
        reported_eps=earnings_context.reported_eps,
        estimated_eps=earnings_context.estimated_eps,
        surprise_percentage=earnings_context.surprise_percentage,
        signal_score=analysis.signal_score,
        sentiment=analysis.sentiment,
        tone=analysis.tone,
        key_themes=analysis.key_themes,
        transcript_available=transcript_available,
        note=note,
    )


def build_trend_dashboard(points: list[QuarterTrendPoint], note: str | None = None) -> TrendDashboard:
    valid_points = [point for point in points if point.signal_score is not None]
    theme_counts = Counter(
        theme
        for point in valid_points
        for theme in point.key_themes
    )
    repeated_themes = [
        theme for theme, count in theme_counts.most_common()
        if count >= 2
    ][:5]

    momentum_flags: list[str] = []
    if len(valid_points) >= 2:
        latest = valid_points[0]
        previous = valid_points[1]
        delta = round((latest.signal_score or 0) - (previous.signal_score or 0), 1)
        if abs(delta) >= 0.5:
            direction = "up" if delta > 0 else "down"
            momentum_flags.append(
                f"Sentiment score is {direction} {abs(delta):.1f} points versus the prior quarter."
            )
        if latest.sentiment != previous.sentiment:
            momentum_flags.append(
                f"Sentiment changed from {previous.sentiment} to {latest.sentiment}."
            )
        new_themes = [theme for theme in latest.key_themes if theme not in previous.key_themes]
        if new_themes:
            momentum_flags.append(
                f"New focus areas versus last quarter: {', '.join(new_themes[:2])}."
            )

    if not momentum_flags and valid_points:
        momentum_flags.append("Sentiment signals are broadly stable versus the prior quarter.")

    if not repeated_themes and valid_points:
        repeated_themes = valid_points[0].key_themes[:3]

    return TrendDashboard(
        points=points,
        repeated_themes=repeated_themes,
        momentum_flags=momentum_flags,
        note=note,
    )


def parse_analysis_payload(raw_text: str) -> AnalysisSummary:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")

    payload = json.loads(cleaned[start : end + 1])
    return AnalysisSummary.model_validate(payload)


def run_openai_analysis(
    api_key: str,
    model: str,
    insights: TranscriptInsights,
    earnings_context: EarningsContext,
    sec_verification: SecVerification | None,
    fallback: AnalysisSummary,
) -> tuple[AnalysisSummary, str]:
    client = OpenAI(api_key=api_key)
    prompt = f"""
You are an equity research assistant. Return a JSON object only, with keys:
summary, signal_score, sentiment, sentiment_rationale, key_themes, financial_highlights, guidance, risks, qa_highlights, tone, sources, confidence_notes.

Constraints:
- Be faithful to the transcript and SEC verification only.
- Use concise bullets in arrays.
- Mention uncertainty when evidence is thin.
- Treat `signal_score` as a heuristic sentiment score from 0 to 10, where 0 is most bearish, 5 is neutral, and 10 is most bullish.
- `sentiment` must be one of Bullish, Neutral, or Bearish.
- Make `sentiment_rationale` a short explanatory sentence, and explicitly avoid sounding certain about future price action.
- Do not include markdown fences.

Structured context:
{insights.condensed_context}

Earnings context:
{earnings_context.model_dump_json(indent=2)}

SEC verification:
{sec_verification.model_dump_json(indent=2) if sec_verification else "null"}

Fallback local analysis:
{fallback.model_dump_json(indent=2)}
""".strip()

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=1200,
        )
        output_text = getattr(response, "output_text", "") or ""
        parsed = parse_analysis_payload(output_text)
        if "OpenAI structured synthesis" not in parsed.sources:
            parsed.sources.append("OpenAI structured synthesis")
        return parsed, model
    except (RateLimitError, APIError, ValueError, json.JSONDecodeError) as exc:
        recovered = fallback.model_copy(deep=True)
        recovered.confidence_notes.append(
            f"OpenAI synthesis fell back to local heuristics because parsing or API execution failed: {exc}"
        )
        return recovered, f"{model} (fallback to local heuristics)"
