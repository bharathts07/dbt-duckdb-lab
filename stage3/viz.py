#!/usr/bin/env python3
"""
Generate DAG.md (mermaid graph) and lineage.html (offline SVG visualization).
Standard library only.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Set


def sanitize_mermaid_id(s: str) -> str:
    """Replace dots with underscores for mermaid node IDs."""
    return s.replace(".", "_")


def generate_dag_md(manifest: Dict[str, Any], output_path: Path) -> None:
    """Generate mermaid graph from manifest dependencies."""
    nodes = manifest.get("nodes", {})

    # Build edge list
    edges = []
    for unique_id, node in nodes.items():
        name = node.get("name", "")
        depends_on = node.get("depends_on", {}).get("nodes", [])

        for dep_id in depends_on:
            dep_node = nodes.get(dep_id, {})
            dep_name = dep_node.get("name", dep_id)
            edges.append((dep_name, name))

    # Write mermaid file
    with output_path.open("w") as f:
        f.write("# DAG\n\n")
        f.write("```mermaid\n")
        f.write("graph LR\n")

        seen = set()
        for src, dst in sorted(edges):
            src_id = sanitize_mermaid_id(src)
            dst_id = sanitize_mermaid_id(dst)
            edge = f"  {src_id} --> {dst_id}\n"
            if edge not in seen:
                f.write(edge)
                seen.add(edge)

        f.write("```\n")

    print(f"Generated {output_path}")


def generate_lineage_html(manifest: Dict[str, Any], run_results: Dict[str, Any], output_path: Path) -> None:
    """
    Generate self-contained HTML with embedded data, vanilla JS, hand-written SVG.
    No CDN, no external dependencies. Works offline from disk.
    """
    nodes = manifest.get("nodes", {})

    # Build execution time index
    exec_times = {}
    for result in run_results.get("results", []):
        unique_id = result.get("unique_id")
        exec_time = result.get("execution_time", 0)
        if unique_id:
            exec_times[unique_id] = exec_time

    # Extract models only, group by layer
    layers = {"staging": [], "marts": []}
    for unique_id, node in nodes.items():
        if node.get("resource_type") != "model":
            continue

        name = node.get("name", "")
        fqn = node.get("fqn", [])
        layer = fqn[-2] if len(fqn) > 2 else "other"

        if layer in layers:
            sql = node.get("compiled_code") or node.get("raw_code", "")
            exec_time = exec_times.get(unique_id, 0)
            depends_on = node.get("depends_on", {}).get("nodes", [])
            dep_names = [nodes.get(d, {}).get("name", "") for d in depends_on if nodes.get(d, {}).get("resource_type") == "model"]

            layers[layer].append({
                "name": name,
                "sql": sql,
                "exec_time": exec_time,
                "deps": dep_names
            })

    # Serialize payload
    payload = json.dumps(layers).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>dbt Lineage</title>
  <style>
    body {{
      margin: 0;
      padding: 20px;
      font-family: system-ui, sans-serif;
      background: #1a1a1a;
      color: #e0e0e0;
    }}
    #container {{
      max-width: 1400px;
      margin: 0 auto;
    }}
    h1 {{
      margin-bottom: 10px;
    }}
    svg {{
      background: #2a2a2a;
      border: 1px solid #444;
      border-radius: 4px;
    }}
    .node {{
      cursor: pointer;
    }}
    .node rect {{
      fill: #3a3a3a;
      stroke: #666;
      stroke-width: 2;
    }}
    .node.staging rect {{
      fill: #2d4a5a;
    }}
    .node.marts rect {{
      fill: #4a3a2d;
    }}
    .node.highlight rect {{
      stroke: #ff6b6b;
      stroke-width: 3;
    }}
    .node text {{
      fill: #e0e0e0;
      font-size: 12px;
      pointer-events: none;
    }}
    .edge {{
      stroke: #666;
      stroke-width: 2;
      fill: none;
      marker-end: url(#arrowhead);
    }}
    .edge.highlight {{
      stroke: #ff6b6b;
      stroke-width: 3;
    }}
    .timing-bar {{
      fill: #4a8f6a;
      rx: 2;
    }}
    #tooltip {{
      position: absolute;
      background: #333;
      border: 1px solid #666;
      padding: 10px;
      border-radius: 4px;
      pointer-events: none;
      display: none;
      max-width: 600px;
      font-size: 12px;
      z-index: 1000;
    }}
    #tooltip code {{
      display: block;
      white-space: pre-wrap;
      background: #1a1a1a;
      padding: 8px;
      border-radius: 3px;
      margin-top: 5px;
      font-size: 11px;
      max-height: 300px;
      overflow-y: auto;
    }}
  </style>
</head>
<body>
  <div id="container">
    <h1>dbt Lineage</h1>
    <p>Click a node to highlight downstream dependencies. Hover for SQL.</p>
    <svg id="graph" width="1200" height="600"></svg>
  </div>
  <div id="tooltip"></div>

  <script>
    const data = {payload};

    const svg = document.getElementById('graph');
    const tooltip = document.getElementById('tooltip');

    const width = 1200;
    const height = 600;
    const nodeWidth = 160;
    const nodeHeight = 50;
    const layerGap = 400;
    const leftMargin = 100;

    // Position nodes in columns
    const layers = ['staging', 'marts'];
    const positions = {{}};
    const nodes = [];

    layers.forEach((layer, layerIdx) => {{
      const layerNodes = data[layer];
      const x = leftMargin + layerIdx * layerGap;
      const verticalGap = Math.max(80, (height - 100) / Math.max(1, layerNodes.length - 1));

      layerNodes.forEach((node, i) => {{
        const y = 50 + i * verticalGap;
        positions[node.name] = {{ x, y, layer }};
        nodes.push(node);
      }});
    }});

    // Build edge list
    const edges = [];
    nodes.forEach(node => {{
      node.deps.forEach(dep => {{
        if (positions[dep] && positions[node.name]) {{
          edges.push({{ from: dep, to: node.name }});
        }}
      }});
    }});

    // Draw edges
    const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    edgeGroup.setAttribute('id', 'edges');
    svg.appendChild(edgeGroup);

    // Arrow marker
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '10');
    marker.setAttribute('markerHeight', '10');
    marker.setAttribute('refX', '9');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', '0 0, 10 3, 0 6');
    polygon.setAttribute('fill', '#666');
    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.appendChild(defs);

    edges.forEach(edge => {{
      const from = positions[edge.from];
      const to = positions[edge.to];

      const x1 = from.x + nodeWidth;
      const y1 = from.y + nodeHeight / 2;
      const x2 = to.x;
      const y2 = to.y + nodeHeight / 2;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const d = `M ${{x1}} ${{y1}} C ${{x1 + 100}} ${{y1}}, ${{x2 - 100}} ${{y2}}, ${{x2}} ${{y2}}`;
      path.setAttribute('d', d);
      path.setAttribute('class', 'edge');
      path.setAttribute('data-from', edge.from);
      path.setAttribute('data-to', edge.to);
      edgeGroup.appendChild(path);
    }});

    // Draw nodes
    const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodeGroup.setAttribute('id', 'nodes');
    svg.appendChild(nodeGroup);

    nodes.forEach(node => {{
      const pos = positions[node.name];
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', `node ${{pos.layer}}`);
      g.setAttribute('data-name', node.name);

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', pos.x);
      rect.setAttribute('y', pos.y);
      rect.setAttribute('width', nodeWidth);
      rect.setAttribute('height', nodeHeight);
      rect.setAttribute('rx', 4);
      g.appendChild(rect);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', pos.x + nodeWidth / 2);
      text.setAttribute('y', pos.y + nodeHeight / 2 - 8);
      text.setAttribute('text-anchor', 'middle');
      text.textContent = node.name;
      g.appendChild(text);

      // Timing bar
      if (node.exec_time > 0) {{
        const barWidth = Math.min(120, node.exec_time * 100);
        const bar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bar.setAttribute('class', 'timing-bar');
        bar.setAttribute('x', pos.x + 20);
        bar.setAttribute('y', pos.y + 32);
        bar.setAttribute('width', barWidth);
        bar.setAttribute('height', 4);
        g.appendChild(bar);

        const timeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        timeText.setAttribute('x', pos.x + nodeWidth / 2);
        timeText.setAttribute('y', pos.y + nodeHeight / 2 + 12);
        timeText.setAttribute('text-anchor', 'middle');
        timeText.setAttribute('style', 'font-size: 10px; fill: #999;');
        timeText.textContent = `${{node.exec_time.toFixed(2)}}s`;
        g.appendChild(timeText);
      }}

      // Hover
      g.addEventListener('mouseenter', e => {{
        tooltip.style.display = 'block';
        tooltip.innerHTML = `<strong>${{node.name}}</strong><br>Layer: ${{pos.layer}}<br>Time: ${{node.exec_time.toFixed(2)}}s<code>${{node.sql.substring(0, 500)}}</code>`;
      }});

      g.addEventListener('mousemove', e => {{
        tooltip.style.left = (e.pageX + 15) + 'px';
        tooltip.style.top = (e.pageY + 15) + 'px';
      }});

      g.addEventListener('mouseleave', () => {{
        tooltip.style.display = 'none';
      }});

      // Click to highlight downstream
      g.addEventListener('click', () => {{
        // Clear highlights
        document.querySelectorAll('.node').forEach(n => n.classList.remove('highlight'));
        document.querySelectorAll('.edge').forEach(e => e.classList.remove('highlight'));

        // Find downstream
        const downstream = new Set([node.name]);
        const queue = [node.name];

        while (queue.length > 0) {{
          const current = queue.shift();
          edges.forEach(edge => {{
            if (edge.from === current && !downstream.has(edge.to)) {{
              downstream.add(edge.to);
              queue.push(edge.to);
            }}
          }});
        }}

        // Highlight
        downstream.forEach(name => {{
          const nodeEl = document.querySelector(`[data-name="${{name}}"]`);
          if (nodeEl) nodeEl.classList.add('highlight');
        }});

        edges.forEach(edge => {{
          if (downstream.has(edge.from) && downstream.has(edge.to)) {{
            const edgeEl = document.querySelector(`[data-from="${{edge.from}}"][data-to="${{edge.to}}"]`);
            if (edgeEl) edgeEl.classList.add('highlight');
          }}
        }});
      }});

      nodeGroup.appendChild(g);
    }});
  </script>
</body>
</html>
"""

    output_path.write_text(html)
    print(f"Generated {output_path} ({len(html)} bytes)")


def main() -> None:
    # Load latest archived run
    history = Path(__file__).parent / "history"
    if not history.exists():
        print("No history directory. Run dbtx.sh first.")
        return

    dirs = sorted([d for d in history.iterdir() if d.is_dir()], reverse=True)
    if not dirs:
        print("No archived runs found.")
        return

    latest = dirs[0]
    manifest_path = latest / "manifest.json"
    run_results_path = latest / "run_results.json"

    if not manifest_path.exists():
        print(f"manifest.json not found in {latest.name}")
        return

    manifest = json.loads(manifest_path.read_text())
    run_results = json.loads(run_results_path.read_text()) if run_results_path.exists() else {}

    # Generate outputs
    repo_root = Path(__file__).parent.parent
    generate_dag_md(manifest, repo_root / "DAG.md")
    generate_lineage_html(manifest, run_results, Path(__file__).parent / "lineage.html")


if __name__ == "__main__":
    main()
