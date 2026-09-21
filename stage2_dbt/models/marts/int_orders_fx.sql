-- reads: {{ ref('int_orders') }}, {{ source('raw', 'fx_rates') }}
-- breaks if: 04 did not run. ALSO silently drops any row whose currency does
--            not match a rate. Nothing warns. That is exercise 3.
select o.*, f.rate_to_usd, o.amount * f.rate_to_usd as amount_usd
from {{ ref('int_orders') }} o
join {{ source('raw', 'fx_rates') }} f
  on f.currency = o.currency and f.rate_date = cast(o.created_at as date)
