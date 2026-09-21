#!/usr/bin/env python3
"""
Offline inspector for dbt artifacts. Standard library only.
Reads manifest.json + run_results.json from archived runs.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_artifacts(run_dir: Optional[str] = None) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Load an archived run. If run_dir is None, loads the latest.
    Compare invocation_id across manifest and run_results because
    dbt source freshness rewrites one and not the other.
    """
    history = Path(__file__).parent / "history"
    if not history.exists():
        print("No history directory found. Run run_dbt_and_save_history.sh first.", file=sys.stderr)
        sys.exit(1)

    if run_dir:
        target = history / run_dir
        if not target.exists() or not target.is_dir():
            print(f"Run directory not found: {run_dir}", file=sys.stderr)
            sys.exit(1)
    else:
        dirs = sorted([d for d in history.iterdir() if d.is_dir()], reverse=True)
        if not dirs:
            print("No archived runs found.", file=sys.stderr)
            sys.exit(1)
        target = dirs[0]

    manifest_path = target / "manifest.json"
    run_results_path = target / "run_results.json"

    if not manifest_path.exists() or not run_results_path.exists():
        print(f"Missing artifacts in {target.name}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    run_results = json.loads(run_results_path.read_text())

    # Check for desync
    manifest_id = manifest.get("metadata", {}).get("invocation_id", "")
    run_results_id = run_results.get("metadata", {}).get("invocation_id", "")

    if manifest_id != run_results_id:
        print("=" * 80, file=sys.stderr)
        print("WARNING: INVOCATION_ID MISMATCH", file=sys.stderr)
        print(f"manifest.json:     {manifest_id}", file=sys.stderr)
        print(f"run_results.json:  {run_results_id}", file=sys.stderr)
        print("These artifacts are from DIFFERENT invocations.", file=sys.stderr)
        print("'dbt source freshness' rewrites manifest but not run_results.", file=sys.stderr)
        print("Joining run results into manifest nodes will render empty SQL.", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print()

    # Build execution time index
    exec_times = {}
    for result in run_results.get("results", []):
        unique_id = result.get("unique_id")
        exec_time = result.get("execution_time", 0)
        if unique_id:
            exec_times[unique_id] = exec_time

    return manifest, run_results, exec_times


def cmd_dag(manifest: Dict[str, Any], exec_times: Dict[str, float]) -> None:
    """Print all nodes with layer and materialization."""
    nodes = manifest.get("nodes", {})

    # Group by resource_type
    models = []
    tests = []
    others = []

    for unique_id, node in nodes.items():
        resource_type = node.get("resource_type", "")
        if resource_type == "model":
            models.append(node)
        elif resource_type == "test":
            tests.append(node)
        else:
            others.append(node)

    if models:
        print("MODELS:")
        for node in sorted(models, key=lambda n: n.get("name", "")):
            name = node.get("name", "")
            layer = node.get("fqn", [])[-2] if len(node.get("fqn", [])) > 2 else "root"
            mat = node.get("config", {}).get("materialized", "view")
            print(f"  {name:30} layer={layer:15} mat={mat}")
        print()

    if tests:
        print(f"TESTS: {len(tests)} tests")
        print()

    if others:
        print(f"OTHER: {len(others)} nodes")


def cmd_blast(manifest: Dict[str, Any], target: str) -> None:
    """Print everything downstream of target node."""
    nodes = manifest.get("nodes", {})

    # Find target node
    target_id = None
    for unique_id, node in nodes.items():
        if node.get("name") == target or unique_id == target:
            target_id = unique_id
            break

    if not target_id:
        print(f"Node '{target}' not found", file=sys.stderr)
        sys.exit(1)

    # Build reverse dependency graph
    downstream = {}
    for unique_id, node in nodes.items():
        depends_on = node.get("depends_on", {}).get("nodes", [])
        for dep in depends_on:
            if dep not in downstream:
                downstream[dep] = []
            downstream[dep].append(unique_id)

    # BFS to find all downstream nodes
    visited = set()
    queue = [target_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        for child in downstream.get(current, []):
            if child not in visited:
                queue.append(child)

    # Print results
    print(f"Downstream of {target} ({len(visited)} nodes including self):")
    for unique_id in sorted(visited):
        node = nodes.get(unique_id, {})
        name = node.get("name", unique_id)
        print(f"  {name}")


def cmd_timing(manifest: Dict[str, Any], run_results: Dict[str, Any], exec_times: Dict[str, float]) -> None:
    """
    Print models sorted by execution time descending.

    Note: At small scale (50K rows), all models take roughly the same time
    and the numbers are measurement noise. This view shows the mechanism and
    where the data comes from; it becomes informative at real scale.
    """
    nodes = manifest.get("nodes", {})
    elapsed = run_results.get("elapsed_time", 0)

    # Get models with execution times
    model_times = []
    for unique_id, node in nodes.items():
        if node.get("resource_type") == "model":
            name = node.get("name", "")
            exec_time = exec_times.get(unique_id, 0)
            if exec_time > 0:
                pct = (exec_time / elapsed * 100) if elapsed > 0 else 0
                model_times.append((name, exec_time, pct))

    # Sort by execution time descending
    model_times.sort(key=lambda x: x[1], reverse=True)

    print(f"Total elapsed: {elapsed:.2f}s")
    print()
    print("TIMING (models only):")
    for name, exec_time, pct in model_times:
        print(f"  {name:30} {exec_time:6.2f}s  {pct:5.1f}%")


def cmd_runs() -> None:
    """List all archived runs with invocation IDs and flag mismatches."""
    history = Path(__file__).parent / "history"
    if not history.exists():
        print("No history directory found.", file=sys.stderr)
        sys.exit(1)

    dirs = sorted([d for d in history.iterdir() if d.is_dir()], reverse=True)
    if not dirs:
        print("No archived runs found.", file=sys.stderr)
        sys.exit(1)

    print(f"Archived runs ({len(dirs)}):")
    print()
    for d in dirs:
        manifest_path = d / "manifest.json"
        run_results_path = d / "run_results.json"

        if not manifest_path.exists() or not run_results_path.exists():
            print(f"  {d.name:30} [missing artifacts]")
            continue

        manifest = json.loads(manifest_path.read_text())
        run_results = json.loads(run_results_path.read_text())

        m_id = manifest.get("metadata", {}).get("invocation_id", "")[:8]
        r_id = run_results.get("metadata", {}).get("invocation_id", "")[:8]

        flag = "MISMATCH" if m_id != r_id else "ok"
        print(f"  {d.name:30} manifest={m_id} run_results={r_id} [{flag}]")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: inspect.py <command> [args] [--run <dirname>]")
        print("Commands:")
        print("  runs             - list all archived runs with invocation IDs")
        print("  dag              - print nodes with layer and materialization")
        print("  blast <name>     - print everything downstream of node")
        print("  timing           - print models sorted by execution time")
        print()
        print("Options:")
        print("  --run <dirname>  - inspect specific run (default: latest)")
        sys.exit(1)

    # Parse --run flag
    run_dir = None
    args = sys.argv[1:]
    if "--run" in args:
        idx = args.index("--run")
        if idx + 1 >= len(args):
            print("Error: --run requires a directory name", file=sys.stderr)
            sys.exit(1)
        run_dir = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if not args:
        print("Error: command required", file=sys.stderr)
        sys.exit(1)

    cmd = args[0]

    if cmd == "runs":
        cmd_runs()
    elif cmd == "dag":
        manifest, run_results, exec_times = load_artifacts(run_dir)
        cmd_dag(manifest, exec_times)
    elif cmd == "blast":
        if len(args) < 2:
            print("Usage: inspect.py blast <node_name>", file=sys.stderr)
            sys.exit(1)
        manifest, run_results, exec_times = load_artifacts(run_dir)
        cmd_blast(manifest, args[1])
    elif cmd == "timing":
        manifest, run_results, exec_times = load_artifacts(run_dir)
        cmd_timing(manifest, run_results, exec_times)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
