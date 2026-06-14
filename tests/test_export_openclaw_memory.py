from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from donna.glue.export_openclaw_memory import export_openclaw_memory
from donna.glue.test_data import seed_context_db


class ExportOpenClawMemoryTest(unittest.TestCase):
    def test_export_writes_memory_md_and_case_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "context.sqlite"
            out_dir = Path(tmp_dir) / "workspace"
            seed_context_db(db_path)

            paths = export_openclaw_memory(db_path, out_dir)

            self.assertTrue((out_dir / "MEMORY.md").exists())
            self.assertTrue((out_dir / "memory" / "cases" / "case-2026-001.md").exists())
            case_text = (out_dir / "memory" / "cases" / "case-2026-001.md").read_text()
            self.assertIn("Maria Lopez", case_text)
            self.assertGreaterEqual(len(paths), 3)


if __name__ == "__main__":
    unittest.main()
