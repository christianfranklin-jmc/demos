{{ config(materialized='table') }}

with products as (
    select * from {{ ref('stg_northwinds__products') }}
),

categories as (
    select * from {{ ref('stg_northwinds__categories') }}
),

suppliers as (
    select * from {{ ref('stg_northwinds__suppliers') }}
),

joined as (
    select
        p.product_key,
        p.product_name,
        p.quantity_per_unit,
        p.unit_price,
        p.units_in_stock,
        p.units_on_order,
        p.reorder_level,
        p.discontinued,
        
        -- Category attributes
        c.category_name,
        c.category_description,
        
        -- Supplier attributes
        s.supplier_name,
        s.supplier_contact_name,
        s.supplier_contact_title,
        s.supplier_address,
        s.supplier_city,
        s.supplier_region,
        s.supplier_postal_code,
        s.supplier_country,
        s.supplier_phone,
        s.supplier_fax,
        s.supplier_home_page
        
    from products p
    left join categories c on p.category_id = c.category_id
    left join suppliers s on p.supplier_id = s.supplier_id
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['product_key']) }} as product_sk,
        product_key,
        product_name,
        quantity_per_unit,
        unit_price,
        units_in_stock,
        units_on_order,
        reorder_level,
        case when discontinued = 1 then true else false end as is_discontinued,
        
        -- Category attributes
        category_name,
        category_description,
        
        -- Supplier attributes
        supplier_name,
        supplier_contact_name,
        supplier_contact_title,
        supplier_address,
        supplier_city,
        supplier_region,
        supplier_postal_code,
        supplier_country,
        supplier_phone,
        supplier_fax,
        supplier_home_page
        
    from joined
)

select * from final