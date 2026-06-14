from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from donna.glue.test_data import seed_context_db
from donna.glue.tools.calendar import seed_calendar_db


DEFAULT_CONTEXT_DB = Path("data/donna_m3_context.sqlite")
DEFAULT_CALENDAR_DB = Path("data/donna_m3_calendar.sqlite")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create seed SQLite databases for M2 testing.")
    parser.add_argument("--context-db", type=Path, default=DEFAULT_CONTEXT_DB)
    parser.add_argument("--calendar-db", type=Path, default=DEFAULT_CALENDAR_DB)
    args = parser.parse_args()

    seed_context_db(args.context_db)
    seed_calendar_db(args.calendar_db)

    print(f"context_db={args.context_db}")
    print(f"calendar_db={args.calendar_db}")


if __name__ == "__main__":
    main()
