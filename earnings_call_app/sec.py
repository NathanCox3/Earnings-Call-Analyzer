from __future__ import annotations

from functools import lru_cache

import requests

from earnings_call_app.models import FinancialMetric, SecVerification

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

METRIC_CANDIDATES = {
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "Net income": ["NetIncomeLoss"],
    "Diluted EPS": ["EarningsPerShareDiluted", "DilutedEarningsPerShare"],
}


class SecApiError(RuntimeError):
    """Raised when SEC data cannot be fetched or matched."""


def _headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def _quarter_match(date_string: str, quarter_code: str) -> bool:
    year, month, _ = [int(part) for part in date_string.split("-")]
    quarter = ((month - 1) // 3) + 1
    return quarter_code == f"{year}Q{quarter}"


@lru_cache(maxsize=1)
def get_company_tickers(user_agent: str) -> dict:
    response = requests.get(SEC_TICKERS_URL, headers=_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.json()


def get_cik_and_name_for_ticker(ticker: str, user_agent: str) -> tuple[str, str]:
    payload = get_company_tickers(user_agent)
    upper_ticker = ticker.upper()
    for item in payload.values():
        if item.get("ticker", "").upper() == upper_ticker:
            cik = str(item["cik_str"]).zfill(10)
            return cik, item["title"]
    raise SecApiError(f"Ticker {upper_ticker} was not found in the SEC ticker map.")


@lru_cache(maxsize=64)
def get_submissions(cik: str, user_agent: str) -> dict:
    response = requests.get(
        SEC_SUBMISSIONS_URL.format(cik=cik),
        headers=_headers(user_agent),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=64)
def get_company_facts(cik: str, user_agent: str) -> dict:
    response = requests.get(
        SEC_COMPANYFACTS_URL.format(cik=cik),
        headers=_headers(user_agent),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _build_filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    accession_digits = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_digits}/{primary_document}"


def find_matching_filing(submissions: dict, quarter_code: str) -> dict | None:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])

    for index, form in enumerate(forms):
        report_date = report_dates[index] if index < len(report_dates) else ""
        filing_date = filing_dates[index] if index < len(filing_dates) else ""
        if not report_date:
            continue
        if form not in {"10-Q", "10-K", "10-Q/A", "10-K/A"}:
            continue
        if _quarter_match(report_date, quarter_code):
            return {
                "form": form,
                "filing_date": filing_date,
                "report_date": report_date,
                "accession_number": accessions[index] if index < len(accessions) else "",
                "primary_document": primary_documents[index] if index < len(primary_documents) else "",
            }
    return None


def _select_metric_entries(companyfacts: dict, concepts: list[str], report_date: str) -> list[dict]:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    matches: list[dict] = []
    for concept in concepts:
        concept_block = facts.get(concept) or {}
        for unit_entries in concept_block.get("units", {}).values():
            for entry in unit_entries:
                if entry.get("end") == report_date and entry.get("form") in {"10-Q", "10-K", "10-Q/A", "10-K/A"}:
                    enriched = dict(entry)
                    enriched["concept"] = concept
                    matches.append(enriched)
    matches.sort(key=lambda item: item.get("filed", ""), reverse=True)
    return matches


def extract_metrics(companyfacts: dict, report_date: str, companyfacts_url: str) -> list[FinancialMetric]:
    metrics: list[FinancialMetric] = []
    for label, concepts in METRIC_CANDIDATES.items():
        entries = _select_metric_entries(companyfacts, concepts, report_date)
        if not entries:
            continue
        chosen = entries[0]
        metrics.append(
            FinancialMetric(
                label=label,
                value=str(chosen.get("val")),
                unit=next(
                    iter(
                        companyfacts.get("facts", {})
                        .get("us-gaap", {})
                        .get(chosen["concept"], {})
                        .get("units", {})
                        .keys()
                    ),
                    None,
                ),
                period_end=chosen.get("end"),
                source_url=companyfacts_url,
            )
        )
    return metrics


def build_sec_verification(ticker: str, quarter_code: str, user_agent: str) -> SecVerification:
    cik, company_name = get_cik_and_name_for_ticker(ticker, user_agent)
    submissions = get_submissions(cik, user_agent)
    filing = find_matching_filing(submissions, quarter_code)

    if not filing:
        return SecVerification(
            company_name=company_name,
            cik=cik,
            companyfacts_url=SEC_COMPANYFACTS_URL.format(cik=cik),
            notes=[f"No 10-Q or 10-K filing matched {quarter_code} in SEC submissions."],
        )

    companyfacts_url = SEC_COMPANYFACTS_URL.format(cik=cik)
    companyfacts = get_company_facts(cik, user_agent)
    filing_url = _build_filing_url(cik, filing["accession_number"], filing["primary_document"])
    metrics = extract_metrics(companyfacts, filing["report_date"], companyfacts_url)

    notes = []
    if not metrics:
        notes.append("SEC filing was matched, but no headline company facts were found for the requested quarter.")

    return SecVerification(
        company_name=company_name,
        cik=cik,
        matched_form=filing["form"],
        filing_date=filing["filing_date"],
        report_date=filing["report_date"],
        filing_url=filing_url,
        companyfacts_url=companyfacts_url,
        metrics=metrics,
        notes=notes,
    )
