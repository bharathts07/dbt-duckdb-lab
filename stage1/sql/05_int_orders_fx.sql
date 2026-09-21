-- reads: s1.int_orders, raw.fx_rates
-- breaks if: 04 did not run. ALSO silently drops any row whose currency does
--            not match a rate. Nothing warns. That is exercise 3.
create or replace table s1.int_orders_fx as
select o.*, f.rate_to_usd, o.amount * f.rate_to_usd as amount_usd
from s1.int_orders o
join raw.fx_rates f
  on f.currency = o.currency and f.rate_date = cast(o.created_at as date);
