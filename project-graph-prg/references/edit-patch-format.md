# Edit Patch Format

Use a UTF-8 JSON file with an `operations` array.

```json
{
  "operations": [
    {
      "op": "update",
      "target": { "type": "TextNode", "text": "ALU" },
      "set": {
        "text": "ALU Core",
        "details": "运算核心\n由 patch 写入"
      }
    }
  ]
}
```

## Selector Format

Selectors are used by `target`, `from`, `to`, `section`, and `edge`.

Supported fields:

- `path`: exact top-level stage path such as `"/21"`
- `uuid`: exact object UUID
- `type`: exact serialized type such as `TextNode`, `Section`, `LineEdge`
- `text`: exact `text` field match
- `text_contains`: substring match against `text`
- `title`: exact `title` field match
- `title_contains`: substring match against `title`
- `label`: exact display label match
- `label_contains`: substring match against display label
- `edge_text`: exact edge text match
- `edge_text_contains`: substring match against edge text
- `source_label`: exact source label for `LineEdge`
- `target_label`: exact target label for `LineEdge`

By default, operations expect exactly one match. Use `"mode": "all"` on operations that should affect multiple objects.

## Supported Operations

## `update`

Update fields on one or more matched objects.

```json
{
  "op": "update",
  "mode": "all",
  "target": { "type": "TextNode", "text_contains": "缓存" },
  "set": {
    "text": "Buffer"
  }
}
```

Supported `set` fields:

- `text`
- `title`
- `url`
- `details`
- `color`
- `fontScaleLevel`
- `sizeAdjust`
- `lineType`
- `locked`
- `isCollapsed`
- `scale`
- `isBackground`
- `x`
- `y`
- `width`
- `height`

`details` accepts either a Plate/Slate block array or a plain string. Plain strings are converted to paragraph blocks line by line.

## `append_details`

Append plain text or block arrays to an object's `details`.

```json
{
  "op": "append_details",
  "target": { "text": "ALU Core" },
  "value": "补充说明"
}
```

## `move`

Move matched objects by delta or set absolute top-left coordinates.

```json
{
  "op": "move",
  "target": { "text": "ALU Core" },
  "dx": 120,
  "dy": 0
}
```

Or:

```json
{
  "op": "move",
  "target": { "text": "ALU Core" },
  "x": 800,
  "y": 240
}
```

## `resize`

Resize matched objects.

```json
{
  "op": "resize",
  "target": { "text": "ALU Core" },
  "width": 220,
  "height": 90
}
```

## `add_text_node`

Append a new text node to the stage.

```json
{
  "op": "add_text_node",
  "text": "级间寄存器",
  "x": 520,
  "y": 180,
  "width": 140,
  "height": 76,
  "details": "由 patch 新增"
}
```

## `add_url_node`

Append a new URL node to the stage.

## `add_section`

Append a new `Section`. `children` is a list of selectors.

```json
{
  "op": "add_section",
  "text": "执行阶段",
  "children": [
    { "text": "ALU Core" },
    { "text": "EX/MEM Register" }
  ]
}
```

## `add_edge`

Create a new edge. `edgeType` defaults to `LineEdge`.

```json
{
  "op": "add_edge",
  "from": { "text": "ALU Core" },
  "to": { "text": "EX/MEM Register" },
  "text": "result"
}
```

For `MultiTargetUndirectedEdge`, provide `edgeType: "MultiTargetUndirectedEdge"` and an `endpoints` selector list.

## `insert_node_between`

Find one existing `LineEdge`, insert a new `TextNode` in the middle, rewrite the original edge, and add a second edge.

```json
{
  "op": "insert_node_between",
  "from": { "text": "A" },
  "to": { "text": "B" },
  "node": {
    "text": "中间块",
    "width": 120,
    "height": 76
  }
}
```

You can also target the edge directly:

```json
{
  "op": "insert_node_between",
  "edge": { "type": "LineEdge", "source_label": "A", "target_label": "B" },
  "node": { "text": "中间块" }
}
```

## `add_to_section`

Append references to existing nodes into a section.

```json
{
  "op": "add_to_section",
  "section": { "type": "Section", "text": "执行阶段" },
  "targets": [
    { "text": "ALU Core" },
    { "text": "EX/MEM Register" }
  ]
}
```

## `remove_from_section`

Remove references from a section without deleting the objects themselves.

## `delete`

Delete matched top-level objects. By default, `cascade` is `true`, so dependent edges are also removed and section child references are cleaned up.

```json
{
  "op": "delete",
  "target": { "text": "临时节点" },
  "cascade": true
}
```

## Recommended Edit Workflow

1. Inspect the existing `.prg` first.
2. Build a UTF-8 edit patch.
3. Run `prg_cli.py edit`.
4. Run `prg_cli.py validate`.
5. If there are operator blocks, run `prg_cli.py validate-op`.
6. Run `prg_cli.py overlap` last.
7. Only use repair commands after reading the validation output.
