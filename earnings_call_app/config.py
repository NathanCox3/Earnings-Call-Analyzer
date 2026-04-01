from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))


@dataclass(frozen=True)
class AppConfig:
    alpha_vantage_api_key: str | None
    openai_api_key: str | None
    openai_model: str
    sec_user_agent: str


def get_config() -> AppConfig:
    return AppConfig(
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("EARNINGS_OPENAI_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-5-mini",
        sec_user_agent=os.getenv(
            "SEC_USER_AGENT",
            "earnings-call-analyzer/1.0 earnings@example.com",
        ),
    )
