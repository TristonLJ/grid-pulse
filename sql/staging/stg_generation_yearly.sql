-- One row per entity per year per fuel, for SA's peers and the World/Africa benchmarks.
-- Same rules as the monthly model: drop Ember's pre-summed series, keep net imports
-- flagged separately so domestic generation can exclude them.
select
    entity,
    entity_code,
    is_aggregate_entity      as is_benchmark,
    cast(date as integer)    as year,
    series                   as fuel,
    case
        when series in ('Coal', 'Gas', 'Other fossil') then 'Fossil'
        when series = 'Nuclear'                        then 'Nuclear'
        when series = 'Net imports'                    then 'Imports'
        else                                                'Renewable'
    end                      as fuel_group,
    generation_twh
from raw.ember_generation_yearly
where not is_aggregate_series
