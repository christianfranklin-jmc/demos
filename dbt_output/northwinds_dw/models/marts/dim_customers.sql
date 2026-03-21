{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_northwinds__customers') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['customer_key']) }} as customer_sk,
        customer_key,
        company_name,
        contact_name,
        contact_title,
        address,
        city,
        region,
        postal_code,
        country,
        phone,
        fax
    from customers
)

select * from final