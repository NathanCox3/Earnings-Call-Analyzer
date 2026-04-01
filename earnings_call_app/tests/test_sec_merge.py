from __future__ import annotations

from earnings_call_app.sec import extract_metrics, find_matching_filing


def test_find_matching_filing_returns_quarter_match(sec_submissions_fixture: dict) -> None:
    filing = find_matching_filing(sec_submissions_fixture, "2024Q1")
    assert filing is not None
    assert filing["form"] == "10-Q"
    assert filing["report_date"] == "2024-03-31"


def test_extract_metrics_reads_companyfacts(sec_companyfacts_fixture: dict) -> None:
    metrics = extract_metrics(
        sec_companyfacts_fixture,
        report_date="2024-03-31",
        companyfacts_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000051143.json",
    )
    labels = {metric.label for metric in metrics}
    assert "Revenue" in labels
    assert "Net income" in labels
