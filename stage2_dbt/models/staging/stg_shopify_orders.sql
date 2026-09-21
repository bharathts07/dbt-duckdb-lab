-- reads: {{ source('raw', 'shopify_orders') }}
-- breaks if: gen.py has not run
select order_ref              as order_key,
       cust_email             as email,
       total_cents / 100.0    as amount,
       upper(trim(curr))      as currency,
       placed_at              as created_at
from {{ source('raw', 'shopify_orders') }}
