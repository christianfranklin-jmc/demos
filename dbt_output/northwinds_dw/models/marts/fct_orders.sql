{{ config(materialized='table') }}

{{ config(materialized='table') }}

with orders as (
    select * from {{ ref('stg_northwinds__orders') }}
),

customers as (
    select * from {{ ref('dim_customers') }}
),

employees as (
    select * from {{ ref('dim_employees') }}
),

shippers as (
    select * from {{ ref('dim_shippers') }}
),

date_dim as (
    select * from {{ ref('dim_date') }}
),

order_aggregates as (
    select
        order_id,
        sum(net_amount) as order_total,
        count(*) as line_item_count
    from {{ ref('stg_northwinds__order_details') }}
    group by order_id
)

select
    {{ dbt_utils.generate_surrogate_key(['o.order_id']) }} as order_key,
    o.order_id,
    c.customer_key,
    e.employee_key,
    s.shipper_key,
    od_date.date_key as order_date_key,
    rd_date.date_key as required_date_key,
    sd_date.date_key as shipped_date_key,
    
    -- Measures
    coalesce(oa.order_total, 0) as order_total,
    o.freight,
    coalesce(oa.line_item_count, 0) as line_item_count,
    
    -- Calculated measures
    case 
        when o.shipped_date is not null and o.order_date is not null
        then o.shipped_date - o.order_date
        else null
    end as days_to_ship
    
from orders o
join customers c on o.customer_id = c.customer_id
left join employees e on o.employee_id = e.employee_id
left join shippers s on o.shipper_id = s.shipper_id
left join date_dim od_date on o.order_date = od_date.date_value
left join date_dim rd_date on o.required_date = rd_date.date_value
left join date_dim sd_date on o.shipped_date = sd_date.date_value
left join order_aggregates oa on o.order_id = oa.order_id