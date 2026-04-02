from __future__ import annotations

import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import msgpack


REQUIRED_ARCHIVE_ENTRIES = {
    "stage.msgpack",
    "tags.msgpack",
    "reference.msgpack",
    "metadata.msgpack",
}

NODE_TYPES = {"TextNode", "UrlNode", "ImageNode", "SvgNode", "ConnectPoint"}
EDGE_TYPES = {"LineEdge", "MultiTargetUndirectedEdge"}
CONTAINER_TYPES = {"Section"}
DRAWING_TYPES = {"PenStroke"}
SUPPORTED_OBJECT_TYPES = NODE_TYPES | EDGE_TYPES | CONTAINER_TYPES | DRAWING_TYPES
OPERATION_BLOCK_PATTERN = re.compile(r"^#.+#$")


@dataclass(slots=True)
class PrgDocument:
    path: Path
    stage: list[Any]
    metadata: dict[str, Any]
    tags: list[Any]
    references: dict[str, Any]
    attachments: dict[str, bytes]


@dataclass(slots=True)
class RectBounds:
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(self.width, 0) * max(self.height, 0)


def vector(x: float, y: float) -> dict[str, Any]:
    return {"_": "Vector", "x": _rounded(x), "y": _rounded(y)}


def color(value: Any | None = None) -> dict[str, Any]:
    if value is None:
        return {"_": "Color", "r": 0, "g": 0, "b": 0, "a": 0}
    if isinstance(value, dict):
        if "_" in value:
            return value
        return {
            "_": "Color",
            "r": int(value.get("r", 0)),
            "g": int(value.get("g", 0)),
            "b": int(value.get("b", 0)),
            "a": int(value.get("a", 0)),
        }
    if isinstance(value, (list, tuple)) and len(value) == 4:
        r, g, b, a = value
        return {"_": "Color", "r": int(r), "g": int(g), "b": int(b), "a": int(a)}
    raise TypeError(f"Unsupported color value: {value!r}")


def collision_box(x: float, y: float, width: float, height: float) -> dict[str, Any]:
    return {
        "_": "CollisionBox",
        "shapes": [
            {
                "_": "Rectangle",
                "location": vector(x, y),
                "size": vector(width, height),
            }
        ],
    }


def read_prg(path: str | Path) -> PrgDocument:
    archive_path = Path(path).resolve()
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        missing = sorted(REQUIRED_ARCHIVE_ENTRIES - names)
        if missing:
            raise ValueError(f"Missing archive entries: {', '.join(missing)}")
        return PrgDocument(
            path=archive_path,
            stage=_unpack_msgpack(archive.read("stage.msgpack")),
            metadata=_unpack_msgpack(archive.read("metadata.msgpack")),
            tags=_unpack_msgpack(archive.read("tags.msgpack")),
            references=_unpack_msgpack(archive.read("reference.msgpack")),
            attachments={name.removeprefix("attachments/"): archive.read(name) for name in archive.namelist() if name.startswith("attachments/")},
        )


def write_prg(
    output_path: str | Path,
    *,
    stage: list[Any],
    metadata: dict[str, Any] | None = None,
    tags: list[Any] | None = None,
    references: dict[str, Any] | None = None,
    attachments: dict[str, bytes] | None = None,
) -> Path:
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("stage.msgpack", _pack_msgpack(stage))
        archive.writestr("metadata.msgpack", _pack_msgpack(metadata or {"version": "2.2.0"}))
        archive.writestr("tags.msgpack", _pack_msgpack(tags or []))
        archive.writestr("reference.msgpack", _pack_msgpack(references or {"sections": {}, "files": []}))
        for name, payload in sorted((attachments or {}).items()):
            archive.writestr(f"attachments/{name}", payload)
    return target


def load_generate_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def generate_prg_from_spec(spec: dict[str, Any]) -> tuple[list[Any], dict[str, bytes], dict[str, Any], list[Any], dict[str, Any]]:
    objects = spec.get("objects", [])
    if not isinstance(objects, list) or not objects:
        raise ValueError("Spec must contain a non-empty 'objects' list.")

    id_to_index: dict[str, int] = {}
    stage: list[dict[str, Any]] = []
    for index, item in enumerate(objects):
        object_id = item.get("id")
        if object_id:
            if object_id in id_to_index:
                raise ValueError(f"Duplicate object id: {object_id}")
            id_to_index[object_id] = index
        stage.append({})

    for index, item in enumerate(objects):
        stage[index] = _build_object(item, id_to_index)

    attachments = _load_attachments(spec.get("attachments", []))
    metadata = spec.get("metadata") or {"version": "2.2.0"}
    tags = spec.get("tags") or []
    references = spec.get("references") or {"sections": {}, "files": []}
    return stage, attachments, metadata, tags, references


def inspect_document(document: PrgDocument, *, sample_limit: int = 20) -> dict[str, Any]:
    stage_summary = summarize_stage(document.stage, sample_limit=sample_limit)
    validation = validate_document(document)
    return {
        "path": str(document.path),
        "metadata": document.metadata,
        "tags_count": len(document.tags),
        "reference_file_count": len(document.references.get("files", [])) if isinstance(document.references, dict) else 0,
        "references": document.references,
        "attachment_count": len(document.attachments),
        "attachments": [
            {"name": name, "size": len(payload), "extension": Path(name).suffix.lower()}
            for name, payload in sorted(document.attachments.items())
        ],
        "stage_summary": stage_summary,
        "validation": validation,
    }


def summarize_stage(stage: list[Any], *, sample_limit: int = 20) -> dict[str, Any]:
    path_map = collect_paths(stage)
    counts: dict[str, int] = {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    drawings: list[dict[str, Any]] = []
    reference_count = 0

    for path, item in walk_serialized(stage):
        if isinstance(item, dict) and "$" in item:
            reference_count += 1
            continue
        if not isinstance(item, dict) or "_" not in item:
            continue
        class_name = item["_"]
        counts[class_name] = counts.get(class_name, 0) + 1

        if class_name in NODE_TYPES:
            nodes.append(
                {
                    "path": path,
                    "type": class_name,
                    "uuid": item.get("uuid"),
                    "label": _label_for_object(item),
                }
            )
        elif class_name in EDGE_TYPES:
            edges.append(
                {
                    "path": path,
                    "type": class_name,
                    "uuid": item.get("uuid"),
                    "label": item.get("text", ""),
                    "endpoints": [_endpoint_summary(path_map, ref) for ref in item.get("associationList", [])],
                }
            )
        elif class_name == "Section":
            sections.append(
                {
                    "path": path,
                    "uuid": item.get("uuid"),
                    "text": item.get("text", ""),
                    "child_count": len(item.get("children", [])),
                }
            )
        elif class_name == "PenStroke":
            drawings.append(
                {
                    "path": path,
                    "type": class_name,
                    "uuid": item.get("uuid"),
                    "segment_count": len(item.get("segments", [])),
                }
            )

    primary_counts = {name: counts.get(name, 0) for name in sorted(SUPPORTED_OBJECT_TYPES) if counts.get(name, 0)}
    return {
        "object_count": len(stage),
        "classes": dict(sorted(counts.items())),
        "primary_classes": primary_counts,
        "reference_count": reference_count,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "section_count": len(sections),
        "drawing_count": len(drawings),
        "nodes": nodes[:sample_limit],
        "edges": edges[:sample_limit],
        "sections": sections[:sample_limit],
        "drawings": drawings[:sample_limit],
    }


def validate_document(document: PrgDocument, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(document.metadata, dict) or not document.metadata.get("version"):
        errors.append("metadata.version is required")
    if not isinstance(document.tags, list):
        errors.append("tags.msgpack must decode to a list")
    if not isinstance(document.references, dict):
        errors.append("reference.msgpack must decode to a dict")
    if not isinstance(document.stage, list):
        errors.append("stage.msgpack must decode to a list")
        return {"ok": False, "errors": errors, "warnings": warnings}

    path_map = collect_paths(document.stage)
    attachment_names = set(document.attachments.keys())

    for path, item in walk_serialized(document.stage):
        if not isinstance(item, dict):
            continue
        if "$" in item:
            ref_path = item["$"]
            try:
                get_by_path(document.stage, ref_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Broken reference at {path}: {ref_path} ({exc})")
            continue
        if "_" not in item:
            continue
        class_name = item["_"]
        if class_name in SUPPORTED_OBJECT_TYPES:
            _validate_object(path, item, attachment_names, errors, warnings)
        elif class_name in {"CollisionBox", "Rectangle", "Vector", "Color", "PenStrokeSegment"}:
            continue

    if expected:
        _validate_expected(document.stage, expected, path_map, errors)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def find_overlaps(
    document: PrgDocument,
    *,
    include_sections: bool = True,
    include_points: bool = False,
    min_overlap_area: float = 1.0,
    ignore_containment: bool = False,
) -> dict[str, Any]:
    rects = extract_rect_objects(
        document.stage,
        include_sections=include_sections,
        include_points=include_points,
    )
    overlaps: list[dict[str, Any]] = []
    for index, first in enumerate(rects):
        for second in rects[index + 1 :]:
            overlap = intersect_rect(first["rect"], second["rect"])
            if overlap is None:
                continue
            if overlap.area < min_overlap_area:
                continue
            if ignore_containment and (_contains(first["rect"], second["rect"]) or _contains(second["rect"], first["rect"])):
                continue
            overlaps.append(
                {
                    "first": _rect_report(first),
                    "second": _rect_report(second),
                    "overlap_rect": {
                        "x": _rounded(overlap.x),
                        "y": _rounded(overlap.y),
                        "width": _rounded(overlap.width),
                        "height": _rounded(overlap.height),
                    },
                    "overlap_area": _rounded(overlap.area),
                }
            )
    return {
        "ok": not overlaps,
        "checked_count": len(rects),
        "overlap_count": len(overlaps),
        "overlaps": overlaps,
    }


def find_spacing_violations(
    document: PrgDocument,
    *,
    include_sections: bool = True,
    include_points: bool = False,
    min_gap: float = 0.0,
    ignore_containment: bool = False,
) -> dict[str, Any]:
    rects = extract_rect_objects(
        document.stage,
        include_sections=include_sections,
        include_points=include_points,
    )
    violations: list[dict[str, Any]] = []
    for index, first in enumerate(rects):
        for second in rects[index + 1 :]:
            if ignore_containment and (_contains(first["rect"], second["rect"]) or _contains(second["rect"], first["rect"])):
                continue
            gap_x = max(0.0, max(first["rect"].left, second["rect"].left) - min(first["rect"].right, second["rect"].right))
            gap_y = max(0.0, max(first["rect"].top, second["rect"].top) - min(first["rect"].bottom, second["rect"].bottom))
            if intersect_rect(first["rect"], second["rect"]) is not None:
                actual_gap = 0.0
            elif gap_x == 0.0:
                actual_gap = gap_y
            elif gap_y == 0.0:
                actual_gap = gap_x
            else:
                actual_gap = (gap_x**2 + gap_y**2) ** 0.5
            if actual_gap >= min_gap:
                continue
            violations.append(
                {
                    "first": _rect_report(first),
                    "second": _rect_report(second),
                    "actual_gap": _rounded(actual_gap),
                    "required_gap": _rounded(min_gap),
                }
            )
    return {
        "ok": not violations,
        "checked_count": len(rects),
        "violation_count": len(violations),
        "violations": violations,
    }


def auto_fix_layout(
    document: PrgDocument,
    *,
    include_sections: bool = False,
    include_points: bool = False,
    min_overlap_area: float = 1.0,
    padding: float = 24.0,
    max_iterations: int = 50,
) -> dict[str, Any]:
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        overlaps = find_overlaps(
            document,
            include_sections=include_sections,
            include_points=include_points,
            min_overlap_area=min_overlap_area,
            ignore_containment=False,
        )
        if overlaps["ok"]:
            return {
                "ok": True,
                "iterations": iterations,
                "final_overlap_count": 0,
                "overlaps": [],
            }
        iterations = iteration
        pending_shifts: dict[str, tuple[float, float]] = {}
        for overlap in overlaps["overlaps"]:
            first_rect = RectBounds(**overlap["first"]["rect"])
            second_rect = RectBounds(**overlap["second"]["rect"])
            dx, dy = resolve_overlap_shift(first_rect, second_rect, padding=padding)
            path = overlap["second"]["path"]
            current_dx, current_dy = pending_shifts.get(path, (0.0, 0.0))
            pending_shifts[path] = (current_dx + dx, current_dy + dy)
        if not pending_shifts:
            break
        for path, (dx, dy) in pending_shifts.items():
            move_object_at_path(document.stage, path, dx, dy)

    final_overlaps = find_overlaps(
        document,
        include_sections=include_sections,
        include_points=include_points,
        min_overlap_area=min_overlap_area,
        ignore_containment=False,
    )
    return {
        "ok": final_overlaps["ok"],
        "iterations": iterations,
        "final_overlap_count": final_overlaps["overlap_count"],
        "overlaps": final_overlaps["overlaps"],
    }


def validate_operation_block_links(document: PrgDocument) -> dict[str, Any]:
    graph = build_directed_graph(document.stage)
    operation_nodes = {
        path: info
        for path, info in graph["nodes"].items()
        if is_operation_block_label(info["label"])
    }

    invalid_links: list[dict[str, Any]] = []
    valid_links: list[dict[str, Any]] = []

    for source_path, source in operation_nodes.items():
        for target_path, target in operation_nodes.items():
            if source_path == target_path:
                continue
            record = {
                "source": {"path": source_path, "label": source["label"], "uuid": source["uuid"]},
                "target": {"path": target_path, "label": target["label"], "uuid": target["uuid"]},
            }

            direct = target_path in graph["adjacency"].get(source_path, [])
            if direct:
                record["distance"] = 1
                record["reason"] = "Direct operation-to-operation edge is not allowed"
                invalid_links.append(record)
                continue

            intermediates = [
                intermediate_path
                for intermediate_path in graph["adjacency"].get(source_path, [])
                if target_path in graph["adjacency"].get(intermediate_path, [])
            ]
            if not intermediates:
                continue

            blank_intermediates = [
                intermediate_path
                for intermediate_path in intermediates
                if is_blank_register_label(graph["nodes"].get(intermediate_path, {}).get("label", ""))
            ]

            record["distance"] = 2
            record["intermediates"] = [
                {
                    "path": intermediate_path,
                    "label": graph["nodes"].get(intermediate_path, {}).get("label", ""),
                    "uuid": graph["nodes"].get(intermediate_path, {}).get("uuid"),
                }
                for intermediate_path in intermediates
            ]
            if len(intermediates) == 1 and len(blank_intermediates) == 1:
                valid_links.append(record)
            elif len(blank_intermediates) == 0:
                record["reason"] = "Operation blocks must be separated by exactly one blank register node"
                invalid_links.append(record)
            else:
                record["reason"] = "Operation blocks must have exactly one intermediate blank register node"
                invalid_links.append(record)

    return {
        "ok": not invalid_links,
        "operation_block_count": len(operation_nodes),
        "invalid_link_count": len(invalid_links),
        "valid_link_count": len(valid_links),
        "invalid_links": invalid_links,
        "valid_links": valid_links,
    }


def auto_fix_operation_block_links(
    document: PrgDocument,
    *,
    intermediate_label: str = "",
    intermediate_width: float = 100.0,
    intermediate_height: float = 76.0,
    vertical_offset: float = 140.0,
) -> dict[str, Any]:
    fixes: list[dict[str, Any]] = []
    stage = document.stage
    validation = validate_operation_block_links(document)
    for invalid in validation["invalid_links"]:
        source_path = invalid["source"]["path"]
        target_path = invalid["target"]["path"]
        source_obj = get_by_path(stage, source_path)
        target_obj = get_by_path(stage, target_path)
        if not (isinstance(source_obj, dict) and isinstance(target_obj, dict)):
            continue

        intermediates = invalid.get("intermediates", [])
        if invalid.get("distance") == 2 and len(intermediates) == 1:
            intermediate_path = intermediates[0]["path"]
            intermediate_obj = get_by_path(stage, intermediate_path)
            if isinstance(intermediate_obj, dict) and intermediate_obj.get("_") == "TextNode":
                intermediate_obj["text"] = intermediate_label
                fixes.append(
                    {
                        "type": "blank_existing_register",
                        "source": invalid["source"],
                        "target": invalid["target"],
                        "updated_node": {
                            "path": intermediate_path,
                            "uuid": intermediate_obj.get("uuid"),
                            "label": intermediate_label,
                        },
                    }
                )
                continue

        path_map = collect_paths(stage)
        for index, item in enumerate(list(stage)):
            if not isinstance(item, dict) or item.get("_") != "LineEdge":
                continue
            endpoints = item.get("associationList", [])
            if len(endpoints) != 2:
                continue
            edge_source_path = _endpoint_path(endpoints[0], path_map["/"])
            edge_target_path = _endpoint_path(endpoints[1], path_map["/"])
            if edge_source_path != source_path or edge_target_path != target_path:
                continue

            source_rect = get_primary_rectangle(source_obj.get("collisionBox"))
            target_rect = get_primary_rectangle(target_obj.get("collisionBox"))
            if source_rect is None or target_rect is None:
                break

            mid_x = min(source_rect.x, target_rect.x) + abs((target_rect.x + target_rect.width / 2) - (source_rect.x + source_rect.width / 2)) / 2 - intermediate_width / 2
            mid_y = max(source_rect.y, target_rect.y) + vertical_offset
            new_uuid = str(uuid.uuid4())
            new_node = {
                "_": "TextNode",
                "details": [],
                "uuid": new_uuid,
                "text": intermediate_label,
                "collisionBox": collision_box(mid_x, mid_y, intermediate_width, intermediate_height),
                "color": color(),
                "fontScaleLevel": 0,
                "sizeAdjust": "auto",
            }
            new_node_index = len(stage)
            stage.append(new_node)

            original_text = item.get("text", "")
            item["associationList"] = [{"$": source_path}, {"$": f"/{new_node_index}"}]
            item["targetRectangleRate"] = vector(0.5, 0.5)
            item["sourceRectangleRate"] = vector(0.5, 0.5)
            item["text"] = original_text

            new_edge = {
                "_": "LineEdge",
                "associationList": [{"$": f"/{new_node_index}"}, {"$": target_path}],
                "color": color(),
                "targetRectangleRate": vector(0.5, 0.5),
                "sourceRectangleRate": vector(0.5, 0.5),
                "uuid": str(uuid.uuid4()),
                "text": "",
                "lineType": "solid",
            }
            stage.append(new_edge)
            fixes.append(
                {
                    "type": "insert_blank_register",
                    "edge_index": index,
                    "source": {"path": source_path, "label": _label_for_object(source_obj), "uuid": source_obj.get("uuid")},
                    "target": {"path": target_path, "label": _label_for_object(target_obj), "uuid": target_obj.get("uuid")},
                    "inserted_node": {"path": f"/{new_node_index}", "label": intermediate_label, "uuid": new_uuid},
                }
            )
            break

    result = validate_operation_block_links(document)
    return {
        "ok": result["ok"],
        "fix_count": len(fixes),
        "fixes": fixes,
        "validation": result,
    }


def edit_document(document: PrgDocument, patch: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    operations = patch if isinstance(patch, list) else patch.get("operations", [])
    if not isinstance(operations, list) or not operations:
        raise ValueError("Edit patch must contain a non-empty operations list")

    applied: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError(f"Operation {index} must be an object")
        op_type = operation.get("op")
        if op_type == "update":
            applied.append(_apply_update_operation(document, operation))
        elif op_type == "append_details":
            applied.append(_apply_append_details_operation(document, operation))
        elif op_type == "move":
            applied.append(_apply_move_operation(document, operation))
        elif op_type == "resize":
            applied.append(_apply_resize_operation(document, operation))
        elif op_type == "add_text_node":
            applied.append(_apply_add_text_node_operation(document, operation))
        elif op_type == "add_url_node":
            applied.append(_apply_add_url_node_operation(document, operation))
        elif op_type == "add_section":
            applied.append(_apply_add_section_operation(document, operation))
        elif op_type == "add_edge":
            applied.append(_apply_add_edge_operation(document, operation))
        elif op_type == "insert_node_between":
            applied.append(_apply_insert_node_between_operation(document, operation))
        elif op_type == "add_to_section":
            applied.append(_apply_add_to_section_operation(document, operation))
        elif op_type == "remove_from_section":
            applied.append(_apply_remove_from_section_operation(document, operation))
        elif op_type == "delete":
            applied.append(_apply_delete_operation(document, operation))
        else:
            raise ValueError(f"Unsupported edit operation: {op_type}")

    validation = validate_document(document)
    return {
        "ok": validation["ok"],
        "operation_count": len(operations),
        "applied_count": len(applied),
        "operations": applied,
        "validation": validation,
    }


def collect_paths(obj: Any, path: str = "") -> dict[str, Any]:
    mapping = {path or "/": obj}
    if isinstance(obj, list):
        for index, item in enumerate(obj):
            mapping.update(collect_paths(item, f"{path}/{index}"))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            mapping.update(collect_paths(value, f"{path}/{key}"))
    return mapping


def extract_rect_objects(
    stage: list[Any],
    *,
    include_sections: bool = True,
    include_points: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path, item in walk_serialized(stage):
        if not isinstance(item, dict):
            continue
        class_name = item.get("_")
        if class_name in {"TextNode", "UrlNode", "ImageNode", "SvgNode"}:
            rect = get_primary_rectangle(item.get("collisionBox"))
            if rect:
                results.append({"path": path, "type": class_name, "uuid": item.get("uuid"), "label": _label_for_object(item), "rect": rect})
        elif class_name == "Section" and include_sections:
            rect = section_bounds(item)
            if rect:
                results.append({"path": path, "type": class_name, "uuid": item.get("uuid"), "label": _label_for_object(item), "rect": rect})
        elif class_name == "ConnectPoint" and include_points:
            rect = get_primary_rectangle(item.get("collisionBox"))
            if rect:
                results.append({"path": path, "type": class_name, "uuid": item.get("uuid"), "label": _label_for_object(item), "rect": rect})
    return results


def build_directed_graph(stage: list[Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    adjacency: dict[str, list[str]] = {}
    path_map = collect_paths(stage)
    for path, item in walk_serialized(stage):
        if not isinstance(item, dict) or "_" not in item:
            continue
        class_name = item["_"]
        if class_name in NODE_TYPES | CONTAINER_TYPES:
            nodes[path] = {
                "type": class_name,
                "uuid": item.get("uuid"),
                "label": _label_for_object(item),
            }
            adjacency.setdefault(path, [])
    for _, item in walk_serialized(stage):
        if not isinstance(item, dict):
            continue
        class_name = item.get("_")
        if class_name == "LineEdge":
            endpoints = item.get("associationList", [])
            if len(endpoints) != 2:
                continue
            source_path = _endpoint_path(endpoints[0], path_map["/"])
            target_path = _endpoint_path(endpoints[1], path_map["/"])
            if source_path and target_path:
                adjacency.setdefault(source_path, []).append(target_path)
        elif class_name == "MultiTargetUndirectedEdge":
            endpoint_paths = []
            for endpoint in item.get("associationList", []):
                endpoint_path = _endpoint_path(endpoint, path_map["/"])
                if endpoint_path:
                    endpoint_paths.append(endpoint_path)
            for source_path in endpoint_paths:
                for target_path in endpoint_paths:
                    if source_path != target_path:
                        adjacency.setdefault(source_path, []).append(target_path)
    return {"nodes": nodes, "adjacency": adjacency}


def shortest_paths_from(source: str, adjacency: dict[str, list[str]]) -> dict[str, int]:
    distances = {source: 0}
    queue = [source]
    while queue:
        current = queue.pop(0)
        next_distance = distances[current] + 1
        for neighbor in adjacency.get(current, []):
            if neighbor in distances:
                continue
            distances[neighbor] = next_distance
            queue.append(neighbor)
    return distances


def get_primary_rectangle(collision_box_obj: Any) -> RectBounds | None:
    if not isinstance(collision_box_obj, dict):
        return None
    shapes = collision_box_obj.get("shapes")
    if not isinstance(shapes, list):
        return None
    for shape in shapes:
        if isinstance(shape, dict) and shape.get("_") == "Rectangle":
            location = shape.get("location", {})
            size = shape.get("size", {})
            return RectBounds(
                float(location.get("x", 0)),
                float(location.get("y", 0)),
                float(size.get("x", 0)),
                float(size.get("y", 0)),
            )
    return None


def section_bounds(section_obj: dict[str, Any]) -> RectBounds | None:
    child_rects: list[RectBounds] = []
    for child in section_obj.get("children", []):
        if isinstance(child, dict) and "$" in child:
            continue
        if not isinstance(child, dict):
            continue
        rect = get_primary_rectangle(child.get("collisionBox"))
        if rect:
            child_rects.append(rect)
    if not child_rects:
        return None
    left = min(rect.left for rect in child_rects)
    right = max(rect.right for rect in child_rects)
    top = min(rect.top for rect in child_rects)
    bottom = max(rect.bottom for rect in child_rects)
    padding = 24
    return RectBounds(left - padding, top - padding, (right - left) + padding * 2, (bottom - top) + padding * 2)


def intersect_rect(first: RectBounds, second: RectBounds) -> RectBounds | None:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)
    if right <= left or bottom <= top:
        return None
    return RectBounds(left, top, right - left, bottom - top)


def walk_serialized(obj: Any, path: str = ""):
    yield path or "/", obj
    if isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from walk_serialized(item, f"{path}/{index}")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from walk_serialized(value, f"{path}/{key}")


def get_by_path(obj: Any, path: str) -> Any:
    result = obj
    for segment in [part for part in path.split("/") if part]:
        if isinstance(result, list):
            result = result[int(segment)]
        elif isinstance(result, dict):
            result = result[segment]
        else:
            raise KeyError(path)
    return result


def is_operation_block_label(label: str) -> bool:
    return bool(OPERATION_BLOCK_PATTERN.fullmatch(label.strip()))


def is_blank_register_label(label: str) -> bool:
    return label.strip() == ""


def move_object_at_path(stage: list[Any], path: str, dx: float, dy: float) -> None:
    obj = get_by_path(stage, path)
    translate_object(obj, dx, dy)


def translate_object(obj: Any, dx: float, dy: float) -> None:
    if not isinstance(obj, dict):
        return
    collision_box_obj = obj.get("collisionBox")
    if isinstance(collision_box_obj, dict):
        translate_collision_box(collision_box_obj, dx, dy)
    if obj.get("_") == "PenStroke":
        for segment in obj.get("segments", []):
            location = segment.get("location", {})
            if isinstance(location, dict):
                location["x"] = _rounded(float(location.get("x", 0)) + dx)
                location["y"] = _rounded(float(location.get("y", 0)) + dy)


def translate_collision_box(collision_box_obj: dict[str, Any], dx: float, dy: float) -> None:
    for shape in collision_box_obj.get("shapes", []):
        if not isinstance(shape, dict):
            continue
        if shape.get("_") == "Rectangle":
            location = shape.get("location", {})
            if isinstance(location, dict):
                location["x"] = _rounded(float(location.get("x", 0)) + dx)
                location["y"] = _rounded(float(location.get("y", 0)) + dy)


def resolve_overlap_shift(first: RectBounds, second: RectBounds, *, padding: float) -> tuple[float, float]:
    overlap = intersect_rect(first, second)
    if overlap is None:
        return (0.0, 0.0)
    first_center_x = first.x + first.width / 2
    second_center_x = second.x + second.width / 2
    first_center_y = first.y + first.height / 2
    second_center_y = second.y + second.height / 2

    horizontal_shift = overlap.width + padding
    vertical_shift = overlap.height + padding

    if overlap.width <= overlap.height:
        direction = 1 if second_center_x >= first_center_x else -1
        return (horizontal_shift * direction, 0.0)
    direction = 1 if second_center_y >= first_center_y else -1
    return (0.0, vertical_shift * direction)


def _build_object(item: dict[str, Any], id_to_index: dict[str, int]) -> dict[str, Any]:
    object_type = item.get("type")
    if object_type not in SUPPORTED_OBJECT_TYPES:
        raise ValueError(f"Unsupported object type: {object_type}")
    object_uuid = item.get("uuid") or str(uuid.uuid4())
    details = item.get("details", [])

    if object_type == "TextNode":
        x, y, width, height = _rect_from_item(item)
        return {
            "_": "TextNode",
            "details": details,
            "uuid": object_uuid,
            "text": item.get("text", ""),
            "collisionBox": collision_box(x, y, width, height),
            "color": color(item.get("color")),
            "fontScaleLevel": int(item.get("fontScaleLevel", 0)),
            "sizeAdjust": item.get("sizeAdjust", "auto"),
        }
    if object_type == "UrlNode":
        x, y, width, height = _rect_from_item(item)
        return {
            "_": "UrlNode",
            "details": details,
            "uuid": object_uuid,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "color": color(item.get("color")),
            "collisionBox": collision_box(x, y, width, height),
        }
    if object_type == "ImageNode":
        x, y, width, height = _rect_from_item(item)
        return {
            "_": "ImageNode",
            "details": details,
            "uuid": object_uuid,
            "collisionBox": collision_box(x, y, width, height),
            "attachmentId": item["attachmentId"],
            "scale": item.get("scale", 1),
            "isBackground": bool(item.get("isBackground", False)),
        }
    if object_type == "SvgNode":
        x, y, width, height = _rect_from_item(item)
        return {
            "_": "SvgNode",
            "details": details,
            "color": color(item.get("color")),
            "uuid": object_uuid,
            "scale": item.get("scale", 1),
            "collisionBox": collision_box(x, y, width, height),
            "attachmentId": item["attachmentId"],
        }
    if object_type == "ConnectPoint":
        x, y, width, height = _rect_from_item(item, default_width=30, default_height=30)
        return {
            "_": "ConnectPoint",
            "details": details,
            "collisionBox": collision_box(x, y, width, height),
            "uuid": object_uuid,
        }
    if object_type == "Section":
        return {
            "_": "Section",
            "details": details,
            "uuid": object_uuid,
            "color": color(item.get("color")),
            "text": item.get("text", ""),
            "children": [{"$": f"/{id_to_index[child_id]}"} for child_id in item.get("children", [])],
            "isCollapsed": bool(item.get("isCollapsed", False)),
            "locked": bool(item.get("locked", False)),
        }
    if object_type == "PenStroke":
        segments = item.get("segments", [])
        if len(segments) < 2:
            raise ValueError("PenStroke requires at least 2 segments")
        return {
            "_": "PenStroke",
            "details": details,
            "uuid": object_uuid,
            "segments": [
                {
                    "_": "PenStrokeSegment",
                    "location": vector(float(segment["x"]), float(segment["y"])),
                    "pressure": segment.get("pressure", 1),
                }
                for segment in segments
            ],
            "color": color(item.get("color")),
        }
    if object_type == "LineEdge":
        endpoints = item.get("endpoints") or [item.get("from"), item.get("to")]
        if len(endpoints) != 2:
            raise ValueError(f"LineEdge requires exactly 2 endpoints: {item}")
        return {
            "_": "LineEdge",
            "associationList": [{"$": f"/{id_to_index[endpoint_id]}"} for endpoint_id in endpoints],
            "color": color(item.get("color")),
            "targetRectangleRate": _vector_like(item.get("targetRate"), 0.5, 0.5),
            "sourceRectangleRate": _vector_like(item.get("sourceRate"), 0.5, 0.5),
            "uuid": object_uuid,
            "text": item.get("text", ""),
            "lineType": item.get("lineType", "solid"),
        }
    if object_type == "MultiTargetUndirectedEdge":
        endpoints = item.get("endpoints", [])
        if len(endpoints) < 2:
            raise ValueError(f"MultiTargetUndirectedEdge requires at least 2 endpoints: {item}")
        rect_rates = item.get("rectRates") or [[0.5, 0.5] for _ in endpoints]
        if len(rect_rates) != len(endpoints):
            raise ValueError("rectRates length must match endpoints length")
        return {
            "_": "MultiTargetUndirectedEdge",
            "associationList": [{"$": f"/{id_to_index[endpoint_id]}"} for endpoint_id in endpoints],
            "color": color(item.get("color")),
            "uuid": object_uuid,
            "text": item.get("text", ""),
            "rectRates": [_vector_like(rate, 0.5, 0.5) for rate in rect_rates],
            "centerRate": _vector_like(item.get("centerRate"), 0.5, 0.5),
            "arrow": item.get("arrow", "none"),
            "renderType": item.get("renderType", "line"),
            "padding": item.get("padding", 10),
        }
    raise AssertionError(object_type)


def _endpoint_summary(path_map: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    if isinstance(ref, dict) and "$" in ref:
        target = get_by_path(path_map["/"], ref["$"])
        ref_path = ref["$"]
    else:
        target = ref
        ref_path = None
    return {
        "ref": ref_path,
        "uuid": target.get("uuid") if isinstance(target, dict) else None,
        "type": target.get("_") if isinstance(target, dict) else type(target).__name__,
        "label": _label_for_object(target) if isinstance(target, dict) else str(target),
    }


def _endpoint_path(ref: dict[str, Any], stage: list[Any]) -> str | None:
    if isinstance(ref, dict) and "$" in ref:
        return ref["$"]
    if isinstance(ref, dict):
        for path, item in walk_serialized(stage):
            if item is ref:
                return path
    return None


def _contains(first: RectBounds, second: RectBounds) -> bool:
    return first.left <= second.left and first.right >= second.right and first.top <= second.top and first.bottom >= second.bottom


def _rect_report(item: dict[str, Any]) -> dict[str, Any]:
    rect: RectBounds = item["rect"]
    return {
        "path": item["path"],
        "type": item["type"],
        "uuid": item["uuid"],
        "label": item["label"],
        "rect": {
            "x": _rounded(rect.x),
            "y": _rounded(rect.y),
            "width": _rounded(rect.width),
            "height": _rounded(rect.height),
        },
    }


def _label_for_object(item: dict[str, Any]) -> str:
    if item.get("_") == "TextNode":
        return item.get("text", "")
    if item.get("_") == "UrlNode":
        return item.get("title", "")
    if item.get("_") == "Section":
        return item.get("text", "")
    return item.get("text", "") or item.get("title", "") or ""


def _apply_update_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    targets = _resolve_targets(document.stage, operation.get("target"), mode=operation.get("mode", "one"))
    updates = operation.get("set")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("update operation requires a non-empty set object")

    results = []
    for target in targets:
        obj = target["object"]
        before_label = _label_for_object(obj)
        _update_object_fields(obj, updates)
        results.append(
            {
                "path": target["path"],
                "type": obj.get("_"),
                "uuid": obj.get("uuid"),
                "before_label": before_label,
                "after_label": _label_for_object(obj),
            }
        )
    return {"op": "update", "match_count": len(results), "targets": results}


def _apply_append_details_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    targets = _resolve_targets(document.stage, operation.get("target"), mode=operation.get("mode", "one"))
    value = operation.get("value", "")
    blocks = _details_value_to_blocks(value)
    results = []
    for target in targets:
        obj = target["object"]
        details = obj.setdefault("details", [])
        if not isinstance(details, list):
            raise ValueError(f"{target['path']} does not have a list-valued details field")
        details.extend(blocks)
        results.append({"path": target["path"], "uuid": obj.get("uuid"), "details_count": len(details)})
    return {"op": "append_details", "match_count": len(results), "targets": results}


def _apply_move_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    targets = _resolve_targets(document.stage, operation.get("target"), mode=operation.get("mode", "one"))
    dx = operation.get("dx")
    dy = operation.get("dy")
    x = operation.get("x")
    y = operation.get("y")
    results = []
    for target in targets:
        rect = _require_primary_rectangle(target["object"], target["path"])
        if x is not None or y is not None:
            delta_x = float(x if x is not None else rect.x) - rect.x
            delta_y = float(y if y is not None else rect.y) - rect.y
        else:
            delta_x = float(dx or 0)
            delta_y = float(dy or 0)
        translate_object(target["object"], delta_x, delta_y)
        moved = _require_primary_rectangle(target["object"], target["path"])
        results.append(
            {
                "path": target["path"],
                "uuid": target["object"].get("uuid"),
                "rect": {"x": _rounded(moved.x), "y": _rounded(moved.y), "width": _rounded(moved.width), "height": _rounded(moved.height)},
            }
        )
    return {"op": "move", "match_count": len(results), "targets": results}


def _apply_resize_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    targets = _resolve_targets(document.stage, operation.get("target"), mode=operation.get("mode", "one"))
    width = operation.get("width")
    height = operation.get("height")
    if width is None and height is None:
        raise ValueError("resize operation requires width and/or height")
    results = []
    for target in targets:
        rect_shape = _require_primary_rectangle_shape(target["object"], target["path"])
        size = rect_shape["size"]
        if width is not None:
            size["x"] = _rounded(float(width))
        if height is not None:
            size["y"] = _rounded(float(height))
        rect = _require_primary_rectangle(target["object"], target["path"])
        results.append(
            {
                "path": target["path"],
                "uuid": target["object"].get("uuid"),
                "rect": {"x": _rounded(rect.x), "y": _rounded(rect.y), "width": _rounded(rect.width), "height": _rounded(rect.height)},
            }
        )
    return {"op": "resize", "match_count": len(results), "targets": results}


def _apply_add_text_node_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    item = {
        "type": "TextNode",
        "text": operation.get("text", ""),
        "details": operation.get("details", []),
        "x": float(operation.get("x", 0)),
        "y": float(operation.get("y", 0)),
        "width": float(operation.get("width", 200)),
        "height": float(operation.get("height", 76)),
        "color": operation.get("color"),
        "fontScaleLevel": int(operation.get("fontScaleLevel", 0)),
        "sizeAdjust": operation.get("sizeAdjust", "auto"),
        "uuid": operation.get("uuid") or str(uuid.uuid4()),
    }
    new_object = _build_object(item, {})
    document.stage.append(new_object)
    return {
        "op": "add_text_node",
        "path": f"/{len(document.stage) - 1}",
        "uuid": new_object.get("uuid"),
        "label": new_object.get("text", ""),
    }


def _apply_add_url_node_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    item = {
        "type": "UrlNode",
        "title": operation.get("title", ""),
        "url": operation.get("url", ""),
        "details": operation.get("details", []),
        "x": float(operation.get("x", 0)),
        "y": float(operation.get("y", 0)),
        "width": float(operation.get("width", 240)),
        "height": float(operation.get("height", 90)),
        "color": operation.get("color"),
        "uuid": operation.get("uuid") or str(uuid.uuid4()),
    }
    new_object = _build_object(item, {})
    document.stage.append(new_object)
    return {
        "op": "add_url_node",
        "path": f"/{len(document.stage) - 1}",
        "uuid": new_object.get("uuid"),
        "label": new_object.get("title", ""),
    }


def _apply_add_section_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    children_selectors = operation.get("children", [])
    child_paths = []
    for selector in children_selectors:
        child_paths.extend(target["path"] for target in _resolve_targets(document.stage, selector, mode="all"))
    child_paths = _unique_paths(child_paths)
    section = {
        "_": "Section",
        "details": _details_value_to_blocks(operation.get("details", [])),
        "uuid": operation.get("uuid") or str(uuid.uuid4()),
        "color": color(operation.get("color")),
        "text": operation.get("text", ""),
        "children": [{"$": path} for path in child_paths],
        "isCollapsed": bool(operation.get("isCollapsed", False)),
        "locked": bool(operation.get("locked", False)),
    }
    document.stage.append(section)
    return {
        "op": "add_section",
        "path": f"/{len(document.stage) - 1}",
        "uuid": section.get("uuid"),
        "label": section.get("text", ""),
        "child_count": len(child_paths),
    }


def _apply_add_edge_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    path_map = collect_paths(document.stage)
    edge_type = operation.get("edgeType", "LineEdge")
    if edge_type == "LineEdge":
        source = _resolve_targets(document.stage, operation.get("from"), mode="one")[0]
        target = _resolve_targets(document.stage, operation.get("to"), mode="one")[0]
        edge = {
            "_": "LineEdge",
            "associationList": [{"$": source["path"]}, {"$": target["path"]}],
            "color": color(operation.get("color")),
            "targetRectangleRate": _vector_like(operation.get("targetRate"), 0.5, 0.5),
            "sourceRectangleRate": _vector_like(operation.get("sourceRate"), 0.5, 0.5),
            "uuid": operation.get("uuid") or str(uuid.uuid4()),
            "text": operation.get("text", ""),
            "lineType": operation.get("lineType", "solid"),
        }
        document.stage.append(edge)
        return {
            "op": "add_edge",
            "path": f"/{len(document.stage) - 1}",
            "uuid": edge["uuid"],
            "source": source["path"],
            "target": target["path"],
        }
    if edge_type == "MultiTargetUndirectedEdge":
        endpoint_selectors = operation.get("endpoints", [])
        if len(endpoint_selectors) < 2:
            raise ValueError("MultiTargetUndirectedEdge requires at least 2 endpoints")
        endpoint_paths = [_resolve_targets(document.stage, selector, mode="one")[0]["path"] for selector in endpoint_selectors]
        rect_rates = operation.get("rectRates") or [[0.5, 0.5] for _ in endpoint_paths]
        if len(rect_rates) != len(endpoint_paths):
            raise ValueError("rectRates length must match endpoints length")
        edge = {
            "_": "MultiTargetUndirectedEdge",
            "associationList": [{"$": path} for path in endpoint_paths],
            "color": color(operation.get("color")),
            "uuid": operation.get("uuid") or str(uuid.uuid4()),
            "text": operation.get("text", ""),
            "rectRates": [_vector_like(rate, 0.5, 0.5) for rate in rect_rates],
            "centerRate": _vector_like(operation.get("centerRate"), 0.5, 0.5),
            "arrow": operation.get("arrow", "none"),
            "renderType": operation.get("renderType", "line"),
            "padding": operation.get("padding", 10),
        }
        document.stage.append(edge)
        return {
            "op": "add_edge",
            "path": f"/{len(document.stage) - 1}",
            "uuid": edge["uuid"],
            "endpoint_count": len(endpoint_paths),
        }
    raise ValueError(f"Unsupported edgeType: {edge_type}")


def _apply_insert_node_between_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    edge_target = _resolve_edge_for_insert(document.stage, operation)
    edge_obj = edge_target["object"]
    source_path, target_path = _line_edge_endpoints(edge_obj)
    source_obj = get_by_path(document.stage, source_path)
    target_obj = get_by_path(document.stage, target_path)
    source_rect = _require_primary_rectangle(source_obj, source_path)
    target_rect = _require_primary_rectangle(target_obj, target_path)

    node_spec = operation.get("node")
    if not isinstance(node_spec, dict):
        raise ValueError("insert_node_between requires a node object")
    node_type = node_spec.get("type", "TextNode")
    if node_type != "TextNode":
        raise ValueError("insert_node_between currently supports only TextNode inserts")

    width = float(node_spec.get("width", 120))
    height = float(node_spec.get("height", 76))
    x = float(
        node_spec.get(
            "x",
            ((source_rect.x + source_rect.width / 2) + (target_rect.x + target_rect.width / 2)) / 2 - width / 2,
        )
    )
    y = float(
        node_spec.get(
            "y",
            ((source_rect.y + source_rect.height / 2) + (target_rect.y + target_rect.height / 2)) / 2 - height / 2,
        )
    )
    new_node = _build_object(
        {
            "type": "TextNode",
            "text": node_spec.get("text", ""),
            "details": node_spec.get("details", []),
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "color": node_spec.get("color"),
            "fontScaleLevel": int(node_spec.get("fontScaleLevel", 0)),
            "sizeAdjust": node_spec.get("sizeAdjust", "auto"),
            "uuid": node_spec.get("uuid") or str(uuid.uuid4()),
        },
        {},
    )
    document.stage.append(new_node)
    new_node_path = f"/{len(document.stage) - 1}"

    original_text = edge_obj.get("text", "")
    edge_obj["associationList"] = [{"$": source_path}, {"$": new_node_path}]
    if operation.get("preserveEdgeText", True):
        edge_obj["text"] = original_text
    else:
        edge_obj["text"] = ""

    new_edge = {
        "_": "LineEdge",
        "associationList": [{"$": new_node_path}, {"$": target_path}],
        "color": color(operation.get("edgeColor")),
        "targetRectangleRate": _vector_like(operation.get("targetRate"), 0.5, 0.5),
        "sourceRectangleRate": _vector_like(operation.get("sourceRate"), 0.5, 0.5),
        "uuid": str(uuid.uuid4()),
        "text": operation.get("newEdgeText", ""),
        "lineType": operation.get("lineType", edge_obj.get("lineType", "solid")),
    }
    document.stage.append(new_edge)
    return {
        "op": "insert_node_between",
        "edge_path": edge_target["path"],
        "inserted_node_path": new_node_path,
        "inserted_node_uuid": new_node.get("uuid"),
        "new_edge_path": f"/{len(document.stage) - 1}",
    }


def _apply_add_to_section_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    section = _resolve_targets(document.stage, operation.get("section"), mode="one")[0]
    section_obj = section["object"]
    if section_obj.get("_") != "Section":
        raise ValueError("section selector must resolve to a Section")
    targets = []
    for selector in operation.get("targets", []):
        targets.extend(_resolve_targets(document.stage, selector, mode="all"))
    unique_paths = _unique_paths(target["path"] for target in targets)
    existing = {child["$"] for child in section_obj.get("children", []) if isinstance(child, dict) and "$" in child}
    added_paths = []
    for path in unique_paths:
        if path in existing:
            continue
        section_obj.setdefault("children", []).append({"$": path})
        added_paths.append(path)
    return {"op": "add_to_section", "section_path": section["path"], "added_count": len(added_paths), "added_paths": added_paths}


def _apply_remove_from_section_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    section = _resolve_targets(document.stage, operation.get("section"), mode="one")[0]
    section_obj = section["object"]
    if section_obj.get("_") != "Section":
        raise ValueError("section selector must resolve to a Section")
    targets = []
    for selector in operation.get("targets", []):
        targets.extend(_resolve_targets(document.stage, selector, mode="all"))
    remove_paths = set(_unique_paths(target["path"] for target in targets))
    children = section_obj.get("children", [])
    kept = [child for child in children if not (isinstance(child, dict) and child.get("$") in remove_paths)]
    removed_count = len(children) - len(kept)
    section_obj["children"] = kept
    return {"op": "remove_from_section", "section_path": section["path"], "removed_count": removed_count}


def _apply_delete_operation(document: PrgDocument, operation: dict[str, Any]) -> dict[str, Any]:
    targets = _resolve_targets(document.stage, operation.get("target"), mode=operation.get("mode", "one"))
    delete_paths = {target["path"] for target in targets}
    cascade = bool(operation.get("cascade", True))
    summary = _delete_paths(document.stage, delete_paths, cascade=cascade)
    return {"op": "delete", **summary}


def _resolve_targets(stage: list[Any], selector: Any, *, mode: str = "one") -> list[dict[str, Any]]:
    if not isinstance(selector, dict):
        raise ValueError("selector must be an object")
    matches = _match_top_level_objects(stage, selector)
    if mode == "one":
        if len(matches) != 1:
            raise ValueError(f"selector expected exactly 1 match, got {len(matches)}: {selector}")
        return matches
    if mode == "all":
        if not matches:
            raise ValueError(f"selector matched no objects: {selector}")
        return matches
    raise ValueError(f"Unsupported selector mode: {mode}")


def _match_top_level_objects(stage: list[Any], selector: dict[str, Any]) -> list[dict[str, Any]]:
    path_map = collect_paths(stage)
    matches = []
    for index, obj in enumerate(stage):
        if not isinstance(obj, dict) or "_" not in obj:
            continue
        path = f"/{index}"
        if _selector_matches(path, obj, selector, path_map):
            matches.append({"path": path, "object": obj})
    return matches


def _selector_matches(path: str, obj: dict[str, Any], selector: dict[str, Any], path_map: dict[str, Any]) -> bool:
    if selector.get("path") and selector["path"] != path:
        return False
    if selector.get("uuid") and selector["uuid"] != obj.get("uuid"):
        return False
    if selector.get("type") and selector["type"] != obj.get("_"):
        return False
    label = _label_for_object(obj)
    text = obj.get("text", "")
    title = obj.get("title", "")
    if selector.get("text") is not None and selector["text"] != text:
        return False
    if selector.get("text_contains") is not None and selector["text_contains"] not in text:
        return False
    if selector.get("title") is not None and selector["title"] != title:
        return False
    if selector.get("title_contains") is not None and selector["title_contains"] not in title:
        return False
    if selector.get("label") is not None and selector["label"] != label:
        return False
    if selector.get("label_contains") is not None and selector["label_contains"] not in label:
        return False
    if obj.get("_") in EDGE_TYPES:
        edge_text = obj.get("text", "")
        if selector.get("edge_text") is not None and selector["edge_text"] != edge_text:
            return False
        if selector.get("edge_text_contains") is not None and selector["edge_text_contains"] not in edge_text:
            return False
        if selector.get("source_label") is not None or selector.get("target_label") is not None:
            if obj.get("_") != "LineEdge":
                return False
            source_path, target_path = _line_edge_endpoints(obj)
            source_obj = get_by_path(path_map["/"], source_path)
            target_obj = get_by_path(path_map["/"], target_path)
            if selector.get("source_label") is not None and _label_for_object(source_obj) != selector["source_label"]:
                return False
            if selector.get("target_label") is not None and _label_for_object(target_obj) != selector["target_label"]:
                return False
    return True


def _update_object_fields(obj: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if key == "text":
            obj["text"] = value
        elif key == "title":
            obj["title"] = value
        elif key == "url":
            obj["url"] = value
        elif key == "details":
            obj["details"] = _details_value_to_blocks(value)
        elif key == "color":
            obj["color"] = color(value)
        elif key == "fontScaleLevel":
            obj["fontScaleLevel"] = int(value)
        elif key == "sizeAdjust":
            obj["sizeAdjust"] = value
        elif key == "lineType":
            obj["lineType"] = value
        elif key == "locked":
            obj["locked"] = bool(value)
        elif key == "isCollapsed":
            obj["isCollapsed"] = bool(value)
        elif key == "scale":
            obj["scale"] = value
        elif key == "isBackground":
            obj["isBackground"] = bool(value)
        elif key in {"x", "y", "width", "height"}:
            rect_shape = _require_primary_rectangle_shape(obj, obj.get("uuid", "<unknown>"))
            if key == "x":
                rect_shape["location"]["x"] = _rounded(float(value))
            elif key == "y":
                rect_shape["location"]["y"] = _rounded(float(value))
            elif key == "width":
                rect_shape["size"]["x"] = _rounded(float(value))
            elif key == "height":
                rect_shape["size"]["y"] = _rounded(float(value))
        else:
            raise ValueError(f"Unsupported update field: {key}")


def _details_value_to_blocks(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Unsupported details value: {value!r}")
    if value == "":
        return []
    return [{"type": "p", "children": [{"text": line}]} for line in value.splitlines() or [value]]


def _require_primary_rectangle(obj: dict[str, Any], path: str) -> RectBounds:
    rect = get_primary_rectangle(obj.get("collisionBox"))
    if rect is None:
        raise ValueError(f"{path} does not have a primary rectangle")
    return rect


def _require_primary_rectangle_shape(obj: dict[str, Any], path: str) -> dict[str, Any]:
    collision_box_obj = obj.get("collisionBox")
    if not isinstance(collision_box_obj, dict):
        raise ValueError(f"{path} does not have a collisionBox")
    for shape in collision_box_obj.get("shapes", []):
        if isinstance(shape, dict) and shape.get("_") == "Rectangle":
            return shape
    raise ValueError(f"{path} does not contain a Rectangle shape")


def _unique_paths(paths: Any) -> list[str]:
    ordered = []
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def _resolve_edge_for_insert(stage: list[Any], operation: dict[str, Any]) -> dict[str, Any]:
    if operation.get("edge"):
        return _resolve_targets(stage, operation.get("edge"), mode="one")[0]
    source = _resolve_targets(stage, operation.get("from"), mode="one")[0]
    target = _resolve_targets(stage, operation.get("to"), mode="one")[0]
    candidates = _match_top_level_objects(
        stage,
        {
            "type": "LineEdge",
            "source_label": _label_for_object(source["object"]),
            "target_label": _label_for_object(target["object"]),
            **({"edge_text": operation["edgeText"]} if operation.get("edgeText") is not None else {}),
        },
    )
    if len(candidates) != 1:
        raise ValueError(f"insert_node_between expected exactly 1 matching edge, got {len(candidates)}")
    return candidates[0]


def _line_edge_endpoints(edge_obj: dict[str, Any]) -> tuple[str, str]:
    endpoints = edge_obj.get("associationList", [])
    if len(endpoints) != 2:
        raise ValueError("LineEdge requires exactly 2 endpoints")
    if not (isinstance(endpoints[0], dict) and "$" in endpoints[0] and isinstance(endpoints[1], dict) and "$" in endpoints[1]):
        raise ValueError("LineEdge endpoints must be path references")
    return endpoints[0]["$"], endpoints[1]["$"]


def _delete_paths(stage: list[Any], delete_paths: set[str], *, cascade: bool) -> dict[str, Any]:
    delete_indices = {int(path.removeprefix("/")) for path in delete_paths}
    removed_edge_count = 0
    kept: list[dict[str, Any]] = []
    old_to_new: dict[int, int] = {}

    for old_index, item in enumerate(stage):
        if old_index in delete_indices:
            continue
        if isinstance(item, dict) and item.get("_") == "LineEdge":
            source_path, target_path = _line_edge_endpoints(item)
            if int(source_path.removeprefix("/")) in delete_indices or int(target_path.removeprefix("/")) in delete_indices:
                if cascade:
                    removed_edge_count += 1
                    continue
                raise ValueError("delete would leave dangling LineEdge references; set cascade=true")
        elif isinstance(item, dict) and item.get("_") == "MultiTargetUndirectedEdge":
            endpoints = [ref["$"] for ref in item.get("associationList", []) if isinstance(ref, dict) and "$" in ref]
            remaining = [path for path in endpoints if int(path.removeprefix("/")) not in delete_indices]
            if len(remaining) < len(endpoints):
                if not cascade:
                    raise ValueError("delete would leave dangling MultiTargetUndirectedEdge references; set cascade=true")
                if len(remaining) < 2:
                    removed_edge_count += 1
                    continue
                item["associationList"] = [{"$": path} for path in remaining]
                rect_rates = item.get("rectRates", [])
                item["rectRates"] = [rect_rates[i] for i, path in enumerate(endpoints) if int(path.removeprefix("/")) not in delete_indices]
        old_to_new[old_index] = len(kept)
        kept.append(item)

    for item in kept:
        if not isinstance(item, dict):
            continue
        if item.get("_") == "Section":
            new_children = []
            for child in item.get("children", []):
                if not (isinstance(child, dict) and "$" in child):
                    continue
                old_index = int(child["$"].removeprefix("/"))
                if old_index in delete_indices:
                    continue
                new_children.append({"$": f"/{old_to_new[old_index]}"})
            item["children"] = new_children
        elif item.get("_") == "LineEdge":
            source_path, target_path = _line_edge_endpoints(item)
            item["associationList"] = [
                {"$": f"/{old_to_new[int(source_path.removeprefix('/'))]}"},
                {"$": f"/{old_to_new[int(target_path.removeprefix('/'))]}"},
            ]
        elif item.get("_") == "MultiTargetUndirectedEdge":
            item["associationList"] = [
                {"$": f"/{old_to_new[int(ref['$'].removeprefix('/'))]}"}
                for ref in item.get("associationList", [])
                if isinstance(ref, dict) and "$" in ref
            ]

    stage[:] = kept
    return {
        "deleted_count": len(delete_indices),
        "deleted_paths": sorted(delete_paths),
        "cascade_deleted_edges": removed_edge_count,
        "remaining_count": len(stage),
    }


def _validate_object(
    path: str,
    item: dict[str, Any],
    attachment_names: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    class_name = item["_"]
    for field in ("uuid",):
        if field not in item:
            errors.append(f"{path} ({class_name}) missing required field: {field}")
    if class_name in {"TextNode", "UrlNode", "ImageNode", "SvgNode", "ConnectPoint"}:
        if "collisionBox" not in item:
            errors.append(f"{path} ({class_name}) missing collisionBox")
    if class_name == "TextNode" and "text" not in item:
        errors.append(f"{path} (TextNode) missing text")
    if class_name == "UrlNode":
        for field in ("title", "url"):
            if field not in item:
                errors.append(f"{path} (UrlNode) missing {field}")
    if class_name == "Section":
        if "children" not in item or not isinstance(item.get("children"), list):
            errors.append(f"{path} (Section) missing children list")
    if class_name == "PenStroke":
        if len(item.get("segments", [])) < 2:
            errors.append(f"{path} (PenStroke) requires at least 2 segments")
    if class_name == "LineEdge":
        if len(item.get("associationList", [])) != 2:
            errors.append(f"{path} (LineEdge) associationList must contain exactly 2 endpoints")
    if class_name == "MultiTargetUndirectedEdge":
        if len(item.get("associationList", [])) < 2:
            errors.append(f"{path} (MultiTargetUndirectedEdge) requires at least 2 endpoints")
        if len(item.get("associationList", [])) != len(item.get("rectRates", [])):
            errors.append(f"{path} (MultiTargetUndirectedEdge) rectRates length mismatch")
    if class_name in {"ImageNode", "SvgNode"}:
        attachment_id = item.get("attachmentId")
        if not attachment_id:
            errors.append(f"{path} ({class_name}) missing attachmentId")
        elif not any(name.startswith(f"{attachment_id}.") for name in attachment_names):
            warnings.append(f"{path} ({class_name}) attachmentId {attachment_id} not found in attachments/")


def _validate_expected(stage: list[Any], expected: dict[str, Any], path_map: dict[str, Any], errors: list[str]) -> None:
    texts = [item.get("text", "") for _, item in walk_serialized(stage) if isinstance(item, dict) and item.get("_") == "TextNode"]
    section_titles = [item.get("text", "") for _, item in walk_serialized(stage) if isinstance(item, dict) and item.get("_") == "Section"]
    edge_pairs = []
    for _, item in walk_serialized(stage):
        if not isinstance(item, dict) or item.get("_") not in EDGE_TYPES:
            continue
        labels = []
        for ref in item.get("associationList", []):
            target = get_by_path(path_map["/"], ref["$"])
            labels.append(_label_for_object(target) if isinstance(target, dict) else "")
        edge_pairs.append(labels)

    for text in expected.get("texts", []):
        if text not in texts:
            errors.append(f"Expected text node not found: {text}")
    for title in expected.get("sections", []):
        if title not in section_titles:
            errors.append(f"Expected section not found: {title}")
    for endpoints in expected.get("edges", []):
        if endpoints not in edge_pairs:
            errors.append(f"Expected edge not found: {endpoints}")


def _load_attachments(items: list[dict[str, Any]]) -> dict[str, bytes]:
    attachments: dict[str, bytes] = {}
    for item in items:
        attachment_id = item["id"]
        source = Path(item["source"]).resolve()
        extension = item.get("extension") or source.suffix
        if not extension.startswith("."):
            extension = f".{extension}"
        attachments[f"{attachment_id}{extension.lower()}"] = source.read_bytes()
    return attachments


def _unpack_msgpack(payload: bytes) -> Any:
    return msgpack.unpackb(payload, raw=False)


def _pack_msgpack(data: Any) -> bytes:
    return msgpack.packb(data, use_bin_type=True)


def _rect_from_item(item: dict[str, Any], *, default_width: float = 200, default_height: float = 76) -> tuple[float, float, float, float]:
    if "rect" in item:
        rect = item["rect"]
        return float(rect["x"]), float(rect["y"]), float(rect["width"]), float(rect["height"])
    return (
        float(item.get("x", 0)),
        float(item.get("y", 0)),
        float(item.get("width", default_width)),
        float(item.get("height", default_height)),
    )


def _vector_like(value: Any | None, default_x: float, default_y: float) -> dict[str, Any]:
    if value is None:
        return vector(default_x, default_y)
    if isinstance(value, dict) and "_" in value:
        return value
    if isinstance(value, dict):
        return vector(float(value.get("x", default_x)), float(value.get("y", default_y)))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return vector(float(value[0]), float(value[1]))
    raise TypeError(f"Unsupported vector value: {value!r}")


def _rounded(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return round(float(value), 2)
