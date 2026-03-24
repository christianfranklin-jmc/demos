{{ config(materialized='table') }}

{{ config(materialized='table') }}

with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="'1996-01-01'",
        end_date="'1999-12-31'"
    ) }}
)

select
    {{ dbt_utils.generate_surrogate_key(['date_day']) }} as date_key,
    date_day as date_value,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month_number,
    to_char(date_day, 'Month') as month_name,
    to_char(date_day, 'Mon') as month_name_short,
    extract(week from date_day) as week_of_year,
    extract(day from date_day) as day_of_month,
    to_char(date_day, 'Day') as day_name,
    to_char(date_day, 'Dy') as day_name_short,
    extract(dow from date_day) as day_of_week,
    case when extract(dow from date_day) in (0, 6) then true else false end as is_weekend
from date_spine