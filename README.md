# dbt + DuckDB Lab

A hands-on learning repo demonstrating how dbt transforms SQL workflows. Built around a dual-pipeline reconciliation scenario: Salesforce and Shopify orders merge into one revenue table, with explicit exercises showing what breaks without dbt and how dbt solves it.

## Schema

```
raw_customers              raw_salesforce_orders      raw_shopify_orders
    |                           |                           |
    |                           |                           |
    v                           v                           v
stg_customers              stg_salesforce_orders      stg_shopify_orders
    |                           |                           |
    +---------------------------+---------------------------+
                                |
                                v
                           int_orders -----> int_orders_fx
                                                    |
                                                    v
                                              daily_revenue
```

Three sources, six models (three staging views, three marts tables), six data tests, and one singular test asserting parity between stage 1 and stage 2 pipelines.

## Commands

```bash
# Regenerate data (flags: --dirty-currency, --null-customer, --late-shopify)
uv run python generate/gen.py

# Run the stage 1 SQL pipeline (no dbt)
bash stage1/run.sh

# Run the stage 2 dbt pipeline
cd stage2_dbt && DBT_PROFILES_DIR=. uv run dbt build

# Run and archive artifacts (enables inspect.py and viz.py)
./stage2_dbt/dbtx.sh build

# Inspect archived runs
uv run python stage3/inspect.py dag
uv run python stage3/inspect.py blast stg_shopify_orders
uv run python stage3/inspect.py timing

# Generate DAG.md and lineage.html
uv run python stage3/viz.py
```

## Reading Order

1. **README.md** (this file) for the overall structure
2. **LOG.md** to see the development sequence and what was learned
3. **PAIN.md** for the five exercises demonstrating problems that dbt solves
4. **DAG.md** for the mermaid dependency graph
5. **stage3/lineage.html** for an interactive offline visualization

## Warnings

- **dbt_temp schema**: dbt creates a temporary schema (default name `dbt_temp`) for intermediate operations. This is expected behavior and not a bug.

- **DuckDB single-writer lock**: DuckDB enforces single-writer access. If you have the `duckdb` CLI open on the same database file, dbt will fail at connect time with `Could not set lock on file`. Close the CLI before running dbt commands.

## Artifacts

The `dbtx.sh` wrapper archives `target/*.json` after every run into `stage3/history/<timestamp>-<invocation8>/`. This is necessary because dbt overwrites `run_results.json` on every invocation and keeps no run history. An `on-run-end` hook cannot archive artifacts: hooks render to SQL with no shell escape, and `run_results.json` is written after hooks finish.

`inspect.py` compares `metadata.invocation_id` across `manifest.json` and `run_results.json` because `dbt source freshness` rewrites one but not the other. Without this check, joining run results into manifest nodes can render empty SQL for every node with no explanation.

## What Makes This a Learning Repo

This lab is designed to teach by contrast. Five exercises in `PAIN.md` introduce real pipeline problems (dirty currency codes, null customers, late-arriving rows, schema drift, parity checks), then demonstrate how dbt's built-in features solve them. Stage 1 is hand-written SQL with no abstractions. Stage 2 uses dbt's `ref()`, tests, and dependency inference. The singular test `assert_parity` verifies that both pipelines produce identical output.
