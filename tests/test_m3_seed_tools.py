from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from donna.glue.test_data import search_context, seed_context_db
from donna.glue.tools.calendar import create_event, search_events, seed_calendar_db


class M3SeedToolsTest(unittest.TestCase):
    def test_seed_context_db_returns_case_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "context.sqlite"
            seed_context_db(db_path)

            hits = search_context(db_path, "Maria")

        self.assertTrue(hits)
        self.assertEqual(hits[0].case_id, "case-2026-001")

    def test_calendar_create_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "calendar.sqlite"
            seed_calendar_db(db_path)
            create_event(
                db_path,
                title="Andre Patel records call",
                start="2026-06-20T09:00:00-07:00",
                end="2026-06-20T09:30:00-07:00",
                attendee="Andre Patel",
                case_id="case-2026-002",
                notes="Check urgent care records.",
            )

            events = search_events(db_path, case_id="case-2026-002")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].attendee, "Andre Patel")


if __name__ == "__main__":
    unittest.main()
