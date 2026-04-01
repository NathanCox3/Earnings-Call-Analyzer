# Earnings Call Analyzer

A Streamlit app for reading and comparing earnings calls using free data sources. It pulls transcript and earnings context from Alpha Vantage, verifies filings with SEC EDGAR when available, and produces a concise sentiment summary with a 0 to 10 score where 0 is most bearish and 10 is most bullish.

## What It Does

- Analyzes one ticker and quarter at a time.
- Extracts prepared remarks, Q&A, themes, guidance, risks, and key quotes.
- Renders a sentiment score, sentiment label, and rationale.
- Shows a 4-quarter trend dashboard so you can compare the latest call against recent history.
- Exports JSON and Markdown reports.

## Modes

- `Demo`: bundled offline sample data for testing the UI without API access.
- `Free Data Only`: Alpha Vantage transcript and earnings data plus SEC verification and local heuristic analysis.
- `Free Data + OpenAI`: adds an optional OpenAI narrative synthesis layer on top of the free data pipeline.

## Tech Stack

- Python
- Streamlit
- Alpha Vantage API
- SEC EDGAR API
- OpenAI API, optional
- Pydantic

## Setup

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your keys:

```env
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
OPENAI_API_KEY=your_openai_key_optional
EARNINGS_OPENAI_MODEL=gpt-5-mini
SEC_USER_AGENT=your-app-name/1.0 your-email@example.com
```

If you do not want to use OpenAI, you can leave `OPENAI_API_KEY` out entirely.

## Run Locally

```powershell
python -m streamlit run earnings_call_app/app.py --server.port 8502
```

Then open:

- `http://127.0.0.1:8502`

## Project Structure

- `earnings_call_app/app.py`: Streamlit UI and report rendering.
- `earnings_call_app/alpha_vantage.py`: Alpha Vantage data retrieval and retry logic.
- `earnings_call_app/sec.py`: SEC filing verification.
- `earnings_call_app/analysis.py`: transcript parsing, heuristic sentiment scoring, trend logic, and optional OpenAI synthesis.
- `earnings_call_app/demo_data.py`: offline demo report data.
- `earnings_call_app/models.py`: shared data models.
- `earnings_call_app/reporting.py`: JSON and Markdown export helpers.
- `earnings_call_app/tests`: automated tests.

## Notes

- The sentiment score is a heuristic summary of call tone, not investment advice.
- Alpha Vantage free-tier access can be rate-limited, so the app caches and retries where it can.
- SEC verification depends on a valid `SEC_USER_AGENT`.
- If live data is unavailable, the app can fall back to bundled demo content so the UI stays usable.

## Testing

```powershell
python -m pytest earnings_call_app/tests -q
```

