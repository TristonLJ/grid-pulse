-- One row per entity per year: how far each grid has moved off fossil fuels.
-- Shares are of domestic generation (net imports excluded), matching the monthly mart.
with gen as (
    select
        entity,
        any_value(entity_code)  as entity_code,
        any_value(is_benchmark) as is_benchmark,
        year,
        sum(generation_twh) filter (where fuel_group <> 'Imports')    as generation_twh,
        sum(generation_twh) filter (where fuel = 'Coal')              as coal_twh,
        sum(generation_twh) filter (where fuel in ('Wind', 'Solar'))  as wind_solar_twh
    from staging.stg_generation_yearly
    group by entity, year
)
select
    gen.*,
    100 * coal_twh       / generation_twh  as coal_share_pct,
    100 * wind_solar_twh / generation_twh  as wind_solar_share_pct,
    ci.gco2_per_kwh
from gen
left join staging.stg_carbon_intensity_yearly ci using (entity, year)
order by entity, year
