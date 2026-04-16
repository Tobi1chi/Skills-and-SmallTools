from __future__ import annotations

import json
import math
import unicodedata
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
BLOCKING_NODE_TYPES = {"TextNode", "UrlNode", "ImageNode", "SvgNode"}

DEFAULT_FONT_SIZE = 32
DEFAULT_LINE_HEIGHT = 1.5
DEFAULT_NODE_PADDING = 14
DEFAULT_SECTION_PADDING = 30
DEFAULT_SECTION_TITLE_HEIGHT = 50
DEFAULT_SECTION_MIN_SIZE = 100
DEFAULT_MIN_GAP = 200.0
EDGE_ROUTING_CLEARANCE = 48.0
POINT_DEFAULT_SIZE = 30.0


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
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

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


def generate_prg_from_spec(
    spec: dict[str, Any],
    *,
    layout: str = "auto",
) -> tuple[list[Any], dict[str, bytes], dict[str, Any], list[Any], dict[str, Any]]:
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


@dataclass(slots=True)
class SegmentHit:
    t: float
    x: float
    y: float
    side: str


def generate_prg_from_spec(
    spec: dict[str, Any],
    *,
    layout: str = "auto",
) -> tuple[list[Any], dict[str, bytes], dict[str, Any], list[Any], dict[str, Any]]:
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

    normalize_stage_geometry(stage)
    if layout != "off":
        import graph_layout

        graph_layout.apply_layout_to_stage(
            stage,
            layout_plan=_stage_layout_plan(spec.get("layoutPlan"), id_to_index),
            graph_intent=spec.get("graphIntent"),
            strategy=layout,
        )
    attachments = _load_attachments(spec.get("attachments", []))
    metadata = spec.get("metadata") or {"version": "2.2.0"}
    tags = spec.get("tags") or []
    references = spec.get("references") or {"sections": {}, "files": []}
    return stage, attachments, metadata, tags, references


def _stage_layout_plan(layout_plan: Any, id_to_index: dict[str, int]) -> dict[str, Any] | None:
    if not isinstance(layout_plan, dict):
        return None

    def translate(value: Any) -> Any:
        if isinstance(value, str) and value in id_to_index:
            return f"/{id_to_index[value]}"
        if isinstance(value, list):
            return [translate(item) for item in value]
        if isinstance(value, dict):
            return {key: translate(item) for key, item in value.items()}
        return value

    return translate(layout_plan)


def inspect_document(document: PrgDocument, *, sample_limit: int = 20) -> dict[str, Any]:
    normalize_stage_geometry(document.stage)
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


def validate_document(document: PrgDocument, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    normalize_stage_geometry(document.stage)
    return _validate_document_impl(document, expected=expected)


def _validate_document_impl(document: PrgDocument, expected: dict[str, Any] | None = None) -> dict[str, Any]:
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


def normalize_stage_geometry(stage: list[Any]) -> None:
    for _, item in walk_serialized(stage):
        if isinstance(item, dict) and item.get("_") == "TextNode":
            _normalize_text_node_geometry(item)


def _normalize_text_node_geometry(node: dict[str, Any]) -> None:
    rect = get_primary_rectangle(node.get("collisionBox"))
    if rect is None:
        rect = RectBounds(0, 0, 200, 76)
    font_size = DEFAULT_FONT_SIZE * math.pow(2, int(node.get("fontScaleLevel", 0)))
    size_adjust = node.get("sizeAdjust", "auto")
    text = node.get("text", "")
    if size_adjust == "manual":
        wrap_width = max(rect.width - DEFAULT_NODE_PADDING * 2, 1)
        measured = measure_wrapped_text_size(text, font_size, wrap_width, DEFAULT_LINE_HEIGHT)
        width = rect.width
        height = measured.height + DEFAULT_NODE_PADDING * 2
    else:
        measured = measure_multiline_text_size(text, font_size, DEFAULT_LINE_HEIGHT)
        width = measured.width + DEFAULT_NODE_PADDING * 2
        height = measured.height + DEFAULT_NODE_PADDING * 2
    node["collisionBox"] = collision_box(rect.x, rect.y, width, height)


def measure_multiline_text_size(text: str, font_size: float, line_height: float) -> RectBounds:
    lines = text.split("\n")
    width = 0.0
    height = 0.0
    for line in lines:
        width = max(width, estimate_text_width(line, font_size))
        height += font_size * line_height
    return RectBounds(0, 0, math.ceil(width), height)


def measure_wrapped_text_size(text: str, font_size: float, limit_width: float, line_height: float) -> RectBounds:
    lines = wrap_text_to_lines(text, font_size, limit_width)
    width = 0.0
    height = 0.0
    for line in lines:
        width = max(width, estimate_text_width(line, font_size))
        height += font_size * line_height
    return RectBounds(0, 0, math.ceil(width), height)


def wrap_text_to_lines(text: str, font_size: float, limit_width: float) -> list[str]:
    current_line = ""
    lines: list[str] = []
    for char in text:
        if char == "\n":
            lines.append(current_line)
            current_line = ""
            continue
        if estimate_text_width(current_line + char, font_size) > limit_width:
            lines.append(current_line)
            current_line = char
        else:
            current_line += char
    if current_line or not lines:
        lines.append(current_line)
    return lines


def estimate_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for char in text:
        width += font_size * _char_width_factor(char)
    return math.ceil(width)


def _char_width_factor(char: str) -> float:
    if not char:
        return 0.0
    if char == " ":
        return 0.33
    if char == "\t":
        return 1.32
    if unicodedata.combining(char):
        return 0.0
    if unicodedata.east_asian_width(char) in {"W", "F"}:
        return 1.0
    category = unicodedata.category(char)
    if category.startswith("P"):
        return 0.35
    if category.startswith("S"):
        return 0.8
    if char.isdigit():
        return 0.62
    if char.isupper():
        return 0.68
    if char.islower():
        return 0.56
    return 0.62


def _resolve_ref(stage_root: list[Any], ref: Any, path_map: dict[str, Any]) -> tuple[str | None, Any]:
    if isinstance(ref, dict) and "$" in ref:
        ref_path = ref["$"]
        return ref_path, get_by_path(stage_root, ref_path)
    return None, ref


def _pen_stroke_bounds(item: dict[str, Any]) -> RectBounds | None:
    points = []
    for segment in item.get("segments", []):
        location = segment.get("location", {}) if isinstance(segment, dict) else {}
        if isinstance(location, dict):
            points.append((float(location.get("x", 0)), float(location.get("y", 0))))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return RectBounds(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _bounds_for_object(
    stage_root: list[Any],
    path: str,
    item: dict[str, Any],
    path_map: dict[str, Any],
    bounds_cache: dict[str, RectBounds | None],
    section_members: dict[str, set[str]],
) -> RectBounds | None:
    if path in bounds_cache:
        return bounds_cache[path]
    class_name = item.get("_")
    rect: RectBounds | None = None
    if class_name in {"TextNode", "UrlNode", "ImageNode", "SvgNode", "ConnectPoint"}:
        rect = get_primary_rectangle(item.get("collisionBox"))
    elif class_name == "Section":
        rect = section_bounds(stage_root, path, item, path_map, bounds_cache, section_members)
    elif class_name == "PenStroke":
        rect = _pen_stroke_bounds(item)
    bounds_cache[path] = rect
    return rect


def section_member_paths(
    stage_root: list[Any],
    section_path: str,
    section_obj: dict[str, Any],
    path_map: dict[str, Any] | None = None,
    cache: dict[str, set[str]] | None = None,
) -> set[str]:
    if cache is None:
        cache = {}
    if section_path in cache:
        return cache[section_path]
    if path_map is None:
        path_map = collect_paths(stage_root)
    members: set[str] = set()
    for child in section_obj.get("children", []):
        child_path, child_obj = _resolve_ref(stage_root, child, path_map)
        if not child_path or not isinstance(child_obj, dict):
            continue
        members.add(child_path)
        if child_obj.get("_") == "Section":
            members.update(section_member_paths(stage_root, child_path, child_obj, path_map, cache))
    cache[section_path] = members
    return members


def section_bounds(
    stage_root: list[Any],
    section_path: str,
    section_obj: dict[str, Any],
    path_map: dict[str, Any] | None = None,
    bounds_cache: dict[str, RectBounds | None] | None = None,
    section_members: dict[str, set[str]] | None = None,
) -> RectBounds | None:
    if bounds_cache is None:
        bounds_cache = {}
    if section_path in bounds_cache:
        return bounds_cache[section_path]
    if path_map is None:
        path_map = collect_paths(stage_root)
    if section_members is None:
        section_members = {}

    child_rects: list[RectBounds] = []
    for child in section_obj.get("children", []):
        child_path, child_obj = _resolve_ref(stage_root, child, path_map)
        if not child_path or not isinstance(child_obj, dict):
            continue
        rect = _bounds_for_object(stage_root, child_path, child_obj, path_map, bounds_cache, section_members)
        if rect:
            child_rects.append(rect)

    title_width = estimate_text_width(section_obj.get("text", ""), DEFAULT_FONT_SIZE)
    if not child_rects:
        bounds_cache[section_path] = None
        return None

    left = min(rect.left for rect in child_rects) - DEFAULT_SECTION_PADDING
    right = max(rect.right for rect in child_rects) + DEFAULT_SECTION_PADDING
    top = min(rect.top for rect in child_rects) - DEFAULT_SECTION_PADDING - DEFAULT_SECTION_TITLE_HEIGHT
    bottom = max(rect.bottom for rect in child_rects) + DEFAULT_SECTION_PADDING
    width = max(right - left, title_width + DEFAULT_NODE_PADDING * 2)
    result = RectBounds(left, top, width, bottom - top)
    bounds_cache[section_path] = result
    return result


def extract_rect_objects(
    stage: list[Any],
    *,
    include_sections: bool = True,
    include_points: bool = False,
) -> list[dict[str, Any]]:
    path_map = collect_paths(stage)
    bounds_cache: dict[str, RectBounds | None] = {}
    section_members: dict[str, set[str]] = {}
    results: list[dict[str, Any]] = []
    for path, item in walk_serialized(stage):
        if not isinstance(item, dict) or "$" in item:
            continue
        class_name = item.get("_")
        rect: RectBounds | None = None
        descendants: set[str] = set()
        if class_name in {"TextNode", "UrlNode", "ImageNode", "SvgNode"}:
            rect = get_primary_rectangle(item.get("collisionBox"))
        elif class_name == "Section" and include_sections:
            rect = section_bounds(stage, path, item, path_map, bounds_cache, section_members)
            descendants = section_member_paths(stage, path, item, path_map, section_members)
        elif class_name == "ConnectPoint" and include_points:
            rect = get_primary_rectangle(item.get("collisionBox"))
        if rect:
            results.append({
                "path": path,
                "type": class_name,
                "uuid": item.get("uuid"),
                "label": _label_for_object(item),
                "rect": rect,
                "descendants": descendants,
            })
    return results

def rect_gap(first: RectBounds, second: RectBounds) -> float:
    dx = max(first.left - second.right, second.left - first.right, 0)
    dy = max(first.top - second.bottom, second.top - first.bottom, 0)
    if dx == 0 and dy == 0:
        return 0.0
    if dx == 0:
        return dy
    if dy == 0:
        return dx
    return math.hypot(dx, dy)


def _should_skip_pair(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if first["path"] == second["path"]:
        return True
    if first["type"] == "Section" and second["path"] in first.get("descendants", set()):
        return True
    if second["type"] == "Section" and first["path"] in second.get("descendants", set()):
        return True
    return False


def find_overlaps(
    document: PrgDocument,
    *,
    include_sections: bool = True,
    include_points: bool = False,
    min_overlap_area: float = 1.0,
    ignore_containment: bool = False,
    min_gap: float = DEFAULT_MIN_GAP,
) -> dict[str, Any]:
    normalize_stage_geometry(document.stage)
    rects = extract_rect_objects(document.stage, include_sections=include_sections, include_points=include_points)
    overlaps: list[dict[str, Any]] = []
    spacing_violations: list[dict[str, Any]] = []
    for index, first in enumerate(rects):
        for second in rects[index + 1 :]:
            if _should_skip_pair(first, second):
                continue
            overlap = intersect_rect(first["rect"], second["rect"])
            if overlap is not None and overlap.area >= min_overlap_area:
                if not (ignore_containment and (_contains(first["rect"], second["rect"]) or _contains(second["rect"], first["rect"]))):
                    overlaps.append({
                        "first": _rect_report(first),
                        "second": _rect_report(second),
                        "overlap_rect": {
                            "x": _rounded(overlap.x),
                            "y": _rounded(overlap.y),
                            "width": _rounded(overlap.width),
                            "height": _rounded(overlap.height),
                        },
                        "overlap_area": _rounded(overlap.area),
                    })
            if min_gap > 0:
                gap = rect_gap(first["rect"], second["rect"])
                if gap < min_gap:
                    spacing_violations.append({
                        "first": _rect_report(first),
                        "second": _rect_report(second),
                        "actual_gap": _rounded(gap),
                        "required_gap": _rounded(min_gap),
                    })
    return {
        "ok": not overlaps and not spacing_violations,
        "checked_count": len(rects),
        "overlap_count": len(overlaps),
        "spacing_count": len(spacing_violations),
        "overlaps": overlaps,
        "spacing_violations": spacing_violations,
    }


def point_on_rect(rect: RectBounds, rate: Any | None) -> tuple[float, float]:
    if isinstance(rate, dict):
        rx = float(rate.get("x", 0.5))
        ry = float(rate.get("y", 0.5))
    elif isinstance(rate, (list, tuple)) and len(rate) == 2:
        rx = float(rate[0])
        ry = float(rate[1])
    else:
        rx = 0.5
        ry = 0.5
    return (rect.left + rect.width * rx, rect.top + rect.height * ry)


def _point_inside_rect(point: tuple[float, float], rect: RectBounds) -> bool:
    return rect.left < point[0] < rect.right and rect.top < point[1] < rect.bottom


def _segment_rect_hits(start: tuple[float, float], end: tuple[float, float], rect: RectBounds) -> list[SegmentHit]:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    hits: list[SegmentHit] = []

    def add_hit(t: float, x: float, y: float, side: str) -> None:
        if t < 0 or t > 1:
            return
        for existing in hits:
            if abs(existing.t - t) < 1e-6 and abs(existing.x - x) < 1e-6 and abs(existing.y - y) < 1e-6:
                return
        hits.append(SegmentHit(t, x, y, side))

    if dx != 0:
        t_left = (rect.left - x1) / dx
        y_left = y1 + t_left * dy
        if rect.top <= y_left <= rect.bottom:
            add_hit(t_left, rect.left, y_left, "left")
        t_right = (rect.right - x1) / dx
        y_right = y1 + t_right * dy
        if rect.top <= y_right <= rect.bottom:
            add_hit(t_right, rect.right, y_right, "right")
    if dy != 0:
        t_top = (rect.top - y1) / dy
        x_top = x1 + t_top * dx
        if rect.left <= x_top <= rect.right:
            add_hit(t_top, x_top, rect.top, "top")
        t_bottom = (rect.bottom - y1) / dy
        x_bottom = x1 + t_bottom * dx
        if rect.left <= x_bottom <= rect.right:
            add_hit(t_bottom, x_bottom, rect.bottom, "bottom")
    hits.sort(key=lambda item: item.t)
    return hits


def segment_passes_through_rect(start: tuple[float, float], end: tuple[float, float], rect: RectBounds) -> dict[str, Any] | None:
    if _point_inside_rect(start, rect) or _point_inside_rect(end, rect):
        return None
    hits = _segment_rect_hits(start, end, rect)
    if len(hits) < 2:
        return None
    entry = hits[0]
    exit_hit = hits[-1]
    if exit_hit.t <= entry.t or entry.side == exit_hit.side:
        return None
    return {"entry": entry, "exit": exit_hit, "t": (entry.t + exit_hit.t) / 2}


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def choose_route_point(start: tuple[float, float], end: tuple[float, float], rect: RectBounds, clearance: float) -> tuple[float, float]:
    candidates = [
        (rect.left - clearance, rect.top - clearance),
        (rect.right + clearance, rect.top - clearance),
        (rect.left - clearance, rect.bottom + clearance),
        (rect.right + clearance, rect.bottom + clearance),
    ]
    viable: list[tuple[float, tuple[float, float]]] = []
    for candidate in candidates:
        if segment_passes_through_rect(start, candidate, rect) is None and segment_passes_through_rect(candidate, end, rect) is None:
            viable.append((_distance(start, candidate) + _distance(candidate, end), candidate))
    if viable:
        viable.sort(key=lambda item: item[0])
        return viable[0][1]
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        return (midpoint[0], rect.top - clearance if midpoint[1] <= rect.center_y else rect.bottom + clearance)
    return (rect.left - clearance if midpoint[0] <= rect.center_x else rect.right + clearance, midpoint[1])


def detect_edge_block_crossings(document: PrgDocument, *, include_sections: bool = False) -> dict[str, Any]:
    normalize_stage_geometry(document.stage)
    path_map = collect_paths(document.stage)
    bounds_cache: dict[str, RectBounds | None] = {}
    section_members: dict[str, set[str]] = {}
    blockers = extract_rect_objects(document.stage, include_sections=include_sections, include_points=False)
    blockers = [item for item in blockers if item["type"] in BLOCKING_NODE_TYPES or (include_sections and item["type"] == "Section")]

    checked_edges = 0
    crossing_edges: list[dict[str, Any]] = []
    for path, item in walk_serialized(document.stage):
        if not isinstance(item, dict) or item.get("_") != "LineEdge":
            continue
        checked_edges += 1
        associations = item.get("associationList", [])
        if len(associations) != 2:
            continue
        source_path, source_obj = _resolve_ref(document.stage, associations[0], path_map)
        target_path, target_obj = _resolve_ref(document.stage, associations[1], path_map)
        if not source_path or not target_path or not isinstance(source_obj, dict) or not isinstance(target_obj, dict):
            continue
        source_rect = _bounds_for_object(document.stage, source_path, source_obj, path_map, bounds_cache, section_members)
        target_rect = _bounds_for_object(document.stage, target_path, target_obj, path_map, bounds_cache, section_members)
        if source_rect is None or target_rect is None:
            continue
        start = point_on_rect(source_rect, item.get("sourceRectangleRate"))
        end = point_on_rect(target_rect, item.get("targetRectangleRate"))
        crossings: list[dict[str, Any]] = []
        for blocker in blockers:
            if blocker["path"] in {source_path, target_path}:
                continue
            if blocker["type"] == "Section" and (source_path in blocker.get("descendants", set()) or target_path in blocker.get("descendants", set())):
                continue
            crossing = segment_passes_through_rect(start, end, blocker["rect"])
            if crossing is None:
                continue
            route_point = choose_route_point(start, end, blocker["rect"], EDGE_ROUTING_CLEARANCE)
            crossings.append({
                "block": _rect_report(blocker),
                "entry": {"x": _rounded(crossing["entry"].x), "y": _rounded(crossing["entry"].y), "side": crossing["entry"].side},
                "exit": {"x": _rounded(crossing["exit"].x), "y": _rounded(crossing["exit"].y), "side": crossing["exit"].side},
                "route_point": {"x": _rounded(route_point[0]), "y": _rounded(route_point[1])},
                "t": crossing["t"],
            })
        crossings.sort(key=lambda item: item["t"])
        if crossings:
            crossing_edges.append({
                "path": path,
                "uuid": item.get("uuid"),
                "label": item.get("text", ""),
                "source": _endpoint_summary(path_map, associations[0]),
                "target": _endpoint_summary(path_map, associations[1]),
                "crossing_count": len(crossings),
                "crossings": crossings,
            })
    return {"ok": not crossing_edges, "checked_edge_count": checked_edges, "crossing_edge_count": len(crossing_edges), "crossings": crossing_edges}


def insert_connect_points_for_crossing_edges(
    stage: list[Any],
    *,
    clearance: float = EDGE_ROUTING_CLEARANCE,
    point_size: float = POINT_DEFAULT_SIZE,
    include_sections: bool = False,
) -> dict[str, Any]:
    report = detect_edge_block_crossings(PrgDocument(Path("<memory>"), stage, {"version": "2.2.0"}, [], {}, {}), include_sections=include_sections)
    if report["ok"]:
        return {"ok": True, "modified_edge_count": 0, "inserted_point_count": 0, "inserted_points": [], "crossing_report": report}

    inserted_points: list[dict[str, Any]] = []
    modified_edges = 0
    for edge_report in report["crossings"]:
        edge = get_by_path(stage, edge_report["path"])
        if not isinstance(edge, dict):
            continue
        associations = list(edge.get("associationList", []))
        if len(associations) != 2:
            continue
        source_rate = edge.get("sourceRectangleRate")
        target_rate = edge.get("targetRectangleRate")
        original_text = edge.get("text", "")
        original_color = edge.get("color")
        line_type = edge.get("lineType", "solid")
        point_refs: list[dict[str, Any]] = []

        for crossing in edge_report["crossings"]:
            route = crossing["route_point"]
            point_uuid = str(uuid.uuid4())
            stage.append({
                "_": "ConnectPoint",
                "details": [],
                "collisionBox": collision_box(float(route["x"]) - point_size / 2, float(route["y"]) - point_size / 2, point_size, point_size),
                "uuid": point_uuid,
            })
            point_refs.append({"$": f"/{len(stage) - 1}"})
            inserted_points.append({"uuid": point_uuid, "x": route["x"], "y": route["y"], "edge_path": edge_report["path"]})

        edge["associationList"] = [associations[0], point_refs[0]]
        edge["sourceRectangleRate"] = source_rate or vector(0.5, 0.5)
        edge["targetRectangleRate"] = vector(0.5, 0.5)
        edge["text"] = original_text
        edge["lineType"] = line_type
        if original_color is not None:
            edge["color"] = original_color
        modified_edges += 1

        previous_ref = point_refs[0]
        for next_ref in point_refs[1:]:
            stage.append({
                "_": "LineEdge",
                "associationList": [previous_ref, next_ref],
                "color": original_color or color(),
                "targetRectangleRate": vector(0.5, 0.5),
                "sourceRectangleRate": vector(0.5, 0.5),
                "uuid": str(uuid.uuid4()),
                "text": "",
                "lineType": line_type,
            })
            previous_ref = next_ref
        stage.append({
            "_": "LineEdge",
            "associationList": [previous_ref, associations[1]],
            "color": original_color or color(),
            "targetRectangleRate": target_rate or vector(0.5, 0.5),
            "sourceRectangleRate": vector(0.5, 0.5),
            "uuid": str(uuid.uuid4()),
            "text": "",
            "lineType": line_type,
        })
    normalize_stage_geometry(stage)
    return {"ok": True, "modified_edge_count": modified_edges, "inserted_point_count": len(inserted_points), "inserted_points": inserted_points, "crossing_report": report}
