-- ============================================================
-- FP&A Automation Pipeline - MySQL Schema
-- ============================================================
-- Database: fpa_project
-- Five tables, each holding both 'Budget' and 'Actual' scenarios
-- for the same set of months, enabling Budget vs Actual (BvA)
-- variance analysis directly in SQL or downstream in Python.
--
-- Design notes:
--   - Derived fields (year, month name, month index) are NOT
--     stored, since they can always be computed from month_date -
--     storing them would risk drift if a date were ever corrected.
--   - Every table's primary key includes 'scenario' so the same
--     month can hold one Budget row and one Actual row without
--     collision.
-- ============================================================

CREATE DATABASE IF NOT EXISTS fpa_project;
USE fpa_project;

-- ------------------------------------------------------------
-- Income Statement
-- ------------------------------------------------------------
CREATE TABLE income_statement (
    month_date                  DATE NOT NULL,
    scenario                    VARCHAR(10) NOT NULL,          -- 'Budget' or 'Actual'
    active_customers            INT,
    net_bookings                DECIMAL(14,2),
    net_revenue_mrr             DECIMAL(14,2),
    deferred_rev                DECIMAL(14,2),
    annual_run_rate             DECIMAL(14,2),
    ltv_cac_ratio                DECIMAL(8,2),
    cogs_aws                    DECIMAL(14,2),
    cogs_customer_support       DECIMAL(14,2),
    cogs_benefits_taxes         DECIMAL(14,2),
    total_cogs                  DECIMAL(14,2),
    gross_margin                DECIMAL(14,2),
    gm_pct                      DECIMAL(6,3),
    personnel_sales             DECIMAL(14,2),
    personnel_marketing         DECIMAL(14,2),
    personnel_creative          DECIMAL(14,2),
    personnel_technology        DECIMAL(14,2),
    personnel_productmgmt       DECIMAL(14,2),
    personnel_execadmin         DECIMAL(14,2),
    personnel_bonuses           DECIMAL(14,2),
    personnel_benefits_taxes    DECIMAL(14,2),
    total_personnel_exp         DECIMAL(14,2),
    ad_spend                    DECIMAL(14,2),
    other_marketing_opex        DECIMAL(14,2),
    technology_opex             DECIMAL(14,2),
    da_opex                     DECIMAL(14,2),
    misc_fixed_exp              DECIMAL(14,2),
    variable_exp_pct_bookings   DECIMAL(14,2),                 -- resized: this line grows into
                                                                -- dollar amounts, not a pure %,
                                                                -- in later months of the model
    total_other_opex            DECIMAL(14,2),
    total_opex                  DECIMAL(14,2),
    ebit                        DECIMAL(14,2),                 -- dollar EBIT ("OPERATING PROFIT" row)
    ebit_margin_pct             DECIMAL(6,3),                   -- EBIT as % of revenue (the row actually
                                                                -- labeled "EBIT" in the source workbook)
    tax_loss_asset              DECIMAL(14,2),
    taxes                       DECIMAL(14,2),
    net_income                  DECIMAL(14,2),
    PRIMARY KEY (month_date, scenario)
);

-- ------------------------------------------------------------
-- Balance Sheet
-- ------------------------------------------------------------
CREATE TABLE balance_sheet (
    month_date                   DATE NOT NULL,
    scenario                     VARCHAR(10) NOT NULL,
    cash                         DECIMAL(14,2),
    fixed_assets                 DECIMAL(14,2),
    depreciation                 DECIMAL(14,2),
    net_fixed_assets             DECIMAL(14,2),
    total_assets                 DECIMAL(14,2),
    deferred_revenue_liability   DECIMAL(14,2),
    total_liabilities            DECIMAL(14,2),
    new_financing                DECIMAL(14,2),
    retained_earnings            DECIMAL(14,2),
    total_equity                 DECIMAL(14,2),
    balance_check                DECIMAL(14,2),
    PRIMARY KEY (month_date, scenario)
);

-- ------------------------------------------------------------
-- Cash Flow Statement
-- ------------------------------------------------------------
CREATE TABLE cash_flow (
    month_date            DATE NOT NULL,
    scenario               VARCHAR(10) NOT NULL,
    net_income             DECIMAL(14,2),
    net_deferred_rev       DECIMAL(14,2),
    depreciation           DECIMAL(14,2),
    operating_cash_flow    DECIMAL(14,2),
    capex                  DECIMAL(14,2),
    new_equity             DECIMAL(14,2),
    net_cash_flow          DECIMAL(14,2),
    PRIMARY KEY (month_date, scenario)
);

-- ------------------------------------------------------------
-- Headcount Assumptions (long format: one row per month/department/scenario)
-- ------------------------------------------------------------
CREATE TABLE headcount_assumptions (
    month_date    DATE NOT NULL,
    department    VARCHAR(30) NOT NULL,   -- Sales, Marketing, Creative, Technology,
                                           -- Product Mgmt, Exec/Admin, Customer Support
    scenario      VARCHAR(10) NOT NULL,
    headcount     INT,
    PRIMARY KEY (month_date, department, scenario)
);

-- ------------------------------------------------------------
-- Monthly SaaS Metrics
-- ------------------------------------------------------------
CREATE TABLE monthly_saas_metrics (
    month_date          DATE NOT NULL,
    scenario            VARCHAR(10) NOT NULL,
    customers_begin     INT,
    customers_new       INT,
    customers_churned   INT,
    customers_end       INT,
    mrr_begin           DECIMAL(14,2),
    expansion_mrr       DECIMAL(14,2),
    churned_mrr         DECIMAL(14,2),
    mrr_end             DECIMAL(14,2),
    ndr_pct             DECIMAL(6,3),
    cogs                DECIMAL(14,2),
    sales_mkt_spend     DECIMAL(14,2),
    PRIMARY KEY (month_date, scenario)
);
