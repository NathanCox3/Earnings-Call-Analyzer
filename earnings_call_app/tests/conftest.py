from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def alpha_vantage_transcript_fixture() -> dict:
    return load_fixture("alpha_vantage_ibm_transcript.json")


@pytest.fixture
def sec_submissions_fixture() -> dict:
    return load_fixture("sec_submissions_ibm.json")


@pytest.fixture
def sec_companyfacts_fixture() -> dict:
    return load_fixture("sec_companyfacts_ibm.json")
