# Spec Format

Use a JSON object with these top-level keys:

```json
{
  "graphIntent": {
    "primaryType": "dag",
    "secondaryTypes": ["clustered"],
    "confidence": 0.85,
    "evidence": ["Requirements emphasize module dependencies and build order"],
    "extractionFocus": ["extract directional dependency edges", "identify entry and exit nodes"],
    "fallbackType": "cyclic_dependency"
  },
  "layoutPlan": {
    "strategy": "layered",
    "direction": "right",
    "root": null,
    "mainPath": [],
    "clusters": [],
    "spacing": {
      "nodeGap": 180,
      "layerGap": 320,
      "clusterGap": 420,
      "minGap": 200
    },
    "seed": 7
  },
  "routingPlan": {
    "insertConnectPoints": false
  },
  "metadata": { "version": "2.2.0" },
  "tags": [],
  "references": { "sections": {}, "files": [] },
  "attachments": [],
  "objects": []
}
```

`graphIntent` and `layoutPlan` are optional for backward compatibility. When omitted, `prg_cli.py generate` classifies the graph from `objects` and applies a default native layout unless `--layout off` is passed.

`routingPlan` is optional. It records whether the workflow should insert `ConnectPoint` detours after overlap validation. The default is `false`; set `insertConnectPoints` to `true` only when edge-through-block routing should be enforced.

## Graph Intent

Use `graphIntent` before extracting objects. It controls which entities, groups, and edge semantics should be captured.

Required fields when present:

- `primaryType`: one of `tree`, `mindmap`, `dag`, `cyclic_dependency`, `dense_network`, `pipeline`, `clustered`
- `confidence`: number between `0` and `1`
- `evidence`: short reasons for the type choice
- `extractionFocus`: extraction rules implied by the graph type
- `fallbackType`: graph type to use if script metrics contradict the primary type

Optional:

- `secondaryTypes`: extra signals such as `clustered` for a DAG with Sections

## Layout Plan

Use `layoutPlan` to make the generated `.prg` deterministic and reviewable.

Fields:

- `strategy`: one of `tree`, `mindmap`, `layered`, `scc-layered`, `force`, `pipeline`, `clustered`
- `direction`: one of `right`, `left`, `down`, `up`; default is `right`
- `root`: node id used by `tree` and `mindmap`
- `mainPath`: ordered node ids used by `pipeline`
- `clusters`: list of `{ "id": "...", "label": "...", "nodes": ["node-id"] }`; `clustered` falls back to `Section` membership
- `spacing.nodeGap`: minimum sibling lane spacing before `minGap` normalization; default `180`
- `spacing.layerGap`: minimum layer spacing before `minGap` normalization; default `320`
- `spacing.clusterGap`: minimum cluster-box spacing before `minGap` normalization; default `420`
- `spacing.minGap`: required edge-to-edge clearance; default `200`
- `seed`: deterministic seed for force-like layouts; default `7`

Strategy guide:

| Graph type | Strategy | Use when |
|---|---|---|
| `tree` | `tree` | A root-to-child hierarchy or forest with at most one parent per node. |
| `mindmap` | `mindmap` | A central idea fans out into first-level branches and details. |
| `dag` | `layered` | Directional dependencies, prerequisites, or build/order flow without cycles. |
| `cyclic_dependency` | `scc-layered` | Dependencies include feedback loops or mutual references. |
| `dense_network` | `force` | Many peer relationships and no credible hierarchy. |
| `pipeline` | `pipeline` | A dominant main path with side inputs, outputs, or checks. |
| `clustered` | `clustered` | Nodes belong to explicit groups, Sections, subsystems, or swimlanes. |

Before generating, run:

```bash
uv run --with msgpack --python 3.12 scripts/prg_cli.py classify spec.json
```

If the reported `hasCycles`, `density`, `component_count`, or `root_count` contradicts `graphIntent`, update `graphIntent` and `layoutPlan` before generating.

## Object Types

### `TextNode`

```json
{
  "id": "title",
  "type": "TextNode",
  "text": "Example",
  "x": 100,
  "y": 50,
  "width": 220,
  "height": 76,
  "fontScaleLevel": 1
}
```

### `Section`

```json
{
  "id": "sec-a",
  "type": "Section",
  "text": "Section Title",
  "children": ["title", "node-b"]
}
```

Children must reference existing object ids.

### `LineEdge`

```json
{
  "id": "edge-a",
  "type": "LineEdge",
  "from": "node-a",
  "to": "node-b",
  "text": "0.2",
  "sourceRate": [0.98, 0.35],
  "targetRate": [0.02, 0.35]
}
```

### `MultiTargetUndirectedEdge`

```json
{
  "id": "edge-b",
  "type": "MultiTargetUndirectedEdge",
  "endpoints": ["node-a", "node-b", "node-c"],
  "text": "关联"
}
```

### `UrlNode`

```json
{
  "id": "link-a",
  "type": "UrlNode",
  "title": "Docs",
  "url": "https://example.com",
  "x": 600,
  "y": 80,
  "width": 280,
  "height": 150
}
```

### `ImageNode` and `SvgNode`

Provide `attachmentId` and a matching attachment entry:

```json
{
  "attachments": [
    { "id": "asset-svg", "source": "C:/path/icon.svg" }
  ],
  "objects": [
    {
      "id": "svg-a",
      "type": "SvgNode",
      "attachmentId": "asset-svg",
      "x": 0,
      "y": 0,
      "width": 100,
      "height": 100
    }
  ]
}
```

### `ConnectPoint`

```json
{
  "id": "cp-a",
  "type": "ConnectPoint",
  "x": 200,
  "y": 200
}
```

### `PenStroke`

```json
{
  "id": "draw-a",
  "type": "PenStroke",
  "segments": [
    { "x": 20, "y": 20, "pressure": 1 },
    { "x": 60, "y": 40, "pressure": 1 },
    { "x": 90, "y": 25, "pressure": 1 }
  ]
}
```

## Expected Validation File

Use this shape with `validate_prg.py --expect expect.json`:

```json
{
  "texts": ["Program Counter", "ALU"],
  "sections": ["Fetch", "Memory"],
  "edges": [
    ["Next-PC select", "Program Counter"],
    ["ALU", "EX/MEM Register"]
  ]
}
```
