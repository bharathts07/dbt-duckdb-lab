-- reads: {{ ref('int_orders_fx') }}
-- breaks if: 05 did not run
select cast(created_at as date) as revenue_date, source_system,
       count(*) as order_count, sum(amount_usd) as revenue_usd
from {{ ref('int_orders_fx') }}
group by 1, 2
