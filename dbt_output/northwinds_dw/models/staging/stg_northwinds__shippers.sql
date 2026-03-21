with source as (
    select * from {{ source('northwinds', 'shippers') }}
),

renamed as (
    select
        shipper_id as shipper_key,
        company_name as shipper_name,
        phone as shipper_phone
    from source
)

select * from renamed