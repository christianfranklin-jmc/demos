{{ config(materialized='table') }}

with employees as (
    select * from {{ ref('stg_northwinds__employees') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['employee_key']) }} as employee_sk,
        employee_key,
        first_name,
        last_name,
        first_name || ' ' || last_name as full_name,
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
        notes,
        reports_to,
        photo_path
    from employees
)

select * from final