-- Staging model for FACT_REVENUE
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FACT_REVENUE

SELECT
    revenue_key,
    date_key,
    client_key,
    product_key,
    gl_account_key,
    revenue_type,
    aum_amount,
    fee_basis_points,
    gross_revenue,
    adjustments,
    net_revenue,
    source_system,
    source_transaction_id,
    created_date
FROM {{ source('pinnacle_financial_demo_asingh', 'FACT_REVENUE') }}
