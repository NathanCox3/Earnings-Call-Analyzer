from __future__ import annotations

from functools import lru_cache
import time

import requests

from earnings_call_app.models import EarningsContext, TranscriptTurn

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


class AlphaVantageError(RuntimeError):
    """Raised when Alpha Vantage returns an application-level error."""


def normalize_quarter_code(value: str) -> str:
    cleaned = value.strip().upper().replace("-", "").replace(" ", "")
    if len(cleaned) == 6 and cleaned[4] == "Q" and cleaned[-1] in "1234":
        return cleaned
    raise ValueError("Quarter must look like YYYYQ1, YYYYQ2, YYYYQ3, or YYYYQ4.")


def fiscal_date_to_quarter(fiscal_date: str) -> str:
    year, month, _ = [int(part) for part in fiscal_date.split("-")]
    quarter = ((month - 1) // 3) + 1
    return f"{year}Q{quarter}"


def _api_key_or_demo(api_key: str | None) -> str:
    return api_key or "demo"


@lru_cache(maxsize=64)
def _fetch_alpha_vantage(function_name: str, symbol: str, quarter: str | None, api_key: str | None) -> dict:
    params = {
        "function": function_name,
        "symbol": symbol.upper(),
        "apikey": _api_key_or_demo(api_key),
    }
    if quarter:
        params["quarter"] = quarter

    for attempt in range(3):
        response = requests.get(ALPHA_VANTAGE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            info_message = payload.get("Information") or payload.get("Note")
            if info_message:
                lowered = info_message.lower()
                if (
                    "1 request per second" in lowered
                    or "please consider spreading out your free api requests" in lowered
                ) and attempt < 2:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise AlphaVantageError(info_message)
            if payload.get("Error Message"):
                raise AlphaVantageError(payload["Error Message"])

        return payload

    raise AlphaVantageError("Alpha Vantage request failed after retries.")


def get_earnings(symbol: str, api_key: str | None) -> dict:
    return _fetch_alpha_vantage("EARNINGS", symbol, None, api_key)


def _context_from_quarterly_item(symbol: str, item: dict) -> EarningsContext:
    resolved = fiscal_date_to_quarter(item["fiscalDateEnding"])
    return EarningsContext(
        symbol=symbol.upper(),
        quarter=resolved,
        resolved_quarter=resolved,
        fiscal_date_ending=item.get("fiscalDateEnding"),
        reported_date=item.get("reportedDate"),
        reported_eps=item.get("reportedEPS"),
        estimated_eps=item.get("estimatedEPS"),
        surprise=item.get("surprise"),
        surprise_percentage=item.get("surprisePercentage"),
    )


def list_recent_quarter_contexts(symbol: str, api_key: str | None, limit: int = 4) -> list[EarningsContext]:
    earnings_payload = get_earnings(symbol, api_key)
    quarterly = earnings_payload.get("quarterlyEarnings") or []
    if not quarterly:
        raise AlphaVantageError(f"No quarterly earnings data returned for {symbol.upper()}.")
    return [_context_from_quarterly_item(symbol, item) for item in quarterly[:limit]]


def resolve_quarter(symbol: str, requested_quarter: str | None, api_key: str | None) -> EarningsContext:
    earnings_payload = get_earnings(symbol, api_key)
    quarterly = earnings_payload.get("quarterlyEarnings") or []
    if not quarterly:
        raise AlphaVantageError(f"No quarterly earnings data returned for {symbol.upper()}.")

    if requested_quarter:
        normalized = normalize_quarter_code(requested_quarter)
        for item in quarterly:
            if fiscal_date_to_quarter(item["fiscalDateEnding"]) == normalized:
                return _context_from_quarterly_item(symbol, item)
        raise AlphaVantageError(f"No quarterly earnings match found for {symbol.upper()} {normalized}.")

    return _context_from_quarterly_item(symbol, quarterly[0])


def get_transcript(symbol: str, quarter: str, api_key: str | None) -> list[TranscriptTurn]:
    payload = _fetch_alpha_vantage(
        "EARNINGS_CALL_TRANSCRIPT",
        symbol,
        normalize_quarter_code(quarter),
        api_key,
    )
    transcript_items = payload.get("transcript") or []
    if not transcript_items:
        raise AlphaVantageError(
            f"No transcript returned for {symbol.upper()} {normalize_quarter_code(quarter)}."
        )

    return [
        TranscriptTurn(
            speaker=(item.get("speaker") or "Unknown Speaker").strip(),
            title=(item.get("title") or None),
            content=(item.get("content") or "").strip(),
        )
        for item in transcript_items
        if (item.get("content") or "").strip()
    ]
