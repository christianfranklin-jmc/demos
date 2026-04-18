-- Staging model for FACT_BUDGET
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FACT_BUDGET

SELECT
    budget_key,
    date_key,
    cost_center_key,
    gl_account_key,
    budget_type,
    budget_version,
    fiscal_year,
    budget_amount,
    forecast_amount,
    approved_by,
    approved_date,
    created_date,
    updated_date
FROM {{ source('pinnacle_financial_demo_asingh', 'FACT_BUDGET') }}
