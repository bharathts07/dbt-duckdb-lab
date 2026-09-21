-- reads: {{ source('raw', 'customers') }}
-- breaks if: gen.py has not run
select customer_id, email, country from {{ source('raw', 'customers') }}
