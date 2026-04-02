# Spec Format

Use a JSON object with these top-level keys:

```json
{
  "metadata": { "version": "2.2.0" },
  "tags": [],
  "references": { "sections": {}, "files": [] },
  "attachments": [],
  "objects": []
}
```

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
