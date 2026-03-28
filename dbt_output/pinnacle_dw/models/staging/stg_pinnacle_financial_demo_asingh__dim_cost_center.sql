-- Staging model for DIM_COST_CENTER
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_COST_CENTER

SELECT
    cost_center_key,
    cost_center_id,
    cost_center_name,
    department,
    expense_category,
    expense_type,
    gl_account_code,
    manager,
    is_active,
    created_date,
    updated_date
FROM {{ source('pinnacle_financial_demo_asingh', 'DIM_COST_CENTER') }}
