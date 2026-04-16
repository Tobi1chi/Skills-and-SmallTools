from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import geometry_prg_tools as geom
import graph_layout


SCRIPT_DIR = Path(__file__).resolve().parent
CLI = SCRIPT_DIR / "prg_cli.py"


class GraphLayoutTests(unittest.TestCase):
    def test_layout_strategies_have_clearance(self) -> None:
        cases = [
            ("tree", self._tree_spec()),
            ("mindmap", self._mindmap_spec()),
            ("dag", self._dag_spec()),
            ("cyclic_dependency", self._cycle_spec()),
            ("dense_network", self._dense_spec()),
            ("pipeline", self._pipeline_spec()),
            ("clustered", self._clustered_spec()),
        ]
        for graph_type, spec in cases:
            with self.subTest(graph_type=graph_type):
                document = self._document(spec)
                changed = any(self._rect(item).x != 0 or self._rect(item).y != 0 for item in self._text_nodes(document.stage))
                self.assertTrue(changed)
                overlap = geom.find_overlaps(document, include_sections=True, min_gap=200)
                self.assertTrue(overlap["ok"], overlap)

    def test_main_direction_for_layered_and_pipeline(self) -> None:
        dag_document = self._document(self._dag_spec())
        self.assertLess(self._center_x(dag_document.stage, "A"), self._center_x(dag_document.stage, "D"))

        pipeline_document = self._document(self._pipeline_spec())
        xs = [self._center_x(pipeline_document.stage, label) for label in ["Ingest", "Transform", "Serve"]]
        self.assertEqual(xs, sorted(xs))

    def test_classify_recommends_plan(self) -> None:
        result = graph_layout.classify_spec(self._cycle_spec())
        self.assertTrue(result["metrics"]["hasCycles"])
        self.assertEqual(result["graphIntent"]["primaryType"], "cyclic_dependency")
        self.assertEqual(result["layoutPlan"]["strategy"], "scc-layered")

    def test_cli_classify_generate_off_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spec_path = temp_path / "spec.json"
            auto_path = temp_path / "auto.prg"
            off_path = temp_path / "off.prg"
            relayout_path = temp_path / "relayout.prg"
            spec_path.write_text(json.dumps(self._dag_spec(), ensure_ascii=False), encoding="utf-8")

            classify = subprocess.run(
                [sys.executable, str(CLI), "classify", str(spec_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(classify.stdout)["layoutPlan"]["strategy"], "layered")

            subprocess.run([sys.executable, str(CLI), "generate", str(spec_path), str(auto_path)], check=True, capture_output=True, text=True)
            subprocess.run(
                [sys.executable, str(CLI), "generate", str(spec_path), str(off_path), "--layout", "off"],
                check=True,
                capture_output=True,
                text=True,
            )
            off_document = geom.read_prg(off_path)
            off_rects = [self._rect(item) for item in self._text_nodes(off_document.stage)]
            self.assertTrue(all(rect.x == 0 and rect.y == 0 for rect in off_rects))

            subprocess.run(
                [sys.executable, str(CLI), "layout", str(off_path), str(relayout_path), "--strategy", "layered", "--direction", "right"],
                check=True,
                capture_output=True,
                text=True,
            )
            relayout_document = geom.read_prg(relayout_path)
            overlap = geom.find_overlaps(relayout_document, include_sections=True, min_gap=200)
            self.assertTrue(overlap["ok"], overlap)

    def _document(self, spec: dict) -> geom.PrgDocument:
        stage, attachments, metadata, tags, references = geom.generate_prg_from_spec(spec)
        return geom.PrgDocument(Path("<test>"), stage, metadata, tags, references, attachments)

    def _text_nodes(self, stage: list) -> list[dict]:
        return [item for item in stage if isinstance(item, dict) and item.get("_") == "TextNode"]

    def _rect(self, item: dict) -> geom.RectBounds:
        rect = geom.get_primary_rectangle(item.get("collisionBox"))
        self.assertIsNotNone(rect)
        return rect

    def _center_x(self, stage: list, label: str) -> float:
        node = next(item for item in stage if isinstance(item, dict) and item.get("_") == "TextNode" and item.get("text") == label)
        rect = self._rect(node)
        return rect.center_x

    def _base_nodes(self, labels: list[str]) -> list[dict]:
        return [
            {"id": label.lower(), "type": "TextNode", "text": label, "x": 0, "y": 0, "width": 120, "height": 76}
            for label in labels
        ]

    def _tree_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "tree", "confidence": 0.9},
            "layoutPlan": {"strategy": "tree", "direction": "right", "root": "root"},
            "objects": [
                {"id": "root", "type": "TextNode", "text": "Root", "x": 0, "y": 0, "width": 120, "height": 76},
                {"id": "a", "type": "TextNode", "text": "A", "x": 0, "y": 0, "width": 120, "height": 76},
                {"id": "b", "type": "TextNode", "text": "B", "x": 0, "y": 0, "width": 120, "height": 76},
                {"id": "e1", "type": "LineEdge", "from": "root", "to": "a"},
                {"id": "e2", "type": "LineEdge", "from": "root", "to": "b"},
            ],
        }

    def _mindmap_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "mindmap", "confidence": 0.9},
            "layoutPlan": {"strategy": "mindmap", "direction": "right", "root": "center"},
            "objects": [
                {"id": "center", "type": "TextNode", "text": "Center", "x": 0, "y": 0, "width": 150, "height": 76},
                *self._base_nodes(["Alpha", "Beta", "Gamma", "Delta"]),
                {"id": "e1", "type": "LineEdge", "from": "center", "to": "alpha"},
                {"id": "e2", "type": "LineEdge", "from": "center", "to": "beta"},
                {"id": "e3", "type": "LineEdge", "from": "center", "to": "gamma"},
                {"id": "e4", "type": "LineEdge", "from": "center", "to": "delta"},
            ],
        }

    def _dag_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "dag", "confidence": 0.9},
            "layoutPlan": {"strategy": "layered", "direction": "right"},
            "objects": [
                *self._base_nodes(["A", "B", "C", "D"]),
                {"id": "e1", "type": "LineEdge", "from": "a", "to": "b"},
                {"id": "e2", "type": "LineEdge", "from": "a", "to": "c"},
                {"id": "e3", "type": "LineEdge", "from": "b", "to": "d"},
                {"id": "e4", "type": "LineEdge", "from": "c", "to": "d"},
            ],
        }

    def _cycle_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "cyclic_dependency", "confidence": 0.9},
            "layoutPlan": {"strategy": "scc-layered", "direction": "right"},
            "objects": [
                *self._base_nodes(["A", "B", "C"]),
                {"id": "e1", "type": "LineEdge", "from": "a", "to": "b"},
                {"id": "e2", "type": "LineEdge", "from": "b", "to": "c"},
                {"id": "e3", "type": "LineEdge", "from": "c", "to": "a"},
            ],
        }

    def _dense_spec(self) -> dict:
        nodes = self._base_nodes(["A", "B", "C", "D", "E"])
        edges = [
            {"id": f"e{index}", "type": "LineEdge", "from": source, "to": target}
            for index, (source, target) in enumerate(
                [("a", "b"), ("a", "c"), ("a", "d"), ("a", "e"), ("b", "c"), ("c", "d"), ("d", "e")]
            )
        ]
        return {
            "graphIntent": {"primaryType": "dense_network", "confidence": 0.9},
            "layoutPlan": {"strategy": "force", "direction": "right", "seed": 7},
            "objects": [*nodes, *edges],
        }

    def _pipeline_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "pipeline", "confidence": 0.9},
            "layoutPlan": {"strategy": "pipeline", "direction": "right", "mainPath": ["ingest", "transform", "serve"]},
            "objects": [
                *self._base_nodes(["Ingest", "Transform", "Serve", "Audit"]),
                {"id": "e1", "type": "LineEdge", "from": "ingest", "to": "transform"},
                {"id": "e2", "type": "LineEdge", "from": "transform", "to": "serve"},
                {"id": "e3", "type": "LineEdge", "from": "transform", "to": "audit"},
            ],
        }

    def _clustered_spec(self) -> dict:
        return {
            "graphIntent": {"primaryType": "clustered", "confidence": 0.9},
            "layoutPlan": {
                "strategy": "clustered",
                "direction": "right",
                "clusters": [
                    {"id": "left", "nodes": ["a", "b"]},
                    {"id": "right", "nodes": ["c", "d"]},
                ],
            },
            "objects": [
                *self._base_nodes(["A", "B", "C", "D"]),
                {"id": "e1", "type": "LineEdge", "from": "a", "to": "b"},
                {"id": "e2", "type": "LineEdge", "from": "c", "to": "d"},
                {"id": "e3", "type": "LineEdge", "from": "b", "to": "c"},
                {"id": "s1", "type": "Section", "text": "Left", "children": ["a", "b"]},
                {"id": "s2", "type": "Section", "text": "Right", "children": ["c", "d"]},
            ],
        }


if __name__ == "__main__":
    unittest.main()
