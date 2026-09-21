#!/usr/bin/env bash
# Execution order is the filename order and nothing else. There is no
# dependency graph here. Insert a file between 03 and 04 and you renumber
# by hand. That is exercise 4.
set -euo pipefail
cd "$(dirname "$0")"
DB="${DB:-../analytics.duckdb}"
START=$(date +%s)
for f in sql/*.sql; do
  echo "--- $f"
  uv run python -c "
import duckdb,sys
con=duckdb.connect('$DB')
try: con.execute(open('$f').read())
finally: con.close()"
done
echo "stage 1 done in $(( $(date +%s) - START ))s"
