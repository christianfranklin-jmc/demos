{{ config(materialized='view') }}

select
    employee_id,
    last_name || ', ' || first_name as employee_name,
    first_name,
    last_name,
    title,
    title_of_courtesy,
    birth_date,
    hire_date,
    address,
    city,
    region,
    postal_code,
    country,
    home_phone,
    extension,
    reports_to,
    notes
from {{ source('northwinds', 'employees') }}