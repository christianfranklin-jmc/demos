{{ config(materialized='table') }}

{{ config(materialized='table') }}

with employees as (
    select * from {{ ref('stg_northwinds__employees') }}
),

managers as (
    select
        employee_id,
        employee_name as manager_name
    from employees
)

select
    {{ dbt_utils.generate_surrogate_key(['e.employee_id']) }} as employee_key,
    e.employee_id,
    e.employee_name,
    e.first_name,
    e.last_name,
    e.title,
    e.title_of_courtesy,
    e.birth_date,
    e.hire_date,
    e.address,
    e.city,
    coalesce(e.region, 'Unknown') as region,
    e.postal_code,
    e.country,
    e.home_phone,
    e.extension,
    e.reports_to,
    coalesce(m.manager_name, 'None') as manager_name
from employees e
left join managers m on e.reports_to = m.employee_id