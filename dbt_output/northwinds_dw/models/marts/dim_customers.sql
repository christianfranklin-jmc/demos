{{ config(materialized='table') }}

{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_northwinds__customers') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['customer_id']) }} as customer_key,
    customer_id,
    company_name,
    contact_name,
    contact_title,
    address,
    city,
    coalesce(region, 'Unknown') as region,
    postal_code,
    country,
    phone,
    fax
from customers