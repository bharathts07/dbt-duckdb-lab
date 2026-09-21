# Stage 1 Pain Points

This table records what stage 1 costs in human effort, and what dbt does instead. Task 3 fills the last two columns.

| Exercise | What stage 1 cost | dbt answer | dbt feature |
|----------|-------------------|------------|-------------|
| **1. The renumber problem** | You need a new model that must run between 03 and 04. Create `stage1/sql/03a_stg_fx_rates.sql` with `select currency, rate_to_usd, rate_date from raw.fx_rates where upper(trim(currency)) = currency`. Then edit `05_int_orders_fx.sql` to join on `s1.stg_fx_rates` instead of `raw.fx_rates`. What do you have to do to the other filenames? | | |
| **2. The rename** | Rename `customer_id` to `cust_id` in `03_stg_customers.sql`. Before running, predict which files will break. Then run `./stage1/run.sh` and count how many files you had to fix. Did `grep customer_id stage1/sql/*.sql` find them all? | | |
| **3. Which do I rerun** | You changed `02_stg_shopify_orders.sql`. Which of the six files must you rerun to propagate the change? How do you know? | | |
| **4. The silent wrong number** | Run `uv run python generate/gen.py --dirty-currency && ./stage1/run.sh`. Then check the revenue total again. It is lower than the baseline and every file reported success. Why did rows drop? What would have had to exist for this to fail loudly instead? | | |

Task 3 will demonstrate how dbt solves each of these.
