{{ config(materialized='view') }}

select
    category_id,
    category_name,
    description as category_description
from {{ source('northwinds', 'categories') }}