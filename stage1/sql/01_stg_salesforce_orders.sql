-- reads: raw.salesforce_orders
-- breaks if: gen.py has not run. Nothing here can tell you that.
create or replace table s1.stg_salesforce_orders as
select order_id, customer_id, amount, currency, created_at from raw.salesforce_orders;
