# Build Log

Measurements and findings from constructing this lab.

## 2026-09-20: Generator performance

First version wrote 75,000 rows in 28.1s using row-by-row `cursor.execute()` inside a loop. Each `INSERT` was an individual transaction, so DuckDB flushed to disk 75,000 times. Wrapping the entire generation loop in one transaction reduced this to 23.5s. Switching from individual `execute()` calls to `executemany()` (which binds parameters in bulk rather than per-row) dropped it to 0.605s. Final speedup: 46x.

Lesson: per-row transactions are the bottleneck in synthetic data generation, not the row count. Parameter binding matters, but transaction boundaries matter more.

## 2026-09-20: Stage 1 baseline

Clean data (no defects injected):

```
rows:    60
revenue: 31987050.73
```

This is the parity target. Stage 2 must reproduce this number exactly when run on the same clean data.

## 2026-09-20: Stage 2 parity confirmed

`dbt build` on clean data: 13 nodes, PASS=13. `assert_parity` test passes, confirming stage 1 and stage 2 produce identical revenue totals.

Command: `cd stage2_dbt && DBT_PROFILES_DIR=. uv run dbt build`

## 2026-09-20: Selection syntax and blast radius

`dbt ls --select stg_shopify_orders+` returns 5 nodes: stg_shopify_orders, int_orders, int_orders_fx, daily_revenue, and assert_parity. This matches the expected downstream blast radius.

`uv run python stage3/inspect.py blast stg_shopify_orders` also returns 5 results, but for a different reason: dbt's count includes test nodes (the parity test depends on daily_revenue), while `inspect.py` counts only models reachable via `depends_on.nodes` and filters to `resource_type == "model"`. Both are correct for their respective purposes.

## 2026-09-20: Lineage visualization

Generated `stage3/lineage.html` from archived artifacts. File size 12,108 bytes, works offline from disk, no CDN dependencies. Click a node to highlight downstream subgraph, hover for compiled SQL. Timing bars display execution time from `run_results.json`.

## 2026-09-20: Invocation ID desync artifact

The mixed-invocation pair preserved in `stage3/history/` demonstrates a real dbt behavior: `dbt source freshness` updates `manifest.json` but writes a different `invocation_id` in `sources.json`, leaving no `run_results.json` at all. Before the skip-if-identical guard was added to `dbtx.sh`, the wrapper archived the stale `run_results.json` from the prior `build` invocation into a directory named for the freshness invocation, creating a mismatch. The desync detector in `inspect.py` catches this: invocation_id `57ba3c31...` in one artifact vs. `3e7d264c...` in another, both in the same archived directory. This directory pair is kept deliberately as proof that the desync is a real failure mode, not a contrived example, and as a test case for the detector.
