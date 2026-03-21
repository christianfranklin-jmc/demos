with source as (
    select * from {{ source('northwinds', 'products') }}
),

renamed as (
    select
        product_id as product_key,
        product_name,
        supplier_id,
        category_id,
        quantity_per_unit,
        unit_price,
        units_in_stock,
        units_on_order,
        reorder_level,
        discontinued
    from source
)

select * from renamed