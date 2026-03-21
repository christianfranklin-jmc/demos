with source as (
    select * from {{ source('northwinds', 'customers') }}
),

renamed as (
    select
        customer_id as customer_key,
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
    from source
)

select * from renamed