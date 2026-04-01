from __future__ import annotations

import json

from earnings_call_app.models import EarningsReport


def report_to_json(report: EarningsReport) -> str:
    return report.model_dump_json(indent=2)


def report_to_markdown(report: EarningsReport) -> str:
    lines = [
        f"# {report.ticker} Earnings Analysis",
        "",
        f"- Quarter: {report.quarter}",
        f"- Requested quarter: {report.requested_quarter or 'Latest available'}",
        f"- Mode: {report.mode}",
        f"- Analysis engine: {report.analysis_engine}",
        f"- Sentiment score: {report.analysis.signal_score}/10",
        f"- Sentiment: {report.analysis.sentiment}",
        "",
        "## Summary",
        report.analysis.summary,
        "",
        "## Sentiment Rationale",
        report.analysis.sentiment_rationale,
        "",
        "## Key Themes",
    ]
    lines.extend(f"- {item}" for item in report.analysis.key_themes)
    lines.extend(["", "## Financial Highlights"])
    lines.extend(f"- {item}" for item in report.analysis.financial_highlights)
    lines.extend(["", "## Guidance"])
    lines.extend(f"- {item}" for item in report.analysis.guidance)
    lines.extend(["", "## Risks"])
    lines.extend(f"- {item}" for item in report.analysis.risks)
    lines.extend(["", "## Q&A Highlights"])
    lines.extend(f"- {item}" for item in report.analysis.qa_highlights)
    if report.trend_dashboard and report.trend_dashboard.points:
        lines.extend(["", "## Trend Dashboard"])
        lines.extend(f"- {flag}" for flag in report.trend_dashboard.momentum_flags)
        if report.trend_dashboard.repeated_themes:
            lines.append(f"- Repeated themes: {', '.join(report.trend_dashboard.repeated_themes)}")
    lines.extend(["", "## Sources"])
    lines.extend(f"- {source.label}: {source.url}" for source in report.sources)
    if report.app_notes:
        lines.extend(["", "## App Notes"])
        lines.extend(f"- {note}" for note in report.app_notes)
    return "\n".join(lines)


def pretty_source_payload(report: EarningsReport) -> str:
    payload = {
        "ticker": report.ticker,
        "quarter": report.quarter,
        "sources": [source.model_dump() for source in report.sources],
        "sec_verification": report.sec_verification.model_dump() if report.sec_verification else None,
    }
    return json.dumps(payload, indent=2)
