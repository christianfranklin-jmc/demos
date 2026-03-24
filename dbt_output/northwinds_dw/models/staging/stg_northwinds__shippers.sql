{{ config(materialized='view') }}

select
    shipper_id,
    company_name,
    phone
from {{ source('northwinds', 'shippers') }}