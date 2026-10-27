-- One row per month: the headline numbers for the power-mix analysis.
-- Domestic generation excludes net imports; demand = domestic generation + net imports.
with gen as (
    select
        month,
        sum(generation_twh) filter (where fuel_group <> 'Imports')        as generation_twh,
        sum(generation_twh) filter (where fuel = 'Coal')                  as coal_twh,
        sum(generation_twh) filter (where fuel in ('Wind', 'Solar'))      as wind_solar_twh,
        sum(generation_twh) filter (where fuel_group = 'Renewable')       as renewables_twh,
        coalesce(sum(generation_twh) filter (where fuel_group = 'Imports'), 0) as net_imports_twh
    from staging.stg_generation_monthly
    group by month
)
select
    gen.month,
    gen.generation_twh,
    gen.coal_twh,
    gen.wind_solar_twh,
    gen.renewables_twh,
    gen.net_imports_twh,
    d.demand_twh,
    100 * gen.coal_twh       / gen.generation_twh as coal_share_pct,
    100 * gen.wind_solar_twh / gen.generation_twh as wind_solar_share_pct
from gen
left join staging.stg_demand_monthly d using (month)
order by gen.month
