# What I learned

Written 2026-09-23, after building this twice and breaking it four times.
Read this first if you are coming back cold. It takes two minutes.

## The one-line version

**dbt runs your SQL in the right order, and runs the checks you wrote. It has no
opinion about whether your data is correct.**

If you remember one sentence, that is the one. Most of what people assume dbt does,
it does not do.

## How it works, in three parts

**1. It figures out the order from your code.**

Instead of naming a table directly, you write `ref()`:

```sql
from built_by_hand.all_orders_combined      -- doing it by hand
from {{ ref('all_orders_combined') }}       -- in dbt
```

That one change does two jobs. At build time it becomes a real table name, which is
also how the same file can write to a dev schema or a prod schema without editing.
And it records that this model comes after that one. **You never write the order down
anywhere. dbt reads the `ref()` calls and works it out.**

**2. It runs only the checks you wrote.**

Two kinds:

- **Generic tests**, declared in YAML. Four built-in names: `unique`, `not_null`,
  `accepted_values` (is every value in this list), `relationships` (does every value
  here exist in that other table).
- **Singular tests**, which are just a `.sql` file. Rule: **if the query returns any
  rows, the test failed.** `part2_with_dbt/tests/assert_parity.sql` is one.

**3. It refuses to build on top of a failure.**

Tests run *before* the models that depend on them, not after. So when a test fails,
everything downstream is marked SKIP and never runs. That is why a bad number never
gets written, rather than getting written and then flagged.

## The four things I actually tried

| What I did to the data | Doing it by hand | With dbt | What it proves |
|---|---|---|---|
| Made 100 currency values dirty, like `"USD "` with a trailing space | All six files reported success. Revenue came out $40,766 too low and nothing said a word | `accepted_values` failed, build stopped, the wrong number was never written at all | dbt's value here was **preventing a wrong answer from existing** |
| Renamed a column that another model reads | Died on file 04. Files 05 and 06 never ran, so revenue silently kept a stale number from the previous run | 3 tests errored, 4 things SKIPPED **and it listed which four**, plus suggested the right column name | dbt's value here was **telling me what did not run** |
| Deleted 81 rows that should have arrived | Revenue dropped. Nothing complained | **Passed 13/13.** Revenue dropped by the same amount. Both were confidently wrong together | dbt's value here was **nothing at all** |
| Added a new model that has to run in the middle | Had to either renumber three files or name it `03a` and start a slide into chaos | Added a file, wrote one `ref()`. Nothing to renumber | dbt's value here was **never making me think about ordering** |

**Row three is the most important one.** It is what separates understanding dbt from
being a fan of it. No test could catch those missing rows, because every test inspects
rows that exist. A row that never arrived is not invalid, it is absent, and there is
nothing there to check. The only thing that caught it was me comparing against a number
I had written down beforehand.

## What dbt does not do

| It does not | That job belongs to |
|---|---|
| Schedule anything. No cron, no triggers | Airflow, Dagster, dbt Cloud jobs, or a cron job |
| Get data into the warehouse | Fivetran, Airbyte, Kafka, or a custom loader |
| Do any computing itself | The warehouse. dbt just sends it SQL |
| Know if your data is right | You, by writing tests |
| Keep any history of its own runs | Nothing. It overwrites the file every time |

That last one surprised me most and it explains a whole industry. See below.

## The JSON files, and why they matter commercially

Every dbt run writes JSON into `part2_with_dbt/target/`. Think of two notebooks:

- **`manifest.json` is the recipe book.** Every model, its compiled SQL, and what it
  depends on. 632 KB for this six-model project.
- **`run_results.json` is the diary.** What ran this time, the status, the timing.

The field that matters is `depends_on.nodes` on each model. Read it for every model and
**you have the entire lineage graph, as data.** No dbt library needed, just `json.load`.
`part3_look_at_artifacts/inspect.py` does exactly that and has four imports, none of
them dbt.

That is why this matters beyond the lab. **Every dbt lineage and observability product
works by parsing these two files.** Monte Carlo, Elementary, Datafold, Atlan, dbt
Cloud's own lineage view, and Pantomath's dbt connector. dbt discards `run_results.json`
on every run, which is why those products exist to capture and keep it.

`inspect.py blast cleaned_shopify_orders` answers "if this breaks, what else is
affected?" That single question is most of what data observability sells.

## Gotchas that cost me time

- **`accepted_values` reports distinct bad values, not bad rows.** `FAIL 8` meant 8
  distinct bad values across 100 affected rows. I misread this at first.
- **Renaming a column does not fail at compile time.** dbt resolves *model* references
  when it parses, but never *columns*. The model builds fine carrying the renamed
  column, and its tests fail afterwards at runtime. I had this wrong in writing before
  I tested it.
- **The two JSON files can describe different runs.** `dbt source freshness` rewrites
  `manifest.json` and leaves `run_results.json` alone. Then a tool reading both shows
  timings from one run against models from another, and the numbers look completely
  plausible. That is worse than obviously broken. `inspect.py` compares the two stamps
  and now refuses to print rather than printing wrong numbers under a warning.
- **DuckDB allows one writer at a time.** If you have the `duckdb` CLI open on the file,
  dbt fails the moment it tries to connect.

## How to run everything again

```bash
cd /Users/bswamy/github.com/bharathts07/dbt-duckdb-lab

# clean slate
rm -f analytics.duckdb
uv run python generate/gen.py            # 4 source tables, ~75k rows, under a second
./part1_by_hand/run.sh                   # the by-hand version, 6 numbered SQL files

cd part2_with_dbt
DBT_PROFILES_DIR=. uv run dbt build      # the dbt version, should be PASS=13
```

The baseline to compare everything against: **60 rows, total revenue 31987050.73.**
Write that down before you break anything, because it is the only thing that catches
missing rows.

To break it on purpose, add a flag to the generator and rerun both:

```bash
uv run python generate/gen.py --dirty-currency   # dbt catches it, by hand does not
uv run python generate/gen.py --null-customer    # dbt catches it, by hand does not
uv run python generate/gen.py --late-shopify     # NEITHER catches it
```

## What I have not done yet

Deliberately left out, listed in the README under "Deliberately out of scope":
incremental models, snapshots, model contracts, unit tests, and slim CI. The one most
worth doing next is **incremental models**, because its failure mode is the sharpest
thing left: a watermark like `where created_at > max(created_at)` never picks up rows
that arrive late with an older timestamp, no test fires, and the table stays quietly
wrong until a full refresh.

## Reading order when I come back

1. **This file**, for what it was all for.
2. **`README.md`**, for the layout and the two gotchas that otherwise look like bugs.
3. **`PAIN.md`**, for the six exercises with their answers, if I want to redo one.
4. **`LOG.md`** only if I want the build diary and the raw measurements.
