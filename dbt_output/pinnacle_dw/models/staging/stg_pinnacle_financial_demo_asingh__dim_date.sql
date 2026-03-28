-- Staging model for DIM_DATE
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_DATE

SELECT
    date_key,
    full_date,
    day_of_week,
    day_name,
    day_of_month,
    day_of_year,
    week_of_year,
    month_number,
    month_name,
    month_short,
    quarter,
    quarter_name,
    year,
    fiscal_quarter,
    fiscal_year,
    is_weekend,
    is_month_end,
    is_quarter_end,
    is_year_end
FROM {{ source('pinnacle_financial_demo_asingh', 'DIM_DATE') }}
