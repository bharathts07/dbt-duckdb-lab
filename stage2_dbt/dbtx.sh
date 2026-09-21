#!/usr/bin/env bash
# dbt overwrites run_results.json on every run, so it keeps no history.
# An on-run-end hook cannot fix that: hooks render to SQL with no shell escape,
# and run_results.json is written AFTER hooks finish. Hence a wrapper. This is
# why every dbt observability product is an external consumer.
set -uo pipefail
cd "$(dirname "$0")"; export DBT_PROFILES_DIR=.
uv run dbt "$@"; EXIT=$?
uv run python - <<'PY'
import json, shutil
from pathlib import Path
rr = Path("target/run_results.json")
if not rr.exists(): raise SystemExit(0)
m = json.loads(rr.read_text()).get("metadata", {})
stamp = m.get("generated_at","").replace("-","").replace(":","").split(".")[0]
dest = Path("../stage3/history")/f"{stamp}-{(m.get('invocation_id') or 'unknown')[:8]}"
dest.mkdir(parents=True, exist_ok=True)
for n in ["manifest.json","run_results.json","catalog.json","sources.json"]:
    p = Path("target")/n
    if p.exists(): shutil.copy2(p, dest/n)
print(f"archived -> {dest}")
PY
exit $EXIT
