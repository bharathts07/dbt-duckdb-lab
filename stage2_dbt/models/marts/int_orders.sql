-- reads: {{ ref('stg_salesforce_orders') }}, {{ ref('stg_shopify_orders') }}, {{ ref('stg_customers') }}
-- breaks if: 01, 02 or 03 did not run. You get "Table does not exist" and it
--            does not tell you which of the three is missing.
select 'salesforce' as source_system, cast(order_id as varchar) as order_key,
       customer_id, amount, currency, created_at
from {{ ref('stg_salesforce_orders') }}
union all
select 'shopify' as source_system, s.order_key, c.customer_id,
       s.amount, s.currency, s.created_at
from {{ ref('stg_shopify_orders') }} s
left join {{ ref('stg_customers') }} c on c.email = s.email
