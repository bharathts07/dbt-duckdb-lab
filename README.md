# dbt + DuckDB Lab

A hands-on learning repo demonstrating how dbt transforms SQL workflows. Built around a dual-pipeline reconciliation scenario: Salesforce and Shopify orders merge into one revenue table, with explicit exercises showing what breaks without dbt and how dbt solves it.


**Start with [`docs/how-dbt-works.md`](docs/how-dbt-works.md)** for what this lab
demonstrates and what dbt turned out to be worth. This file covers layout and commands.

## Schema

```
raw_customers              raw_salesforce_orders      raw_shopify_orders      raw_currency_exchange_rates
    |                           |                           |                      |
    |                           |                           |                      |
    v                           v                           v                      v
cleaned_customers          cleaned_salesforce_orders  cleaned_shopify_orders  (currency_exchange_rates in raw)
    |                           |                           |                      |
    +---------------------------+---------------------------+                      |
                                |                                                  |
                                v                                                  |
                          all_orders_combined ------------------------------------------+
                                |                                                  |
                                v                                                  |
                          orders_converted_to_usd <--------------------------------------+
                                |
                                v
                           revenue_per_day
```

Four sources, six models (three staging views, three marts tables), six data tests, and one singular test asserting parity between stage 1 and stage 2 pipelines.

## Commands

```bash
# Regenerate data (flags: --dirty-currency, --null-customer, --late-shopify)
uv run python generate/gen.py

# Run the part 1 SQL pipeline (no dbt)
bash part1_by_hand/run.sh

# Run the part 2 dbt pipeline
cd part2_with_dbt && DBT_PROFILES_DIR=. uv run dbt build

# Run and archive artifacts (enables inspect.py and viz.py)
./part2_with_dbt/run_dbt_and_save_history.sh build

# Inspect archived runs
uv run python part3_look_at_artifacts/inspect.py runs                           # list all runs with invocation IDs
uv run python part3_look_at_artifacts/inspect.py dag                            # latest run
uv run python part3_look_at_artifacts/inspect.py dag --run 20260921T070059-...  # specific run
uv run python part3_look_at_artifacts/inspect.py blast cleaned_shopify_orders
uv run python part3_look_at_artifacts/inspect.py timing

# Generate DAG.md and lineage.html
uv run python part3_look_at_artifacts/viz.py
```

## Reading Order

1. **README.md** (this file) for the overall structure
2. **PAIN.md** for the six exercises demonstrating problems that dbt solves
3. **LOG.md** to see build measurements and findings
4. **DAG.md** for the mermaid dependency graph
5. **part3_look_at_artifacts/lineage.html** for an interactive offline visualization

## Warnings

- **dbt_temp schema**: dbt may create a temporary schema (default name `dbt_temp`) for intermediate operations. This is expected behavior and not a bug.

- **DuckDB single-writer lock**: DuckDB enforces single-writer access. If you have the `duckdb` CLI open on the same database file, dbt will fail at connect time with `Could not set lock on file`. Close the CLI before running dbt commands.

## Artifacts

The `run_dbt_and_save_history.sh` wrapper archives `target/*.json` after every run into `part3_look_at_artifacts/history/<timestamp>-<invocation8>/`. This is necessary because dbt overwrites `run_results.json` on every invocation and keeps no run history. An `on-run-end` hook cannot archive artifacts: hooks render to SQL with no shell escape, and `run_results.json` is written after hooks finish.

`inspect.py` compares `metadata.invocation_id` across `manifest.json` and `run_results.json` because `dbt source freshness` rewrites one but not the other. Without this check, joining run results into manifest nodes can render empty SQL for every node with no explanation.

The `timing` command shows model execution times. At this scale (50K rows), all models take roughly the same time and the numbers are measurement noise. The view demonstrates the mechanism and where the data comes from; it becomes informative at real scale where one model typically dominates wall clock.

### Run history is not committed

`part3_look_at_artifacts/history/` is gitignored. Two reasons: dbt records the absolute
path it was invoked from inside every `run_results.json`, so committing them would publish
whoever's machine produced them, and the timings in someone else's runs tell you nothing
about yours.

Create your own in a few seconds:

```bash
cd part2_with_dbt
./run_dbt_and_save_history.sh build
./run_dbt_and_save_history.sh test
cd .. && uv run python part3_look_at_artifacts/inspect.py runs
```

**See the artifact mismatch yourself.** `inspect.py` warns when a run's two JSON files
disagree about which dbt invocation produced them. That is a real thing, not a contrived one,
and you can cause it in two commands:

```bash
cd part2_with_dbt
DBT_PROFILES_DIR=. uv run dbt build            # both files agree
DBT_PROFILES_DIR=. uv run dbt source freshness # now they do not
python3 -c "import json;[print(f, json.load(open(f'target/{f}.json'))['metadata']['invocation_id']) for f in ['manifest','run_results']]"
```

`dbt source freshness` rewrites `manifest.json` but never writes a new `run_results.json`, so
after that second command the two files in `target/` describe different runs. If a tool joined
them together it would show you every model with empty SQL and no explanation of why. That is
the trap `inspect.py` checks for.

The archived runs under `part3_look_at_artifacts/history/` all have matching IDs, because
`run_dbt_and_save_history.sh` refuses to archive a run that produced no new results.

## What Makes This a Learning Repo

This lab is designed to teach by contrast. Six exercises in `PAIN.md` introduce real pipeline problems (the renumber problem, the rename, which-do-I-rerun, dirty currency codes, missing rows, and null customers), then demonstrate how dbt's built-in features solve them. Part 1 is hand-written SQL with no abstractions. Part 2 uses dbt's `ref()`, tests, and dependency inference. The singular test `assert_parity` verifies that both pipelines produce identical output.

## What These Would Be Called in a Real Project

This lab uses plain, self-explanatory names so nothing has to be decoded while learning. In a professional dbt project, you will see models prefixed by their role in the pipeline.

Common prefixes and what they mean:

- **`stg_`** (staging): One model per source table. Light cleanup only (renaming, casting, trimming). No business logic, no joins. The raw-to-clean boundary.
- **`int_`** (intermediate): Joins, reshaping, and calculations between staging and the final tables. Not meant for end users. Working tables that build toward the business layer.
- **`fct_`** (fact): The business-facing table of events or transactions. Usually numeric, one row per thing that happened (an order, a pageview, a login).
- **`dim_`** (dimension): The business-facing table describing entities. One row per customer, product, or campaign.
- **`fx`**: Standard shorthand for foreign exchange (currency conversion).

Here is how this lab's models would be named in a production project:

| This lab's name | Professional convention |
|-----------------|-------------------------|
| `cleaned_salesforce_orders` | `stg_salesforce_orders` |
| `cleaned_shopify_orders` | `stg_shopify_orders` |
| `cleaned_customers` | `stg_customers` |
| `all_orders_combined` | `int_orders` |
| `orders_converted_to_usd` | `int_orders_fx` |
| `revenue_per_day` | `fct_daily_revenue` |

This lab uses the plain names so nothing has to be decoded while learning. The convention is worth recognizing later, because every dbt codebase you encounter in an interview or on the job will follow it.
