#!/usr/bin/env bash
# Execution order is the filename order and nothing else. There is no
# dependency graph here. Insert a file between 03 and 04 and you renumber
# by hand. That is exercise 1.
set -euo pipefail
cd "$(dirname "$0")"
DB="${DB:-../analytics.duckdb}"
START=$(date +%s)
# Create schema built_by_hand (required for fresh clone / deleted DB)
uv run python -c "import duckdb; duckdb.connect('$DB').execute('create schema if not exists built_by_hand').close()"
for f in sql/*.sql; do
  echo "--- $f"
  uv run python -c "
import duckdb,sys
con=duckdb.connect('$DB')
try: con.execute(open('$f').read())
finally: con.close()"
done
echo "part 1 done in $(( $(date +%s) - START ))s"
