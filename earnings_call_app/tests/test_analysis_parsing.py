from __future__ import annotations

import pytest

from earnings_call_app.analysis import parse_analysis_payload


def test_parse_analysis_payload_accepts_fenced_json() -> None:
    raw = """```json
    {
      "summary": "A concise summary.",
      "signal_score": 7.4,
      "sentiment": "Bullish",
      "sentiment_rationale": "Constructive tone and favorable surprise support a modestly bullish signal.",
      "key_themes": ["Theme A"],
      "financial_highlights": ["EPS beat consensus."],
      "guidance": ["Guidance reiterated."],
      "risks": ["Macro risk remains."],
      "qa_highlights": ["AI demand came up in Q&A."],
      "tone": "Constructive",
      "sources": ["Alpha Vantage transcript"],
      "confidence_notes": ["Model used condensed context."]
    }
    ```"""
    parsed = parse_analysis_payload(raw)
    assert parsed.tone == "Constructive"
    assert parsed.key_themes == ["Theme A"]
    assert parsed.signal_score == 7.4
    assert parsed.sentiment == "Bullish"


def test_parse_analysis_payload_raises_without_json() -> None:
    with pytest.raises(ValueError):
        parse_analysis_payload("not-json")
