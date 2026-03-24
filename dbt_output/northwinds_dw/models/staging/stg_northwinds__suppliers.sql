{{ config(materialized='view') }}

select
    supplier_id,
    company_name,
    contact_name,
    contact_title,
    address,
    city,
    region,
    postal_code,
    country,
    phone,
    fax,
    home_page
from {{ source('northwinds', 'suppliers') }}