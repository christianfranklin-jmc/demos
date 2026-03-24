{{ config(materialized='table') }}

{{ config(materialized='table') }}

with shippers as (
    select * from {{ ref('stg_northwinds__shippers') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['shipper_id']) }} as shipper_key,
    shipper_id,
    company_name,
    phone
from shippers