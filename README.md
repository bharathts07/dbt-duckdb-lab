# dbt + DuckDB Lab

A hands-on learning repo demonstrating how dbt transforms SQL workflows. Built around a dual-pipeline reconciliation scenario: Salesforce and Shopify orders merge into one revenue table, with explicit exercises showing what breaks without dbt and how dbt solves it.

## Schema

```
raw_customers              raw_salesforce_orders      raw_shopify_orders      raw_fx_rates
    |                           |                           |                      |
    |                           |                           |                      |
    v                           v                           v                      v
stg_customers              stg_salesforce_orders      stg_shopify_orders      stg_fx_rates
    |                           |                           |                      |
    +---------------------------+---------------------------+                      |
                                |                                                  |
                                v                                                  |
                           int_orders -----------------------------------------------+
                                |                                                  |
                                v                                                  |
                           int_orders_fx <------------------------------------------+
                                |
                                v
                           daily_revenue
```

Four sources, seven models (four staging views, three marts tables), six data tests, and one singular test asserting parity between stage 1 and stage 2 pipelines.

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
uv run python stage3/inspect.py runs                           # list all runs with invocation IDs
uv run python stage3/inspect.py dag                            # latest run
uv run python stage3/inspect.py dag --run 20260921T070059-...  # specific run
uv run python stage3/inspect.py blast stg_shopify_orders
uv run python stage3/inspect.py timing

# Generate DAG.md and lineage.html
uv run python stage3/viz.py
```

## Reading Order

1. **README.md** (this file) for the overall structure
2. **PAIN.md** for the six exercises demonstrating problems that dbt solves
3. **LOG.md** to see build measurements and findings
4. **DAG.md** for the mermaid dependency graph
5. **stage3/lineage.html** for an interactive offline visualization

## Warnings

- **dbt_temp schema**: dbt may create a temporary schema (default name `dbt_temp`) for intermediate operations. This is expected behavior and not a bug.

- **DuckDB single-writer lock**: DuckDB enforces single-writer access. If you have the `duckdb` CLI open on the same database file, dbt will fail at connect time with `Could not set lock on file`. Close the CLI before running dbt commands.

## Artifacts

The `dbtx.sh` wrapper archives `target/*.json` after every run into `stage3/history/<timestamp>-<invocation8>/`. This is necessary because dbt overwrites `run_results.json` on every invocation and keeps no run history. An `on-run-end` hook cannot archive artifacts: hooks render to SQL with no shell escape, and `run_results.json` is written after hooks finish.

`inspect.py` compares `metadata.invocation_id` across `manifest.json` and `run_results.json` because `dbt source freshness` rewrites one but not the other. Without this check, joining run results into manifest nodes can render empty SQL for every node with no explanation.

The `timing` command shows model execution times. At this scale (50K rows), all models take roughly the same time and the numbers are measurement noise. The view demonstrates the mechanism and where the data comes from; it becomes informative at real scale where one model typically dominates wall clock.

**Preserved artifact:** The mixed-invocation pair in `stage3/history/` is a wrapper artifact from before the skip-if-identical guard was added. It demonstrates a real dbt behavior: `dbt source freshness` updates `manifest.json` with one invocation_id, writes `sources.json` with a different one, and produces no `run_results.json` at all. The pair is kept deliberately as proof that the desync is a real failure mode, not a contrived example, and as a test case for `inspect.py`'s detector.

## What Makes This a Learning Repo

This lab is designed to teach by contrast. Six exercises in `PAIN.md` introduce real pipeline problems (the renumber problem, the rename, which-do-I-rerun, dirty currency codes, missing rows, and null customers), then demonstrate how dbt's built-in features solve them. Stage 1 is hand-written SQL with no abstractions. Stage 2 uses dbt's `ref()`, tests, and dependency inference. The singular test `assert_parity` verifies that both pipelines produce identical output.
