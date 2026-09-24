# How dbt works, and what it is worth

Notes on what this lab demonstrates. Start here.

## The short version

**dbt runs your SQL in dependency order, and runs the checks you wrote. It has no
opinion about whether your data is correct.**

Most of what dbt is assumed to do, it does not do. The rest of this page is the
evidence, measured in this repo.

## Three mechanisms

**1. Order is derived from the code, not maintained by hand.**

Instead of naming a table directly, a model references another model:

```sql
from built_by_hand.all_orders_combined      -- part 1, by hand
from {{ ref('all_orders_combined') }}       -- part 2, dbt
```

`ref()` does two jobs. At build time it resolves to a real schema-qualified table name,
which is how one file writes to a dev schema or a prod schema with no edit. And it
declares a dependency edge. **The execution order is written down nowhere. dbt derives
it from the `ref()` calls.**

**2. Only the declared checks run.**

Two kinds of test:

- **Generic tests**, declared in YAML. Four built in: `unique`, `not_null`,
  `accepted_values` (every value is in this list), `relationships` (every value exists
  in another table's column).
- **Singular tests**, which are a plain `.sql` file. The rule is that **a test fails if
  its query returns any rows.** `part2_with_dbt/tests/assert_parity.sql` is one.

**3. A failed check blocks everything downstream.**

Tests on a model run before the models that depend on it. When a test fails, downstream
nodes are marked SKIP and never execute. A bad value therefore does not reach the final
table and then get flagged; it never reaches it.

## What the four experiments measured

Each row was run in both pipelines against identical data.

| Data defect | Part 1, by hand | Part 2, dbt | What dbt was worth |
|---|---|---|---|
| 100 currency values dirtied, for example `"USD "` with a trailing space | All six files reported success. Revenue understated by $40,766, silently | `accepted_values` failed, build stopped, the incorrect total was never written | **Prevented a wrong answer from existing** |
| A column renamed that a downstream model reads | Aborted at file 04. Files 05 and 06 never ran, leaving a stale total from the previous run with no record of the partial update | Three tests errored, four nodes SKIPPED **and enumerated**, with the correct column name suggested in the error | **Reported what did not run** |
| 81 rows removed before they arrived | Revenue dropped. Nothing reported a problem | **Passed 13/13.** Revenue dropped identically. Both pipelines agreed with each other and both were wrong | **Nothing** |
| A new model inserted mid-pipeline | Either rename three files or name it `03a` and accept that ordering now depends on filename sort | One file plus one `ref()`. Nothing renamed | **Removed ordering as a decision** |

**The third row is the most important.** No test could detect the missing rows, because
every test inspects rows that exist. An absent row is not invalid; there is nothing to
inspect. Only comparing an aggregate against a previously recorded baseline caught it,
and nothing in this repo automates that comparison.

## What dbt does not do

| Not dbt's job | Whose it is |
|---|---|
| Scheduling. No cron, no triggers, no event handling | Airflow, Dagster, dbt Cloud jobs, or cron |
| Loading data into the warehouse | Fivetran, Airbyte, Kafka, or a custom loader |
| Computing anything | The warehouse. dbt generates SQL and sends it |
| Judging whether data is correct | Whoever writes the tests |
| Retaining any history of its own runs | Nothing. The file is overwritten every run |

The last row has commercial consequences, covered next.

## The artifact layer

Every dbt run writes JSON to `part2_with_dbt/target/`. Two files carry almost everything:

- **`manifest.json`** is the project, serialised: every model, its compiled SQL, its
  config, and what it depends on. 632 KB for this six-model project.
- **`run_results.json`** is the record of one invocation: status, timing, and messages.

The load-bearing field is `depends_on.nodes` on each model. Read it across all nodes and
**the complete lineage graph is available as data**, with no dbt library involved.
`part3_look_at_artifacts/inspect.py` does this in four imports, none of them dbt.

This is why the artifact layer matters beyond a teaching repo. **Every dbt lineage and
observability product is built by parsing these two files:** Monte Carlo, Elementary,
Datafold, Atlan, dbt Cloud's own lineage view, and Pantomath's dbt connector among them.
dbt overwrites `run_results.json` on every invocation and retains no history, which is
part of why a market exists to capture and keep it.

`inspect.py blast cleaned_shopify_orders` answers "if this breaks, what else is
affected?" That one question is a large share of what data observability sells.

## Details that are easy to get wrong

- **`accepted_values` reports distinct offending values, not offending rows.** A result
  of `FAIL 8` in this lab means 8 distinct bad values spread across 100 affected rows.
- **A renamed column does not fail at compile time.** dbt resolves *model* references
  during parsing and never resolves *columns*. The model builds successfully carrying
  the renamed column; its tests then fail at runtime with a binder error. The observed
  result is `PASS=6 ERROR=3 SKIP=4`.
- **The two artifact files can describe different invocations.** `dbt source freshness`
  rewrites `manifest.json` and leaves `run_results.json` untouched. A tool reading both
  then reports timings from one run against models from another, and the output looks
  entirely plausible, which is more dangerous than an obvious failure. `inspect.py`
  compares the two `invocation_id` values and refuses to print rather than printing
  wrong numbers beneath a warning.
- **DuckDB permits a single writer.** An open `duckdb` CLI session on the database file
  makes dbt fail at connect time, not at query time.

## Reproducing all of it

```bash
rm -f analytics.duckdb
uv run python generate/gen.py            # 4 source tables, ~75k rows, under a second
./part1_by_hand/run.sh                   # part 1, six numbered SQL files

cd part2_with_dbt
DBT_PROFILES_DIR=. uv run dbt build      # part 2, expect PASS=13
```

The reference values on clean data: **60 rows in `revenue_per_day`, total revenue
31987050.73.** Record this before introducing any defect, because for missing rows it is
the only available detector.

Defects are injected through the generator, and both pipelines are then rebuilt:

```bash
uv run python generate/gen.py --dirty-currency   # dbt catches it, part 1 does not
uv run python generate/gen.py --null-customer    # dbt catches it, part 1 does not
uv run python generate/gen.py --late-shopify     # NEITHER catches it
```

## Deliberately not covered

Listed in the README under "Deliberately out of scope": incremental models, snapshots,
model contracts, unit tests, and slim CI. The most instructive omission is **incremental
models**, whose failure mode is sharper than anything demonstrated here: a watermark of
the form `where created_at > max(created_at)` never collects rows that arrive late with
an earlier timestamp, no test fires because the rows are absent rather than invalid, and
the table remains quietly wrong until a full refresh.

## Where to go next

1. This page, for what the lab establishes.
2. `README.md`, for layout, commands, and two behaviours that otherwise look like bugs.
3. `PAIN.md`, for the six exercises with their measured answers.
4. `LOG.md`, for the build diary and raw measurements, only if the numbers matter.
