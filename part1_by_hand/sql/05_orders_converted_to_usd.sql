-- reads: built_by_hand.all_orders_combined, raw.currency_exchange_rates
-- breaks if: 04 did not run. ALSO silently drops any row whose currency does
--            not match a rate. Nothing warns. That is exercise 4.
create or replace table built_by_hand.orders_converted_to_usd as
select o.*, f.rate_to_usd, o.amount * f.rate_to_usd as amount_usd
from built_by_hand.all_orders_combined o
join raw.currency_exchange_rates f
  on f.currency = o.currency and f.rate_date = cast(o.created_at as date);
