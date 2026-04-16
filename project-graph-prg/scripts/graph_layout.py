from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geometry_prg_tools as geom


GRAPH_TYPES = {
    "tree",
    "mindmap",
    "dag",
    "cyclic_dependency",
    "dense_network",
    "pipeline",
    "clustered",
}
STRATEGY_BY_TYPE = {
    "tree": "tree",
    "mindmap": "mindmap",
    "dag": "layered",
    "cyclic_dependency": "scc-layered",
    "dense_network": "force",
    "pipeline": "pipeline",
    "clustered": "clustered",
}
STRATEGIES = set(STRATEGY_BY_TYPE.values())
DIRECTIONS = {"right", "left", "down", "up"}
DEFAULT_SPACING = {
    "nodeGap": 180.0,
    "layerGap": 320.0,
    "clusterGap": 420.0,
    "minGap": geom.DEFAULT_MIN_GAP,
}


@dataclass(slots=True)
class LayoutNode:
    key: str
    obj: dict[str, Any]
    label: str
    width: float
    height: float
    source_id: str | None = None


@dataclass(slots=True)
class LayoutEdge:
    source: str
    target: str
    directed: bool = True
    obj: dict[str, Any] | None = None


@dataclass(slots=True)
class LayoutModel:
    nodes: dict[str, LayoutNode]
    edges: list[LayoutEdge]
    sections: dict[str, set[str]]
    section_labels: dict[str, str]

    def directed_adjacency(self, subset: set[str] | None = None) -> dict[str, list[str]]:
        allowed = subset or set(self.nodes)
        adjacency = {key: [] for key in allowed}
        for edge in self.edges:
            if edge.directed and edge.source in allowed and edge.target in allowed:
                adjacency.setdefault(edge.source, []).append(edge.target)
        return {key: sorted(set(values), key=_natural_key) for key, values in adjacency.items()}

    def undirected_adjacency(self, subset: set[str] | None = None) -> dict[str, list[str]]:
        allowed = subset or set(self.nodes)
        adjacency = {key: [] for key in allowed}
        for edge in self.edges:
            if edge.source in allowed and edge.target in allowed:
                adjacency.setdefault(edge.source, []).append(edge.target)
                adjacency.setdefault(edge.target, []).append(edge.source)
        return {key: sorted(set(values), key=_natural_key) for key, values in adjacency.items()}


def classify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    model = _model_from_spec(spec)
    return _classification_payload(model, spec.get("graphIntent"), spec.get("layoutPlan"))


def classify_stage(stage: list[Any]) -> dict[str, Any]:
    geom.normalize_stage_geometry(stage)
    model = _model_from_stage(stage)
    return _classification_payload(model, None, None)


def apply_layout_to_spec(
    spec: dict[str, Any],
    *,
    layout_plan: dict[str, Any] | None = None,
    graph_intent: dict[str, Any] | None = None,
    strategy: str = "auto",
    direction: str | None = None,
    min_gap: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    model = _model_from_spec(spec)
    plan = _complete_plan(model, graph_intent or spec.get("graphIntent"), layout_plan or spec.get("layoutPlan"), strategy, direction, min_gap, seed)
    positions = _layout_positions(model, plan)
    _write_spec_positions(model, positions)
    _write_spec_edge_rates(model, positions)
    return _layout_report(model, plan, positions)


def apply_layout_to_stage(
    stage: list[Any],
    *,
    layout_plan: dict[str, Any] | None = None,
    graph_intent: dict[str, Any] | None = None,
    strategy: str = "auto",
    direction: str | None = None,
    min_gap: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    geom.normalize_stage_geometry(stage)
    model = _model_from_stage(stage)
    plan = _complete_plan(model, graph_intent, layout_plan, strategy, direction, min_gap, seed)
    positions = _layout_positions(model, plan)
    _write_stage_positions(model, positions)
    _write_stage_edge_rates(model, positions)
    geom.normalize_stage_geometry(stage)
    overlap = geom.find_overlaps(
        geom.PrgDocument(Path("<memory>"), stage, {"version": "2.2.0"}, [], {}, {}),
        include_sections=True,
        include_points=False,
        min_gap=float(plan["spacing"]["minGap"]),
    )
    report = _layout_report(model, plan, positions)
    report["geometry"] = overlap
    return report


def _classification_payload(
    model: LayoutModel,
    provided_intent: dict[str, Any] | None,
    provided_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = _graph_metrics(model)
    primary_type, confidence, evidence = _recommend_type(model, metrics, provided_intent, provided_plan)
    graph_intent = {
        "primaryType": primary_type,
        "secondaryTypes": _secondary_types(model, metrics, primary_type),
        "confidence": confidence,
        "evidence": evidence,
        "extractionFocus": _extraction_focus(primary_type),
        "fallbackType": _fallback_type(primary_type, metrics),
    }
    layout_plan = _recommended_plan(model, graph_intent, provided_plan)
    return {
        "metrics": metrics,
        "graphIntent": graph_intent,
        "layoutPlan": layout_plan,
        "recommendedGraphIntent": graph_intent,
        "recommendedLayoutPlan": layout_plan,
        "conflicts": _intent_conflicts(provided_intent, metrics, primary_type),
    }


def _model_from_spec(spec: dict[str, Any]) -> LayoutModel:
    nodes: dict[str, LayoutNode] = {}
    sections: dict[str, set[str]] = {}
    section_labels: dict[str, str] = {}
    objects = spec.get("objects", [])
    if not isinstance(objects, list):
        objects = []

    for item in objects:
        if not isinstance(item, dict):
            continue
        object_id = item.get("id")
        if not object_id:
            continue
        object_type = item.get("type")
        if object_type in {"TextNode", "UrlNode", "ImageNode", "SvgNode"}:
            width, height = _spec_size(item)
            nodes[object_id] = LayoutNode(object_id, item, _spec_label(item), width, height, object_id)

    edges: list[LayoutEdge] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        object_type = item.get("type")
        if object_type == "LineEdge":
            endpoints = item.get("endpoints") or [item.get("from"), item.get("to")]
            if len(endpoints) == 2 and endpoints[0] in nodes and endpoints[1] in nodes:
                edges.append(LayoutEdge(str(endpoints[0]), str(endpoints[1]), True, item))
        elif object_type == "MultiTargetUndirectedEdge":
            endpoints = [endpoint for endpoint in item.get("endpoints", []) if endpoint in nodes]
            for index, source in enumerate(endpoints):
                for target in endpoints[index + 1 :]:
                    edges.append(LayoutEdge(str(source), str(target), False, item))
        elif object_type == "Section":
            section_id = item.get("id")
            if section_id:
                members = {child for child in item.get("children", []) if child in nodes}
                if members:
                    sections[section_id] = members
                    section_labels[section_id] = item.get("text", section_id)
    return LayoutModel(nodes, edges, sections, section_labels)


def _model_from_stage(stage: list[Any]) -> LayoutModel:
    path_map = geom.collect_paths(stage)
    nodes: dict[str, LayoutNode] = {}
    for path, item in geom.walk_serialized(stage):
        if not isinstance(item, dict) or "$" in item:
            continue
        if item.get("_") not in {"TextNode", "UrlNode", "ImageNode", "SvgNode"}:
            continue
        rect = geom.get_primary_rectangle(item.get("collisionBox"))
        if rect is None:
            continue
        nodes[path] = LayoutNode(path, item, _stage_label(item), rect.width, rect.height, item.get("uuid"))

    edges: list[LayoutEdge] = []
    for _, item in geom.walk_serialized(stage):
        if not isinstance(item, dict) or "$" in item:
            continue
        if item.get("_") not in {"LineEdge", "MultiTargetUndirectedEdge"}:
            continue
        endpoints: list[str] = []
        for ref in item.get("associationList", []):
            if isinstance(ref, dict) and "$" in ref and ref["$"] in nodes:
                endpoints.append(ref["$"])
            elif isinstance(ref, dict) and "$" in ref:
                try:
                    target = geom.get_by_path(path_map["/"], ref["$"])
                except Exception:  # noqa: BLE001
                    continue
                target_path = _path_for_object(path_map, target)
                if target_path in nodes:
                    endpoints.append(target_path)
        if item.get("_") == "LineEdge" and len(endpoints) == 2:
            edges.append(LayoutEdge(endpoints[0], endpoints[1], True, item))
        elif item.get("_") == "MultiTargetUndirectedEdge" and len(endpoints) >= 2:
            for index, source in enumerate(endpoints):
                for target in endpoints[index + 1 :]:
                    edges.append(LayoutEdge(source, target, False, item))

    sections: dict[str, set[str]] = {}
    section_labels: dict[str, str] = {}
    for path, item in geom.walk_serialized(stage):
        if not isinstance(item, dict) or item.get("_") != "Section":
            continue
        members = geom.section_member_paths(stage, path, item, path_map)
        node_members = {member for member in members if member in nodes}
        if node_members:
            sections[path] = node_members
            section_labels[path] = item.get("text", path)
    return LayoutModel(nodes, edges, sections, section_labels)


def _path_for_object(path_map: dict[str, Any], target: Any) -> str | None:
    for path, item in path_map.items():
        if item is target:
            return path
    return None


def _graph_metrics(model: LayoutModel) -> dict[str, Any]:
    node_count = len(model.nodes)
    directed_edges = [(edge.source, edge.target) for edge in model.edges if edge.directed]
    all_edges = [(edge.source, edge.target) for edge in model.edges]
    density = 0.0
    if node_count > 1:
        density = len(set(all_edges)) / (node_count * (node_count - 1))
    indegree = {key: 0 for key in model.nodes}
    outdegree = {key: 0 for key in model.nodes}
    for source, target in directed_edges:
        outdegree[source] += 1
        indegree[target] += 1
    sccs = _tarjan(model, set(model.nodes))
    components = _components(model)
    roots = [key for key in model.nodes if indegree[key] == 0]
    leaves = [key for key in model.nodes if outdegree[key] == 0]
    max_degree = 0
    undirected = model.undirected_adjacency()
    if undirected:
        max_degree = max(len(values) for values in undirected.values())
    return {
        "node_count": node_count,
        "edge_count": len(model.edges),
        "directed_edge_count": len(directed_edges),
        "section_count": len(model.sections),
        "density": round(density, 4),
        "hasCycles": any(len(component) > 1 for component in sccs) or any(source == target for source, target in directed_edges),
        "component_count": len(components),
        "root_count": len(roots),
        "leaf_count": len(leaves),
        "max_indegree": max(indegree.values(), default=0),
        "max_outdegree": max(outdegree.values(), default=0),
        "max_degree": max_degree,
        "scc_count": len(sccs),
        "max_scc_size": max((len(component) for component in sccs), default=0),
    }


def _recommend_type(
    model: LayoutModel,
    metrics: dict[str, Any],
    provided_intent: dict[str, Any] | None,
    provided_plan: dict[str, Any] | None,
) -> tuple[str, float, list[str]]:
    requested = (provided_intent or {}).get("primaryType")
    if requested in GRAPH_TYPES:
        return requested, float((provided_intent or {}).get("confidence", 0.9)), ["spec declares graphIntent.primaryType"]
    if (provided_plan or {}).get("strategy") == "mindmap":
        return "mindmap", 0.82, ["layoutPlan.strategy requests mindmap"]
    if model.sections:
        return "clustered", 0.82, ["Section membership is present"]
    if metrics["node_count"] <= 1:
        return "tree", 0.65, ["single node or empty graph"]
    if metrics["hasCycles"]:
        return "cyclic_dependency", 0.86, ["directed cycle detected"]
    if _looks_like_mindmap(model, metrics):
        return "mindmap", 0.78, ["one central topic dominates shallow branches"]
    if _looks_like_pipeline(model, metrics):
        return "pipeline", 0.78, ["dominant directed path detected"]
    if _looks_like_tree(metrics):
        return "tree", 0.84, ["acyclic graph with tree-like indegree"]
    if metrics["density"] >= 0.35 or metrics["max_degree"] >= 4:
        return "dense_network", 0.78, ["high edge density or hub degree"]
    if metrics["directed_edge_count"] > 0:
        return "dag", 0.8, ["directed acyclic dependencies detected"]
    return "dense_network", 0.58, ["no directed hierarchy detected"]


def _looks_like_tree(metrics: dict[str, Any]) -> bool:
    if metrics["hasCycles"] or metrics["node_count"] == 0:
        return False
    return metrics["max_indegree"] <= 1 and metrics["directed_edge_count"] >= max(0, metrics["node_count"] - metrics["component_count"])


def _looks_like_mindmap(model: LayoutModel, metrics: dict[str, Any]) -> bool:
    if metrics["hasCycles"] or metrics["node_count"] < 4 or metrics["component_count"] != 1:
        return False
    adjacency = model.undirected_adjacency()
    hub = max(adjacency, key=lambda node: (len(adjacency[node]), _natural_key(node)))
    if len(adjacency[hub]) < 3:
        return False
    distances = {hub: 0}
    queue = [hub]
    while queue:
        node = queue.pop(0)
        for neighbor in adjacency.get(node, []):
            if neighbor not in distances:
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)
    return len(distances) == metrics["node_count"] and max(distances.values(), default=0) <= 2


def _looks_like_pipeline(model: LayoutModel, metrics: dict[str, Any]) -> bool:
    if metrics["hasCycles"] or metrics["directed_edge_count"] == 0:
        return False
    path = _longest_path(model, set(model.nodes))
    return len(path) >= max(3, math.ceil(metrics["node_count"] * 0.6)) and metrics["max_outdegree"] <= 2


def _secondary_types(model: LayoutModel, metrics: dict[str, Any], primary_type: str) -> list[str]:
    result: list[str] = []
    if model.sections and primary_type != "clustered":
        result.append("clustered")
    if metrics["hasCycles"] and primary_type != "cyclic_dependency":
        result.append("cyclic_dependency")
    if metrics["density"] >= 0.25 and primary_type != "dense_network":
        result.append("dense_network")
    if _looks_like_pipeline(model, metrics) and primary_type != "pipeline":
        result.append("pipeline")
    return result[:3]


def _extraction_focus(primary_type: str) -> list[str]:
    return {
        "tree": ["identify roots and parent-child edges", "keep sibling order explicit"],
        "mindmap": ["identify the central topic", "extract first-level branches before details"],
        "dag": ["extract directional dependency edges", "identify entry and exit nodes"],
        "cyclic_dependency": ["extract feedback loops", "preserve strongly connected dependency groups"],
        "dense_network": ["extract important relationships", "avoid inventing hierarchy where none exists"],
        "pipeline": ["extract the main path", "attach branch inputs and outputs to path steps"],
        "clustered": ["identify groups or sections", "extract intra-cluster and cross-cluster edges separately"],
    }[primary_type]


def _fallback_type(primary_type: str, metrics: dict[str, Any]) -> str:
    if primary_type == "dag" and metrics["hasCycles"]:
        return "cyclic_dependency"
    if primary_type in {"tree", "pipeline"}:
        return "dag"
    if primary_type == "clustered":
        return "dag" if metrics["directed_edge_count"] else "dense_network"
    return "dense_network"


def _recommended_plan(
    model: LayoutModel,
    graph_intent: dict[str, Any],
    provided_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    primary_type = graph_intent["primaryType"]
    spacing = dict(DEFAULT_SPACING)
    if isinstance((provided_plan or {}).get("spacing"), dict):
        spacing.update({key: float(value) for key, value in provided_plan["spacing"].items() if key in spacing})
    plan = {
        "strategy": STRATEGY_BY_TYPE[primary_type],
        "direction": (provided_plan or {}).get("direction", "right"),
        "root": (provided_plan or {}).get("root") or _choose_root(model),
        "mainPath": (provided_plan or {}).get("mainPath") or _longest_path(model, set(model.nodes)),
        "clusters": (provided_plan or {}).get("clusters") or _plan_clusters(model),
        "spacing": spacing,
        "seed": int((provided_plan or {}).get("seed", 7)),
    }
    if (provided_plan or {}).get("strategy") in STRATEGIES:
        plan["strategy"] = provided_plan["strategy"]
    return plan


def _intent_conflicts(provided_intent: dict[str, Any] | None, metrics: dict[str, Any], recommended: str) -> list[str]:
    if not provided_intent:
        return []
    conflicts: list[str] = []
    primary = provided_intent.get("primaryType")
    if primary and primary != recommended:
        conflicts.append(f"provided primaryType={primary!r} differs from script recommendation {recommended!r}")
    if primary in {"tree", "dag", "pipeline"} and metrics["hasCycles"]:
        conflicts.append(f"provided primaryType={primary!r} conflicts with hasCycles=true")
    if primary == "tree" and metrics["max_indegree"] > 1:
        conflicts.append("provided primaryType='tree' conflicts with max_indegree > 1")
    return conflicts


def _complete_plan(
    model: LayoutModel,
    graph_intent: dict[str, Any] | None,
    layout_plan: dict[str, Any] | None,
    strategy: str,
    direction: str | None,
    min_gap: float | None,
    seed: int | None,
) -> dict[str, Any]:
    classification = _classification_payload(model, graph_intent, layout_plan)
    plan = classification["recommendedLayoutPlan"]
    if isinstance(layout_plan, dict):
        merged = dict(plan)
        merged.update({key: value for key, value in layout_plan.items() if key != "spacing"})
        merged["spacing"] = dict(plan["spacing"])
        if isinstance(layout_plan.get("spacing"), dict):
            merged["spacing"].update({key: float(value) for key, value in layout_plan["spacing"].items() if key in DEFAULT_SPACING})
        plan = merged
    if strategy != "auto":
        if strategy not in STRATEGIES:
            raise ValueError(f"Unsupported layout strategy: {strategy}")
        plan["strategy"] = strategy
    if direction is not None:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported layout direction: {direction}")
        plan["direction"] = direction
    if min_gap is not None:
        plan.setdefault("spacing", {})["minGap"] = float(min_gap)
    if seed is not None:
        plan["seed"] = int(seed)
    plan["spacing"] = _normalized_spacing(plan.get("spacing"))
    plan.setdefault("root", _choose_root(model))
    plan.setdefault("mainPath", _longest_path(model, set(model.nodes)))
    plan.setdefault("clusters", _plan_clusters(model))
    plan.setdefault("seed", 7)
    return plan


def _normalized_spacing(spacing: dict[str, Any] | None) -> dict[str, float]:
    result = dict(DEFAULT_SPACING)
    if isinstance(spacing, dict):
        for key in result:
            if key in spacing:
                result[key] = float(spacing[key])
    result["minGap"] = max(0.0, result["minGap"])
    result["nodeGap"] = max(result["nodeGap"], result["minGap"])
    result["layerGap"] = max(result["layerGap"], result["minGap"])
    result["clusterGap"] = max(result["clusterGap"], result["minGap"])
    return result


def _layout_positions(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    strategy = plan["strategy"]
    if not model.nodes:
        return {}
    if strategy == "tree":
        positions = _layout_tree(model, plan)
    elif strategy == "mindmap":
        positions = _layout_mindmap(model, plan)
    elif strategy == "layered":
        positions = _layout_layered(model, plan, set(model.nodes))
    elif strategy == "scc-layered":
        positions = _layout_scc_layered(model, plan)
    elif strategy == "force":
        positions = _layout_force(model, plan, set(model.nodes))
    elif strategy == "pipeline":
        positions = _layout_pipeline(model, plan)
    elif strategy == "clustered":
        positions = _layout_clustered(model, plan)
    else:
        raise ValueError(f"Unsupported layout strategy: {strategy}")
    return _normalize_positions(model, positions, margin=100.0)


def _layout_tree(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    roots = _ordered_roots(model, plan.get("root"), set(model.nodes))
    adjacency = model.directed_adjacency()
    layers: list[list[str]] = []
    visited: set[str] = set()
    current = roots
    while current:
        layer = [node for node in current if node not in visited]
        if not layer:
            break
        layers.append(layer)
        visited.update(layer)
        next_nodes: list[str] = []
        for node in layer:
            next_nodes.extend(child for child in adjacency.get(node, []) if child not in visited)
        current = sorted(set(next_nodes), key=_natural_key)
    remaining = [node for node in sorted(model.nodes, key=_natural_key) if node not in visited]
    if remaining:
        layers.append(remaining)
    return _place_layers(layers, model, plan["direction"], plan["spacing"])


def _layout_mindmap(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    spacing = plan["spacing"]
    root = plan.get("root") if plan.get("root") in model.nodes else _choose_root(model)
    adjacency = model.undirected_adjacency()
    neighbors = [node for node in adjacency.get(root, []) if node != root]
    if not neighbors:
        return {root: (0.0, 0.0)}

    left_neighbors = neighbors[1::2]
    right_neighbors = neighbors[0::2]
    cell_w = max(node.width for node in model.nodes.values()) + spacing["layerGap"]
    cell_h = max(node.height for node in model.nodes.values()) + spacing["nodeGap"]
    positions: dict[str, tuple[float, float]] = {root: (0.0, 0.0)}

    def place_branch(start: str, side: int, row: int, seen: set[str]) -> int:
        queue = [(start, 1)]
        while queue:
            node, depth = queue.pop(0)
            if node in seen:
                continue
            seen.add(node)
            positions[node] = (side * depth * cell_w, row * cell_h)
            row += 1
            for child in adjacency.get(node, []):
                if child != root and child not in seen:
                    queue.append((child, depth + 1))
        return row

    seen = {root}
    row = 0
    for branch in left_neighbors:
        row = place_branch(branch, -1, row, seen)
    row = 0
    for branch in right_neighbors:
        row = place_branch(branch, 1, row, seen)
    for node in model.nodes:
        if node not in seen:
            positions[node] = (2 * cell_w, row * cell_h)
            row += 1

    if plan["direction"] in {"left", "up"}:
        positions = {node: (-x, y) for node, (x, y) in positions.items()}
    if plan["direction"] in {"down", "up"}:
        positions = {node: (y, x) for node, (x, y) in positions.items()}
    return positions


def _layout_layered(model: LayoutModel, plan: dict[str, Any], subset: set[str]) -> dict[str, tuple[float, float]]:
    layers = _dag_layers(model, subset)
    layers = _barycenter_sort(model, layers)
    return _place_layers(layers, model, plan["direction"], plan["spacing"])


def _layout_scc_layered(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    sccs = _tarjan(model, set(model.nodes))
    if len(sccs) == len(model.nodes):
        return _layout_layered(model, plan, set(model.nodes))

    comp_for_node = {node: f"component-{index}" for index, comp in enumerate(sccs) for node in comp}
    comp_nodes = {f"component-{index}": comp for index, comp in enumerate(sccs)}
    comp_model_nodes: dict[str, LayoutNode] = {}
    for comp_key, members in comp_nodes.items():
        width = max(model.nodes[node].width for node in members)
        height = sum(model.nodes[node].height for node in members) + plan["spacing"]["nodeGap"] * max(0, len(members) - 1)
        comp_model_nodes[comp_key] = LayoutNode(comp_key, {}, comp_key, width, height)
    comp_edges: list[LayoutEdge] = []
    for edge in model.edges:
        if not edge.directed:
            continue
        source = comp_for_node[edge.source]
        target = comp_for_node[edge.target]
        if source != target:
            comp_edges.append(LayoutEdge(source, target, True))
    comp_model = LayoutModel(comp_model_nodes, comp_edges, {}, {})
    comp_positions = _layout_layered(comp_model, plan, set(comp_model.nodes))

    positions: dict[str, tuple[float, float]] = {}
    for comp_key, members in comp_nodes.items():
        origin_x, origin_y = comp_positions[comp_key]
        y = origin_y
        for node in sorted(members, key=_natural_key):
            positions[node] = (origin_x, y)
            y += model.nodes[node].height + plan["spacing"]["nodeGap"]
    return positions


def _layout_force(model: LayoutModel, plan: dict[str, Any], subset: set[str]) -> dict[str, tuple[float, float]]:
    nodes = sorted(subset, key=_natural_key)
    if len(nodes) == 1:
        return {nodes[0]: (0.0, 0.0)}
    spacing = plan["spacing"]
    max_size = max(max(model.nodes[node].width, model.nodes[node].height) for node in nodes)
    cell = max_size + spacing["minGap"]
    radius = max(cell, cell / max(0.2, 2 * math.sin(math.pi / len(nodes))))
    rng = random.Random(int(plan.get("seed", 7)))
    start_angle = rng.random() * math.pi * 2
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        angle = start_angle + math.pi * 2 * index / len(nodes)
        center_x = math.cos(angle) * radius
        center_y = math.sin(angle) * radius
        positions[node] = (center_x - model.nodes[node].width / 2, center_y - model.nodes[node].height / 2)
    return positions


def _layout_pipeline(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    main_path = [node for node in plan.get("mainPath", []) if node in model.nodes]
    if not main_path:
        main_path = _longest_path(model, set(model.nodes))
    if not main_path:
        return _layout_layered(model, plan, set(model.nodes))
    main_layers = [[node] for node in main_path]
    positions = _place_layers(main_layers, model, plan["direction"], plan["spacing"])
    placed = set(main_path)
    spacing = plan["spacing"]
    adjacency = model.undirected_adjacency()
    horizontal = plan["direction"] in {"right", "left"}
    sign = 1
    for anchor in main_path:
        branches = [node for node in adjacency.get(anchor, []) if node not in placed]
        for index, branch in enumerate(branches, start=1):
            placed.add(branch)
            anchor_x, anchor_y = positions[anchor]
            if horizontal:
                offset = sign * index * (max(model.nodes[anchor].height, model.nodes[branch].height) + spacing["nodeGap"])
                positions[branch] = (anchor_x, anchor_y + offset)
            else:
                offset = sign * index * (max(model.nodes[anchor].width, model.nodes[branch].width) + spacing["nodeGap"])
                positions[branch] = (anchor_x + offset, anchor_y)
            sign *= -1
    remaining = [node for node in sorted(model.nodes, key=_natural_key) if node not in placed]
    if remaining:
        extra = _place_layers([remaining], model, plan["direction"], plan["spacing"])
        bbox = _positions_bbox(model, positions)
        for node, (x, y) in extra.items():
            if horizontal:
                positions[node] = (bbox.right + spacing["layerGap"] + x, y)
            else:
                positions[node] = (x, bbox.bottom + spacing["layerGap"] + y)
    return positions


def _layout_clustered(model: LayoutModel, plan: dict[str, Any]) -> dict[str, tuple[float, float]]:
    clusters = _clusters_from_plan(model, plan.get("clusters"))
    if not clusters:
        return _layout_layered(model, plan, set(model.nodes))

    spacing = plan["spacing"]
    cluster_boxes: list[tuple[str, list[str], dict[str, tuple[float, float]], geom.RectBounds]] = []
    seen: set[str] = set()
    for cluster_id, members in clusters:
        members = [node for node in members if node in model.nodes and node not in seen]
        if not members:
            continue
        seen.update(members)
        member_set = set(members)
        if len(member_set) <= 2:
            local_positions = _place_layers([members], model, plan["direction"], spacing)
        else:
            local_positions = _layout_layered(model, plan, member_set)
        local_positions = _normalize_positions(model, local_positions, margin=0.0)
        bbox = _positions_bbox(model, local_positions)
        box = geom.RectBounds(0, 0, bbox.width + geom.DEFAULT_SECTION_PADDING * 2, bbox.height + geom.DEFAULT_SECTION_PADDING * 2 + geom.DEFAULT_SECTION_TITLE_HEIGHT)
        cluster_boxes.append((cluster_id, members, local_positions, box))

    remaining = [node for node in sorted(model.nodes, key=_natural_key) if node not in seen]
    if remaining:
        local_positions = _layout_layered(model, plan, set(remaining))
        local_positions = _normalize_positions(model, local_positions, margin=0.0)
        bbox = _positions_bbox(model, local_positions)
        cluster_boxes.append(("__ungrouped__", remaining, local_positions, geom.RectBounds(0, 0, bbox.width, bbox.height)))

    positions: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for cluster_id, members, local_positions, box in cluster_boxes:
        if plan["direction"] in {"right", "left"}:
            cluster_origin = (cursor, 0.0)
            cursor += box.width + spacing["clusterGap"]
        else:
            cluster_origin = (0.0, cursor)
            cursor += box.height + spacing["clusterGap"]
        pad_x = geom.DEFAULT_SECTION_PADDING if cluster_id != "__ungrouped__" else 0.0
        pad_y = (geom.DEFAULT_SECTION_PADDING + geom.DEFAULT_SECTION_TITLE_HEIGHT) if cluster_id != "__ungrouped__" else 0.0
        for node in members:
            x, y = local_positions[node]
            positions[node] = (cluster_origin[0] + pad_x + x, cluster_origin[1] + pad_y + y)
    if plan["direction"] in {"left", "up"}:
        if plan["direction"] == "left":
            positions = {node: (-x, y) for node, (x, y) in positions.items()}
        else:
            positions = {node: (x, -y) for node, (x, y) in positions.items()}
    return positions


def _place_layers(
    layers: list[list[str]],
    model: LayoutModel,
    direction: str,
    spacing: dict[str, float],
) -> dict[str, tuple[float, float]]:
    layers = [[node for node in layer if node in model.nodes] for layer in layers]
    layers = [layer for layer in layers if layer]
    if not layers:
        return {}
    horizontal = direction in {"right", "left"}
    layer_major_sizes: list[float] = []
    layer_minor_sizes: list[float] = []
    for layer in layers:
        if horizontal:
            layer_major_sizes.append(max(model.nodes[node].width for node in layer))
            layer_minor_sizes.append(sum(model.nodes[node].height for node in layer) + spacing["nodeGap"] * max(0, len(layer) - 1))
        else:
            layer_major_sizes.append(max(model.nodes[node].height for node in layer))
            layer_minor_sizes.append(sum(model.nodes[node].width for node in layer) + spacing["nodeGap"] * max(0, len(layer) - 1))
    total_minor = max(layer_minor_sizes)
    major_offsets: list[float] = []
    cursor = 0.0
    for size in layer_major_sizes:
        major_offsets.append(cursor)
        cursor += size + spacing["layerGap"]
    if direction in {"left", "up"}:
        max_major = major_offsets[-1]
        major_offsets = [max_major - offset for offset in major_offsets]

    positions: dict[str, tuple[float, float]] = {}
    for layer_index, layer in enumerate(layers):
        minor = (total_minor - layer_minor_sizes[layer_index]) / 2
        for node in layer:
            if horizontal:
                x = major_offsets[layer_index]
                y = minor
                positions[node] = (x, y)
                minor += model.nodes[node].height + spacing["nodeGap"]
            else:
                x = minor
                y = major_offsets[layer_index]
                positions[node] = (x, y)
                minor += model.nodes[node].width + spacing["nodeGap"]
    return positions


def _dag_layers(model: LayoutModel, subset: set[str]) -> list[list[str]]:
    adjacency = model.directed_adjacency(subset)
    indegree = {node: 0 for node in subset}
    for source, targets in adjacency.items():
        for target in targets:
            indegree[target] += 1
    queue = sorted([node for node, count in indegree.items() if count == 0], key=_natural_key)
    topo: list[str] = []
    while queue:
        node = queue.pop(0)
        topo.append(node)
        for target in adjacency.get(node, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
                queue.sort(key=_natural_key)
    for node in sorted(subset, key=_natural_key):
        if node not in topo:
            topo.append(node)

    ranks = {node: 0 for node in subset}
    for node in topo:
        for target in adjacency.get(node, []):
            ranks[target] = max(ranks[target], ranks[node] + 1)
    max_rank = max(ranks.values(), default=0)
    return [[node for node in topo if ranks[node] == rank] for rank in range(max_rank + 1)]


def _barycenter_sort(model: LayoutModel, layers: list[list[str]]) -> list[list[str]]:
    if len(layers) < 3:
        return [sorted(layer, key=_natural_key) for layer in layers]
    adjacency = model.directed_adjacency()
    predecessors: dict[str, list[str]] = {node: [] for node in model.nodes}
    for source, targets in adjacency.items():
        for target in targets:
            predecessors.setdefault(target, []).append(source)
    ordered = [sorted(layer, key=_natural_key) for layer in layers]
    for _ in range(3):
        index_by_node = {node: index for layer in ordered for index, node in enumerate(layer)}
        for layer_index in range(1, len(ordered)):
            ordered[layer_index].sort(key=lambda node: _barycenter(predecessors.get(node, []), index_by_node, node))
    return ordered


def _barycenter(predecessors: list[str], index_by_node: dict[str, int], fallback: str) -> tuple[float, str]:
    indexes = [index_by_node[node] for node in predecessors if node in index_by_node]
    if not indexes:
        return (math.inf, fallback)
    return (sum(indexes) / len(indexes), fallback)


def _tarjan(model: LayoutModel, subset: set[str]) -> list[list[str]]:
    adjacency = model.directed_adjacency(subset)
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency.get(node, []):
            if target not in indexes:
                strongconnect(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            components.append(sorted(component, key=_natural_key))

    for node in sorted(subset, key=_natural_key):
        if node not in indexes:
            strongconnect(node)
    return components


def _components(model: LayoutModel) -> list[list[str]]:
    adjacency = model.undirected_adjacency()
    seen: set[str] = set()
    components: list[list[str]] = []
    for node in sorted(model.nodes, key=_natural_key):
        if node in seen:
            continue
        queue = [node]
        seen.add(node)
        component: list[str] = []
        while queue:
            current = queue.pop(0)
            component.append(current)
            for neighbor in adjacency.get(current, []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def _choose_root(model: LayoutModel) -> str | None:
    if not model.nodes:
        return None
    indegree = {key: 0 for key in model.nodes}
    outdegree = {key: 0 for key in model.nodes}
    for edge in model.edges:
        if edge.directed:
            indegree[edge.target] += 1
            outdegree[edge.source] += 1
        else:
            outdegree[edge.source] += 1
            outdegree[edge.target] += 1
    candidates = sorted(model.nodes, key=lambda node: (indegree[node], -outdegree[node], _natural_key(node)))
    return candidates[0]


def _ordered_roots(model: LayoutModel, root: str | None, subset: set[str]) -> list[str]:
    if root in subset:
        roots = [root]
    else:
        indegree = {key: 0 for key in subset}
        for edge in model.edges:
            if edge.directed and edge.source in subset and edge.target in subset:
                indegree[edge.target] += 1
        roots = sorted([node for node, count in indegree.items() if count == 0], key=_natural_key)
    roots.extend(node for node in sorted(subset, key=_natural_key) if node not in roots)
    return roots


def _longest_path(model: LayoutModel, subset: set[str]) -> list[str]:
    if not subset:
        return []
    layers = _dag_layers(model, subset)
    order = [node for layer in layers for node in layer]
    adjacency = model.directed_adjacency(subset)
    best_path: dict[str, list[str]] = {node: [node] for node in subset}
    for node in order:
        for target in adjacency.get(node, []):
            candidate = best_path[node] + [target]
            if len(candidate) > len(best_path.get(target, [])):
                best_path[target] = candidate
    return max(best_path.values(), key=lambda path: (len(path), [_natural_key(item) for item in path]))


def _plan_clusters(model: LayoutModel) -> list[dict[str, Any]]:
    return [
        {"id": cluster_id, "label": model.section_labels.get(cluster_id, cluster_id), "nodes": sorted(nodes, key=_natural_key)}
        for cluster_id, nodes in sorted(model.sections.items(), key=lambda item: _natural_key(item[0]))
    ]


def _clusters_from_plan(model: LayoutModel, clusters: Any) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    if isinstance(clusters, list):
        for index, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                continue
            nodes = [str(node) for node in cluster.get("nodes", []) if str(node) in model.nodes]
            if nodes:
                result.append((str(cluster.get("id") or cluster.get("label") or f"cluster-{index}"), nodes))
    if result:
        return result
    return [(cluster_id, sorted(nodes, key=_natural_key)) for cluster_id, nodes in sorted(model.sections.items(), key=lambda item: _natural_key(item[0]))]


def _positions_bbox(model: LayoutModel, positions: dict[str, tuple[float, float]]) -> geom.RectBounds:
    left = min(x for x, _ in positions.values())
    top = min(y for _, y in positions.values())
    right = max(x + model.nodes[node].width for node, (x, _) in positions.items())
    bottom = max(y + model.nodes[node].height for node, (_, y) in positions.items())
    return geom.RectBounds(left, top, right - left, bottom - top)


def _normalize_positions(
    model: LayoutModel,
    positions: dict[str, tuple[float, float]],
    *,
    margin: float,
) -> dict[str, tuple[float, float]]:
    if not positions:
        return {}
    bbox = _positions_bbox(model, positions)
    return {
        node: (round(x - bbox.left + margin, 2), round(y - bbox.top + margin, 2))
        for node, (x, y) in positions.items()
    }


def _write_stage_positions(model: LayoutModel, positions: dict[str, tuple[float, float]]) -> None:
    for node_key, (x, y) in positions.items():
        node = model.nodes[node_key]
        rect = geom.get_primary_rectangle(node.obj.get("collisionBox"))
        if rect is None:
            continue
        node.obj["collisionBox"] = geom.collision_box(x, y, rect.width, rect.height)


def _write_spec_positions(model: LayoutModel, positions: dict[str, tuple[float, float]]) -> None:
    for node_key, (x, y) in positions.items():
        obj = model.nodes[node_key].obj
        obj["x"] = round(x, 2)
        obj["y"] = round(y, 2)
        obj.setdefault("width", round(model.nodes[node_key].width, 2))
        obj.setdefault("height", round(model.nodes[node_key].height, 2))


def _write_stage_edge_rates(model: LayoutModel, positions: dict[str, tuple[float, float]]) -> None:
    for edge in model.edges:
        if not edge.directed or edge.obj is None or edge.obj.get("_") != "LineEdge":
            continue
        source_rate, target_rate = _edge_rates(model, positions, edge.source, edge.target)
        edge.obj["sourceRectangleRate"] = geom.vector(*source_rate)
        edge.obj["targetRectangleRate"] = geom.vector(*target_rate)


def _write_spec_edge_rates(model: LayoutModel, positions: dict[str, tuple[float, float]]) -> None:
    for edge in model.edges:
        if not edge.directed or edge.obj is None or edge.obj.get("type") != "LineEdge":
            continue
        source_rate, target_rate = _edge_rates(model, positions, edge.source, edge.target)
        edge.obj["sourceRate"] = [source_rate[0], source_rate[1]]
        edge.obj["targetRate"] = [target_rate[0], target_rate[1]]


def _edge_rates(
    model: LayoutModel,
    positions: dict[str, tuple[float, float]],
    source: str,
    target: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    source_x, source_y = positions[source]
    target_x, target_y = positions[target]
    source_node = model.nodes[source]
    target_node = model.nodes[target]
    source_center = (source_x + source_node.width / 2, source_y + source_node.height / 2)
    target_center = (target_x + target_node.width / 2, target_y + target_node.height / 2)
    dx = target_center[0] - source_center[0]
    dy = target_center[1] - source_center[1]
    if abs(dx) >= abs(dy):
        return ((1.0, 0.5), (0.0, 0.5)) if dx >= 0 else ((0.0, 0.5), (1.0, 0.5))
    return ((0.5, 1.0), (0.5, 0.0)) if dy >= 0 else ((0.5, 0.0), (0.5, 1.0))


def _layout_report(
    model: LayoutModel,
    plan: dict[str, Any],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "node_count": len(model.nodes),
        "edge_count": len(model.edges),
        "layoutPlan": plan,
        "bounds": _rect_to_report(_positions_bbox(model, positions)) if positions else None,
    }


def _rect_to_report(rect: geom.RectBounds) -> dict[str, Any]:
    return {
        "x": _rounded(rect.x),
        "y": _rounded(rect.y),
        "width": _rounded(rect.width),
        "height": _rounded(rect.height),
    }


def _spec_size(item: dict[str, Any]) -> tuple[float, float]:
    if isinstance(item.get("rect"), dict):
        rect = item["rect"]
        return float(rect.get("width", 200)), float(rect.get("height", 76))
    return float(item.get("width", 200)), float(item.get("height", 76))


def _spec_label(item: dict[str, Any]) -> str:
    if item.get("type") == "TextNode":
        return item.get("text", "")
    if item.get("type") == "UrlNode":
        return item.get("title", "")
    return item.get("text", "") or item.get("title", "") or item.get("id", "")


def _stage_label(item: dict[str, Any]) -> str:
    if item.get("_") == "TextNode":
        return item.get("text", "")
    if item.get("_") == "UrlNode":
        return item.get("title", "")
    return item.get("text", "") or item.get("title", "") or item.get("uuid", "")


def _natural_key(value: str) -> tuple[tuple[int, Any], ...]:
    parts = str(value).replace("/", " / ").replace("-", " - ").split()
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def _rounded(value: float) -> int | float:
    return int(value) if float(value).is_integer() else round(float(value), 2)
