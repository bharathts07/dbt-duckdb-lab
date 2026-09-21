-- reads: raw.shopify_orders
-- breaks if: gen.py has not run
create or replace table s1.stg_shopify_orders as
select order_ref              as order_key,
       cust_email             as email,
       total_cents / 100.0    as amount,
       upper(trim(curr))      as currency,
       placed_at              as created_at
from raw.shopify_orders;
