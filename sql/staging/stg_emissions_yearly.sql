-- Power-sector CO2 by entity, year and fuel (non-aggregate series only).
select
    entity,
    cast(date as integer)  as year,
    series                 as fuel,
    emissions_mtco2
from raw.ember_emissions_yearly
where not is_aggregate_series
