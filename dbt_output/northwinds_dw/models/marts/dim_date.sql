{{ config(materialized='table') }}

with date_spine as (
    select
        generate_series(
            '1996-01-01'::date,
            '1999-01-01'::date,
            '1 day'::interval
        )::date as date_day
),

date_attributes as (
    select
        date_day,
        extract(year from date_day) as year_number,
        extract(quarter from date_day) as quarter_number,
        extract(month from date_day) as month_number,
        extract(week from date_day) as week_number,
        extract(dayofyear from date_day) as day_of_year_number,
        extract(dayofweek from date_day) as day_of_week_number,
        to_char(date_day, 'Day') as day_name,
        to_char(date_day, 'Month') as month_name,
        case when extract(dayofweek from date_day) in (0, 6) then true else false end as is_weekend,
        date_trunc('week', date_day)::date as week_start_date,
        date_trunc('month', date_day)::date as month_start_date,
        date_trunc('quarter', date_day)::date as quarter_start_date,
        date_trunc('year', date_day)::date as year_start_date
    from date_spine
)

select
    {{ dbt_utils.generate_surrogate_key(['date_day']) }} as date_key,
    date_day,
    year_number,
    quarter_number,
    month_number,
    week_number,
    day_of_year_number,
    day_of_week_number,
    day_name,
    month_name,
    is_weekend,
    week_start_date,
    month_start_date,
    quarter_start_date,
    year_start_date,
    year_number || '-Q' || quarter_number as quarter_name,
    to_char(date_day, 'YYYY-MM') as year_month
from date_attributes