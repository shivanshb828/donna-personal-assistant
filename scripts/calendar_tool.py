from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from donna.glue.tools.calendar import create_event, search_events


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite-backed calendar tool for M2 testing.")
    parser.add_argument("action", choices=["create_event", "search_events"])
    parser.add_argument("--db", type=Path, default=Path("data/donna_m3_calendar.sqlite"))
    parser.add_argument("--input", help="JSON object. Defaults to stdin when omitted.")
    args = parser.parse_args()

    payload = json.loads(args.input if args.input is not None else sys.stdin.read())

    if args.action == "create_event":
        event = create_event(args.db, **payload)
        print(json.dumps({"ok": True, "event": asdict(event)}, indent=2))
        return

    events = search_events(args.db, **payload)
    print(json.dumps({"ok": True, "events": [asdict(event) for event in events]}, indent=2))


if __name__ == "__main__":
    main()
