-- reads: s1.stg_salesforce_orders, s1.stg_shopify_orders, s1.stg_customers
-- breaks if: 01, 02 or 03 did not run. You get "Table does not exist" and it
--            does not tell you which of the three is missing.
create or replace table s1.int_orders as
select 'salesforce' as source_system, cast(order_id as varchar) as order_key,
       customer_id, amount, currency, created_at
from s1.stg_salesforce_orders
union all
select 'shopify' as source_system, s.order_key, c.customer_id,
       s.amount, s.currency, s.created_at
from s1.stg_shopify_orders s
left join s1.stg_customers c on c.email = s.email;
