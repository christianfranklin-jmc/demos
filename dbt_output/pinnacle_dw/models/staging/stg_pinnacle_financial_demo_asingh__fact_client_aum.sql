-- Staging model for FACT_CLIENT_AUM
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FACT_CLIENT_AUM

SELECT
    aum_key,
    date_key,
    client_key,
    product_key,
    beginning_aum,
    contributions,
    withdrawals,
    market_change,
    ending_aum,
    aum_change,
    aum_change_pct,
    net_flows,
    organic_growth_pct,
    source_system,
    snapshot_type,
    created_date
FROM {{ source('pinnacle_financial_demo_asingh', 'FACT_CLIENT_AUM') }}
