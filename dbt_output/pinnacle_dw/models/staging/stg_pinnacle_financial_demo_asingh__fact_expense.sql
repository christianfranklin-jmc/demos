-- Staging model for FACT_EXPENSE
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FACT_EXPENSE

SELECT
    expense_key,
    date_key,
    cost_center_key,
    gl_account_key,
    expense_description,
    vendor_name,
    actual_amount,
    budget_amount,
    variance_amount,
    variance_pct,
    is_recurring,
    payment_status,
    source_system,
    source_transaction_id,
    invoice_number,
    created_date
FROM {{ source('pinnacle_financial_demo_asingh', 'FACT_EXPENSE') }}
