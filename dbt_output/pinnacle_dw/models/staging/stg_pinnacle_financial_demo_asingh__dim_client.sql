-- Staging model for DIM_CLIENT
-- Source: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_CLIENT

SELECT
    client_key,
    client_id,
    client_name,
    client_segment,
    client_tier,
    relationship_manager,
    onboarding_date,
    primary_contact,
    email,
    phone,
    address_line1,
    city,
    state,
    zip_code,
    office_location,
    risk_profile,
    is_active,
    created_date,
    updated_date
FROM {{ source('pinnacle_financial_demo_asingh', 'DIM_CLIENT') }}
