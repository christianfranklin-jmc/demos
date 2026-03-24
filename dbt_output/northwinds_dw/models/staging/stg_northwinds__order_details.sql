{{ config(materialized='view') }}

select
    order_id,
    product_id,
    unit_price,
    quantity,
    discount,
    -- Calculate derived measures
    unit_price * quantity as gross_amount,
    unit_price * quantity * discount as discount_amount,
    unit_price * quantity * (1 - discount) as net_amount
from {{ source('northwinds', 'order_details') }}