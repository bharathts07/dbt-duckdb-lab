-- reads: raw.customers
-- breaks if: gen.py has not run
create or replace table s1.stg_customers as
select customer_id, email, country from raw.customers;
