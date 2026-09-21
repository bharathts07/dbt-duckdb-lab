-- reads: built_by_hand.cleaned_salesforce_orders, built_by_hand.cleaned_shopify_orders, built_by_hand.cleaned_customers
-- breaks if: 01, 02 or 03 did not run. You get "Table does not exist" and it
--            does not tell you which of the three is missing.
create or replace table built_by_hand.all_orders_combined as
select 'salesforce' as source_system, cast(order_id as varchar) as order_key,
       customer_id, amount, currency, created_at
from built_by_hand.cleaned_salesforce_orders
union all
select 'shopify' as source_system, s.order_key, c.customer_id,
       s.amount, s.currency, s.created_at
from built_by_hand.cleaned_shopify_orders s
left join built_by_hand.cleaned_customers c on c.email = s.email;
