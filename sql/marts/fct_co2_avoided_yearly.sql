-- How much CO2 South Africa's wind and solar avoided, per year.
--
-- Counterfactual: without wind and solar, the same electricity would have come from
-- other plants. We bracket the answer with two assumptions:
--   high: it would all have come from coal (coal supplies most of the power that SA's wind
--         and solar could displace),
--         at that year's coal emissions rate (coal Mt CO2 / coal TWh)
--   low:  it would have come from the average grid mix, at the grid's carbon intensity
-- Units: Mt CO2 per TWh is numerically the same as kg CO2 per kWh; g/kWh / 1000 = Mt/TWh.
-- (Reads staging only, so marts never depend on each other's build order.)
with sa as (
    select
        g.year,
        sum(g.generation_twh) filter (where g.fuel_group <> 'Imports')   as generation_twh,
        sum(g.generation_twh) filter (where g.fuel = 'Coal')             as coal_twh,
        sum(g.generation_twh) filter (where g.fuel in ('Wind', 'Solar')) as wind_solar_twh,
        any_value(ci.gco2_per_kwh)                                       as gco2_per_kwh
    from staging.stg_generation_yearly g
    left join staging.stg_carbon_intensity_yearly ci using (entity, year)
    where g.entity_code = 'ZAF'
    group by g.year
),
em as (
    select
        year,
        sum(emissions_mtco2)                              as total_mtco2,
        sum(emissions_mtco2) filter (where fuel = 'Coal') as coal_mtco2
    from staging.stg_emissions_yearly
    where entity = 'South Africa'
    group by year
)
select
    sa.year,
    sa.wind_solar_twh,
    em.coal_mtco2 / sa.coal_twh                      as coal_mt_per_twh,
    sa.gco2_per_kwh,
    sa.wind_solar_twh * em.coal_mtco2 / sa.coal_twh  as avoided_high_mtco2,
    sa.wind_solar_twh * sa.gco2_per_kwh / 1000       as avoided_low_mtco2,
    sum(sa.wind_solar_twh * em.coal_mtco2 / sa.coal_twh) over (order by sa.year) as cumulative_high_mtco2,
    sum(sa.wind_solar_twh * sa.gco2_per_kwh / 1000)      over (order by sa.year) as cumulative_low_mtco2,
    em.total_mtco2                                   as actual_mtco2,
    -- Grid intensity in a no-wind-or-solar world (high case), for comparison with the actual
    1000 * (em.total_mtco2 + sa.wind_solar_twh * em.coal_mtco2 / sa.coal_twh) / sa.generation_twh
                                                     as counterfactual_gco2_per_kwh
from sa
join em using (year)
order by sa.year
