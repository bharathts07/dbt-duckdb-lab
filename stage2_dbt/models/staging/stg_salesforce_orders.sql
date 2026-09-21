-- reads: {{ source('raw', 'salesforce_orders') }}
-- breaks if: gen.py has not run. Nothing here can tell you that.
select order_id, customer_id, amount, currency, created_at from {{ source('raw', 'salesforce_orders') }}
