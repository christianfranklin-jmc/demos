-- Staging model for DIM_PRODUCT
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_PRODUCT

SELECT
    product_key,
    product_id,
    product_name,
    product_category,
    product_type,
    investment_strategy,
    benchmark_index,
    inception_date,
    management_fee_bps,
    performance_fee_pct,
    minimum_investment,
    is_active,
    created_date,
    updated_date
FROM {{ source('pinnacle_financial_demo_asingh', 'DIM_PRODUCT') }}
