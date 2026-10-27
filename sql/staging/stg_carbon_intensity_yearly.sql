-- Grid carbon intensity: grams of CO2 per kWh generated.
select
    entity,
    cast(date as integer)               as year,
    emissions_intensity_gco2_per_kwh    as gco2_per_kwh
from raw.ember_carbon_intensity_yearly
