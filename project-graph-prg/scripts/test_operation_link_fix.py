from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from prg_tools import (
    auto_fix_operation_block_links,
    find_spacing_violations,
    generate_prg_from_spec,
    read_prg,
    validate_operation_block_links,
    write_prg,
)


class OperationLinkFixTests(unittest.TestCase):
    def test_auto_fix_direct_operation_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spec = {
                "metadata": {"version": "2.2.0"},
                "objects": [
                    {"id": "op-a", "type": "TextNode", "text": "#ADD#", "x": 0, "y": 0, "width": 140, "height": 76},
                    {"id": "op-b", "type": "TextNode", "text": "#DIV#", "x": 260, "y": 0, "width": 140, "height": 76},
                    {"id": "edge-a", "type": "LineEdge", "from": "op-a", "to": "op-b", "text": ""},
                ],
            }
            stage, attachments, metadata, tags, references = generate_prg_from_spec(spec)
            output = temp_path / "ops.prg"
            write_prg(output, stage=stage, attachments=attachments, metadata=metadata, tags=tags, references=references)

            document = read_prg(output)
            before = validate_operation_block_links(document)
            after = auto_fix_operation_block_links(document)
            write_prg(output, stage=document.stage, metadata=document.metadata, tags=document.tags, references=document.references, attachments=document.attachments)
            reloaded = read_prg(output)
            final = validate_operation_block_links(reloaded)

            self.assertFalse(before["ok"])
            self.assertEqual(before["invalid_link_count"], 1)
            self.assertEqual(after["fix_count"], 1)
            self.assertTrue(final["ok"])
            self.assertEqual(final["valid_link_count"], 1)
            self.assertEqual(final["valid_links"][0]["intermediates"][0]["label"], "")

    def test_spacing_violation_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spec = {
                "metadata": {"version": "2.2.0"},
                "objects": [
                    {"id": "a", "type": "TextNode", "text": "A", "x": 0, "y": 0, "width": 100, "height": 80},
                    {"id": "b", "type": "TextNode", "text": "B", "x": 220, "y": 0, "width": 100, "height": 80},
                ],
            }
            stage, attachments, metadata, tags, references = generate_prg_from_spec(spec)
            output = temp_path / "spacing.prg"
            write_prg(output, stage=stage, attachments=attachments, metadata=metadata, tags=tags, references=references)

            result = find_spacing_violations(read_prg(output), include_sections=False, min_gap=300)
            self.assertFalse(result["ok"])
            self.assertEqual(result["violation_count"], 1)
            self.assertEqual(result["violations"][0]["actual_gap"], 120)

    def test_auto_fix_non_blank_intermediate_register(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spec = {
                "metadata": {"version": "2.2.0"},
                "objects": [
                    {"id": "op-a", "type": "TextNode", "text": "#ADD#", "x": 0, "y": 0, "width": 140, "height": 76},
                    {"id": "mid", "type": "TextNode", "text": "NOT_BLANK", "x": 180, "y": 0, "width": 140, "height": 76},
                    {"id": "op-b", "type": "TextNode", "text": "#DIV#", "x": 360, "y": 0, "width": 140, "height": 76},
                    {"id": "e1", "type": "LineEdge", "from": "op-a", "to": "mid", "text": ""},
                    {"id": "e2", "type": "LineEdge", "from": "mid", "to": "op-b", "text": ""},
                ],
            }
            stage, attachments, metadata, tags, references = generate_prg_from_spec(spec)
            output = temp_path / "nonblank.prg"
            write_prg(output, stage=stage, attachments=attachments, metadata=metadata, tags=tags, references=references)

            document = read_prg(output)
            before = validate_operation_block_links(document)
            after = auto_fix_operation_block_links(document)
            reloaded = read_prg(write_prg(output, stage=document.stage, metadata=document.metadata, tags=document.tags, references=document.references, attachments=document.attachments))
            final = validate_operation_block_links(reloaded)

            self.assertFalse(before["ok"])
            self.assertEqual(after["fix_count"], 1)
            self.assertEqual(after["fixes"][0]["type"], "blank_existing_register")
            self.assertTrue(final["ok"])
            self.assertEqual(final["valid_links"][0]["intermediates"][0]["label"], "")


if __name__ == "__main__":
    unittest.main()
