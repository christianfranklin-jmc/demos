with source as (
    select * from {{ source('northwinds', 'employees') }}
),

renamed as (
    select
        employee_id as employee_key,
        last_name,
        first_name,
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
    from source
)

select * from renamed