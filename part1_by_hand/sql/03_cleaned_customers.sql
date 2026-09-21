-- reads: raw.customers
-- breaks if: gen.py has not run
create or replace table built_by_hand.cleaned_customers as
select customer_id, email, country from raw.customers;
