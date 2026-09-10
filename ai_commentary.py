"""
FP&A Phase 4 - AI-Generated Variance Commentary
================================================
Reads the Phase 2 outputs (revenue_pvm_variance.csv, opex_flux_analysis.csv)
for a chosen month, builds a structured prompt describing that month's
numbers, and asks an LLM to draft a short executive variance commentary -
the kind an analyst would normally write by hand at month-end close.

This does NOT invent numbers: the prompt only contains figures already
computed and verified in Phase 2. The model's job is narrative, not
arithmetic - it is explicitly told to work only from the numbers given.

Design notes (for interview / README):
  - The API key is entered at runtime (getpass), never hardcoded or
    committed to the repo - same pattern used for the MySQL password in
    etl_pipeline.py.
  - Only the top 3 opex categories by absolute variance are included in
    the prompt (not all 10) to keep the commentary focused on what
    actually matters that month, mirroring how a real analyst would
    highlight material variances rather than list every line item.
  - Output is appended to output/ai_commentary.txt with the month and
    timestamp, so a running log builds up across multiple runs rather
    than overwriting the previous month's commentary.
"""

from __future__ import annotations

import getpass
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
PVM_FILE = OUTPUT_DIR / "revenue_pvm_variance.csv"
FLUX_FILE = OUTPUT_DIR / "opex_flux_analysis.csv"
COMMENTARY_FILE = OUTPUT_DIR / "ai_commentary.txt"

MODEL = "gpt-4o-mini"
TOP_N_OPEX_LINES = 3


def load_month_data(month: str | None = None) -> tuple[pd.Series, pd.DataFrame]:
    """Load the PVM row and top opex variance lines for one month.
    If month is None, uses the most recent month present in the data."""
    pvm = pd.read_csv(PVM_FILE, parse_dates=["month_date"])
    flux = pd.read_csv(FLUX_FILE, parse_dates=["month_date"])

    if month is None:
        target_date = pvm["month_date"].max()
    else:
        target_date = pd.Timestamp(month)

    pvm_row = pvm[pvm["month_date"] == target_date]
    if pvm_row.empty:
        raise ValueError(f"No PVM data found for {target_date.date()}")
    pvm_row = pvm_row.iloc[0]

    flux_month = flux[flux["month_date"] == target_date].copy()
    flux_month["abs_variance"] = flux_month["variance"].abs()
    top_flux = flux_month.sort_values("abs_variance", ascending=False).head(TOP_N_OPEX_LINES)

    return pvm_row, top_flux


def build_prompt(pvm_row: pd.Series, top_flux: pd.DataFrame) -> str:
    month_label = pvm_row["month_date"].strftime("%B %Y")

    opex_lines = "\n".join(
        f"  - {row.category}: budget ${row.budget:,.0f}, actual ${row.actual:,.0f}, "
        f"variance ${row.variance:,.0f} ({'unfavorable' if row.variance > 0 else 'favorable'})"
        for row in top_flux.itertuples()
    )

    return f"""You are an FP&A analyst writing a month-end variance commentary.
Use ONLY the numbers below - do not invent figures or assume causes not
implied by the data. Write 3-4 sentences, professional tone, suitable for
an executive summary slide.

Month: {month_label}
Budget MRR: ${pvm_row.budget_mrr:,.0f}
Actual MRR: ${pvm_row.actual_mrr:,.0f}
Total revenue variance: ${pvm_row.total_variance:,.0f}
  - Volume effect (change in customer count): ${pvm_row.volume_effect:,.0f}
  - Price effect (change in revenue per customer): ${pvm_row.price_effect:,.0f}

Largest OpEx variances this month:
{opex_lines}

Write the commentary now."""


def get_commentary(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    api_key = getpass.getpass("OpenAI API key: ")
    client = OpenAI(api_key=api_key)

    pvm_row, top_flux = load_month_data()
    prompt = build_prompt(pvm_row, top_flux)

    log.info("Requesting commentary for %s", pvm_row["month_date"].strftime("%B %Y"))
    commentary = get_commentary(client, prompt)

    print("\n" + "=" * 60)
    print(f"VARIANCE COMMENTARY - {pvm_row['month_date'].strftime('%B %Y')}")
    print("=" * 60)
    print(commentary)
    print("=" * 60 + "\n")

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(COMMENTARY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] "
                 f"{pvm_row['month_date'].strftime('%B %Y')}\n")
        f.write(commentary + "\n")
        f.write("-" * 60 + "\n")

    log.info("Appended to %s", COMMENTARY_FILE)


if __name__ == "__main__":
    main()
