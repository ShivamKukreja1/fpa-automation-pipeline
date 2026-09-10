"""
FP&A Variance Analysis (Phase 2)
================================
Pulls Budget/Actual data from MySQL and produces:
  1. Revenue PVM (Price/Volume) decomposition, month by month
  2. OpEx category flux analysis (Budget vs Actual, by line item)
  3. A simple driver-based 6-month forward extension of the Actuals trend

Outputs three CSVs into ./output/ - these feed directly into the Power BI
dashboard in Phase 3. Nothing is written back to MySQL; this script is
read-only against the database.

Design notes (for interview / README):
  - PVM here decomposes MRR variance into two factors: Volume (change in
    active customers) and Price (change in revenue-per-customer, i.e.
    ARPU). This is the standard two-factor decomposition:
        Volume effect = (Actual_customers - Budget_customers) * Budget_ARPU
        Price  effect = (Actual_ARPU - Budget_ARPU) * Actual_customers
    These two sum exactly to the total revenue variance - verified against
    real data before shipping this script, not assumed to work.
  - "Mix" is intentionally omitted: this model has one product line, so a
    mix effect (revenue shift between products) doesn't apply here. Adding
    a mix term with only one product would be fabricating a number, not
    real analysis.
  - The forward extension is a simple average-growth-rate projection off
    the last 6 months of Actuals, not a new model - it's there to give the
    Power BI dashboard a "next 6 months" view, and is clearly labeled as
    such in the output (scenario = 'Forecast'), not blended with Budget.
"""

from __future__ import annotations

import getpass
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DB = "fpa_project"
MYSQL_USER = "root"

OUTPUT_DIR = Path("output")
FORECAST_MONTHS = 6
FORECAST_TREND_WINDOW = 6   # trailing months of Actuals used to estimate growth


# --------------------------------------------------------------------------
# Connection + load
# --------------------------------------------------------------------------

def get_engine(password: str):
    url = f"mysql+pymysql://{MYSQL_USER}:{password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    return create_engine(url)


def load_tables(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info("Reading income_statement and monthly_saas_metrics from MySQL")
    income = pd.read_sql("SELECT * FROM income_statement", engine, parse_dates=["month_date"])
    metrics = pd.read_sql("SELECT * FROM monthly_saas_metrics", engine, parse_dates=["month_date"])
    return income, metrics


# --------------------------------------------------------------------------
# PVM decomposition (revenue: Volume x Price)
# --------------------------------------------------------------------------

def pvm_revenue_variance(metrics: pd.DataFrame) -> pd.DataFrame:
    budget = metrics[metrics.scenario == "Budget"].set_index("month_date")
    actual = metrics[metrics.scenario == "Actual"].set_index("month_date")

    b_customers = budget["customers_end"].replace(0, np.nan)
    a_customers = actual["customers_end"].replace(0, np.nan)
    b_arpu = budget["mrr_end"] / b_customers
    a_arpu = actual["mrr_end"] / a_customers

    volume_effect = (actual["customers_end"] - budget["customers_end"]) * b_arpu
    price_effect = (a_arpu - b_arpu) * actual["customers_end"]
    total_variance = actual["mrr_end"] - budget["mrr_end"]

    out = pd.DataFrame({
        "budget_mrr": budget["mrr_end"],
        "actual_mrr": actual["mrr_end"],
        "total_variance": total_variance,
        "volume_effect": volume_effect.fillna(0),
        "price_effect": price_effect.fillna(0),
    })
    out["reconciliation_check"] = (
        out["volume_effect"] + out["price_effect"] - out["total_variance"]
    ).round(2)
    return out.reset_index()


# --------------------------------------------------------------------------
# OpEx flux (Budget vs Actual, by category)
# --------------------------------------------------------------------------

OPEX_CATEGORIES = {
    "personnel_sales": "Sales",
    "personnel_marketing": "Marketing",
    "personnel_creative": "Creative",
    "personnel_technology": "Technology",
    "personnel_productmgmt": "Product Mgmt",
    "personnel_execadmin": "Exec / Admin",
    "ad_spend": "Ad Spend",
    "other_marketing_opex": "Other Marketing",
    "technology_opex": "Technology (Other)",
    "misc_fixed_exp": "Misc Fixed",
}


def opex_flux(income: pd.DataFrame) -> pd.DataFrame:
    budget = income[income.scenario == "Budget"].set_index("month_date")
    actual = income[income.scenario == "Actual"].set_index("month_date")

    rows = []
    for col, label in OPEX_CATEGORIES.items():
        variance = actual[col] - budget[col]
        for month_date, b_val, a_val, var in zip(
            budget.index, budget[col], actual[col], variance
        ):
            rows.append({
                "month_date": month_date,
                "category": label,
                "budget": b_val,
                "actual": a_val,
                "variance": var,
                "favorable": var <= 0,   # opex: actual under budget = favorable
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Simple forward extension (labeled 'Forecast', separate from Budget)
# --------------------------------------------------------------------------

def forward_extension(metrics: pd.DataFrame, months: int = FORECAST_MONTHS) -> pd.DataFrame:
    actual = metrics[metrics.scenario == "Actual"].sort_values("month_date")
    recent = actual.tail(FORECAST_TREND_WINDOW)

    mrr_growth = recent["mrr_end"].pct_change().dropna()
    customer_growth = recent["customers_end"].pct_change().dropna()
    avg_mrr_growth = mrr_growth.mean() if len(mrr_growth) else 0.0
    avg_customer_growth = customer_growth.mean() if len(customer_growth) else 0.0

    last_row = actual.iloc[-1]
    last_date = last_row["month_date"]
    last_mrr = last_row["mrr_end"]
    last_customers = last_row["customers_end"]

    rows = []
    for i in range(1, months + 1):
        forecast_date = (last_date + pd.DateOffset(months=i))
        last_mrr = last_mrr * (1 + avg_mrr_growth)
        last_customers = last_customers * (1 + avg_customer_growth)
        rows.append({
            "month_date": forecast_date,
            "scenario": "Forecast",
            "mrr_end": round(last_mrr, 2),
            "customers_end": round(last_customers, 1),
            "trend_mrr_growth_pct": round(avg_mrr_growth * 100, 2),
            "trend_customer_growth_pct": round(avg_customer_growth * 100, 2),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def main() -> None:
    password = getpass.getpass("MySQL root password: ")
    engine = get_engine(password)

    income, metrics = load_tables(engine)

    OUTPUT_DIR.mkdir(exist_ok=True)

    pvm = pvm_revenue_variance(metrics)
    bad_checks = pvm[pvm["reconciliation_check"].abs() > 0.01]
    if len(bad_checks):
        log.warning("%d month(s) failed PVM reconciliation - check manually", len(bad_checks))
    pvm.to_csv(OUTPUT_DIR / "revenue_pvm_variance.csv", index=False)
    log.info("Wrote %d rows to output/revenue_pvm_variance.csv", len(pvm))

    flux = opex_flux(income)
    flux.to_csv(OUTPUT_DIR / "opex_flux_analysis.csv", index=False)
    log.info("Wrote %d rows to output/opex_flux_analysis.csv", len(flux))

    forecast = forward_extension(metrics)
    forecast.to_csv(OUTPUT_DIR / "forward_extension.csv", index=False)
    log.info("Wrote %d rows to output/forward_extension.csv", len(forecast))

    log.info("Done. Three CSVs ready in ./output/ for Power BI.")


if __name__ == "__main__":
    main()
