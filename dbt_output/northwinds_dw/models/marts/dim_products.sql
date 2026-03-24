{{ config(materialized='table') }}

{{ config(materialized='table') }}

with products as (
    select * from {{ ref('stg_northwinds__products') }}
),

categories as (
    select * from {{ ref('stg_northwinds__categories') }}
),

suppliers as (
    select * from {{ ref('stg_northwinds__suppliers') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['p.product_id']) }} as product_key,
    p.product_id,
    p.product_name,
    c.category_name,
    c.category_description,
    s.company_name as supplier_name,
    s.country as supplier_country,
    s.city as supplier_city,
    p.quantity_per_unit,
    p.unit_price,
    p.units_in_stock,
    p.units_on_order,
    p.reorder_level,
    case when p.discontinued = 1 then true else false end as is_discontinued
from products p
left join categories c on p.category_id = c.category_id
left join suppliers s on p.supplier_id = s.supplier_id