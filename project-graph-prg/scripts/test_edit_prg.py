from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prg_tools import edit_document, generate_prg_from_spec, read_prg, validate_document, write_prg


class EditPrgTests(unittest.TestCase):
    def _write_base_document(self, temp_path: Path) -> Path:
        spec = {
            "metadata": {"version": "2.2.0"},
            "objects": [
                {"id": "a", "type": "TextNode", "text": "A", "x": 0, "y": 0, "width": 120, "height": 76},
                {"id": "b", "type": "TextNode", "text": "B", "x": 240, "y": 0, "width": 120, "height": 76},
                {"id": "c", "type": "TextNode", "text": "C", "x": 480, "y": 0, "width": 120, "height": 76},
                {"id": "edge-ab", "type": "LineEdge", "from": "a", "to": "b", "text": "ab"},
                {"id": "section", "type": "Section", "text": "Group", "children": ["a", "b"]},
            ],
        }
        stage, attachments, metadata, tags, references = generate_prg_from_spec(spec)
        output = temp_path / "base.prg"
        write_prg(output, stage=stage, attachments=attachments, metadata=metadata, tags=tags, references=references)
        return output

    def test_update_and_append_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._write_base_document(Path(temp_dir))
            document = read_prg(output)
            result = edit_document(
                document,
                {
                    "operations": [
                        {"op": "update", "target": {"type": "TextNode", "text": "A"}, "set": {"text": "输入数据", "details": "第一行"}},
                        {"op": "append_details", "target": {"type": "TextNode", "text": "输入数据"}, "value": "第二行"},
                    ]
                },
            )
            write_prg(output, stage=document.stage, metadata=document.metadata, tags=document.tags, references=document.references, attachments=document.attachments)
            reloaded = read_prg(output)
            node = reloaded.stage[0]

            self.assertTrue(result["ok"])
            self.assertEqual(node["text"], "输入数据")
            self.assertEqual(node["details"][0]["children"][0]["text"], "第一行")
            self.assertEqual(node["details"][1]["children"][0]["text"], "第二行")

    def test_insert_node_between_existing_edge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._write_base_document(Path(temp_dir))
            document = read_prg(output)
            result = edit_document(
                document,
                {
                    "operations": [
                        {
                            "op": "insert_node_between",
                            "from": {"text": "A"},
                            "to": {"text": "B"},
                            "node": {"text": "寄存器", "width": 100, "height": 60},
                        }
                    ]
                },
            )

            self.assertTrue(result["ok"])
            labels = [item.get("text", "") for item in document.stage if isinstance(item, dict) and item.get("_") == "TextNode"]
            self.assertIn("寄存器", labels)
            edge_count = len([item for item in document.stage if isinstance(item, dict) and item.get("_") == "LineEdge"])
            self.assertEqual(edge_count, 2)

    def test_delete_cascades_line_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._write_base_document(Path(temp_dir))
            document = read_prg(output)
            result = edit_document(
                document,
                {"operations": [{"op": "delete", "target": {"text": "B"}, "cascade": True}]},
            )

            self.assertTrue(result["ok"])
            validation = validate_document(document)
            self.assertTrue(validation["ok"])
            labels = [item.get("text", "") for item in document.stage if isinstance(item, dict) and item.get("_") == "TextNode"]
            self.assertNotIn("B", labels)
            edge_count = len([item for item in document.stage if isinstance(item, dict) and item.get("_") == "LineEdge"])
            self.assertEqual(edge_count, 0)
            section = next(item for item in document.stage if isinstance(item, dict) and item.get("_") == "Section")
            self.assertEqual(len(section["children"]), 1)

    def test_add_edge_and_section_membership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._write_base_document(Path(temp_dir))
            document = read_prg(output)
            result = edit_document(
                document,
                {
                    "operations": [
                        {"op": "add_edge", "from": {"text": "B"}, "to": {"text": "C"}, "text": "bc"},
                        {"op": "add_to_section", "section": {"type": "Section", "text": "Group"}, "targets": [{"text": "C"}]},
                    ]
                },
            )

            self.assertTrue(result["ok"])
            edge_labels = [item.get("text", "") for item in document.stage if isinstance(item, dict) and item.get("_") == "LineEdge"]
            self.assertIn("bc", edge_labels)
            section = next(item for item in document.stage if isinstance(item, dict) and item.get("_") == "Section")
            self.assertEqual(len(section["children"]), 3)


if __name__ == "__main__":
    unittest.main()
