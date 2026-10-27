-- One row per month per fuel. Ember also ships pre-summed series ("Total generation",
-- "Renewables", "Fossil", ...) flagged is_aggregate_series; we drop those so nothing
-- gets double-counted, and rebuild totals ourselves in the marts.
select
    date                     as month,
    series                   as fuel,
    case
        when series in ('Coal', 'Gas', 'Other fossil') then 'Fossil'
        when series = 'Nuclear'                        then 'Nuclear'
        when series = 'Net imports'                    then 'Imports'
        else                                                'Renewable'
    end                      as fuel_group,
    generation_twh,
    share_of_generation_pct  as share_pct
from raw.ember_generation_monthly
where not is_aggregate_series
  and entity_code = 'ZAF'
