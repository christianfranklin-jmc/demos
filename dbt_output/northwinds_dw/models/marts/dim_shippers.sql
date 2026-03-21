{{ config(materialized='table') }}

with shippers as (
    select * from {{ ref('stg_northwinds__shippers') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['shipper_key']) }} as shipper_sk,
        shipper_key,
        shipper_name,
        shipper_phone
    from shippers
)

select * from final