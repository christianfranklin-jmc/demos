-- Staging model for DIM_GL_ACCOUNT
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_GL_ACCOUNT

SELECT
    gl_account_key,
    gl_account_id,
    gl_account_name,
    account_type,
    account_category,
    account_subcategory,
    financial_statement,
    report_line,
    normal_balance,
    is_active,
    created_date,
    updated_date
FROM {{ source('pinnacle_financial_demo_asingh', 'DIM_GL_ACCOUNT') }}
