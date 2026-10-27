select
    date        as month,
    demand_twh
from raw.ember_demand_monthly
where entity_code = 'ZAF'
