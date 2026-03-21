with source as (
    select * from {{ source('northwinds', 'suppliers') }}
),

renamed as (
    select
        supplier_id,
        company_name as supplier_name,
        contact_name as supplier_contact_name,
        contact_title as supplier_contact_title,
        address as supplier_address,
        city as supplier_city,
        region as supplier_region,
        postal_code as supplier_postal_code,
        country as supplier_country,
        phone as supplier_phone,
        fax as supplier_fax,
        home_page as supplier_home_page
    from source
)

select * from renamed