with source as (
    select * from {{ source('northwinds', 'categories') }}
),

renamed as (
    select
        category_id,
        category_name,
        description as category_description
    from source
)

select * from renamed