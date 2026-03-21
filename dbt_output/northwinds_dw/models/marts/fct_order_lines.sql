{{ config(materialized='table') }}

with order_details as (
    select * from {{ ref('stg_northwinds__order_details') }}
),

orders as (
    select * from {{ ref('stg_northwinds__orders') }}
),

dim_customers as (
    select * from {{ ref('dim_customers') }}
),

dim_products as (
    select * from {{ ref('dim_products') }}
),

dim_employees as (
    select * from {{ ref('dim_employees') }}
),

dim_shippers as (
    select * from {{ ref('dim_shippers') }}
),

dim_date as (
    select * from {{ ref('dim_date') }}
),

joined as (
    select
        od.order_id,
        od.product_id,
        
        -- Foreign keys to dimensions
        dc.customer_sk,
        dp.product_sk,
        de.employee_sk,
        ds.shipper_sk,
        dd_order.date_key as order_date_key,
        dd_required.date_key as required_date_key,
        dd_shipped.date_key as shipped_date_key,
        
        -- Degenerate dimensions
        o.order_key,
        od.product_id as product_key_degenerate,
        
        -- Measures
        od.unit_price,
        od.quantity,
        od.discount,
        od.unit_price * od.quantity as line_total_before_discount,
        od.unit_price * od.quantity * (1 - od.discount) as line_total_after_discount,
        od.unit_price * od.quantity * od.discount as discount_amount,
        o.freight,
        
        -- Order attributes
        o.ship_name,
        o.ship_address,
        o.ship_city,
        o.ship_region,
        o.ship_postal_code,
        o.ship_country
        
    from order_details od
    inner join orders o on od.order_id = o.order_key
    left join dim_customers dc on o.customer_id = dc.customer_key
    left join dim_products dp on od.product_id = dp.product_key
    left join dim_employees de on o.employee_id = de.employee_key
    left join dim_shippers ds on o.shipper_id = ds.shipper_key
    left join dim_date dd_order on o.order_date = dd_order.date_day
    left join dim_date dd_required on o.required_date = dd_required.date_day
    left join dim_date dd_shipped on o.shipped_date = dd_shipped.date_day
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['order_id', 'product_id']) }} as order_line_sk,
        
        -- Dimension foreign keys
        customer_sk,
        product_sk,
        employee_sk,
        shipper_sk,
        order_date_key,
        required_date_key,
        shipped_date_key,
        
        -- Degenerate dimensions
        order_key,
        product_key_degenerate,
        
        -- Measures
        unit_price,
        quantity,
        discount,
        line_total_before_discount,
        line_total_after_discount,
        discount_amount,
        freight,
        
        -- Order attributes
        ship_name,
        ship_address,
        ship_city,
        ship_region,
        ship_postal_code,
        ship_country
        
    from joined
)

select * from final