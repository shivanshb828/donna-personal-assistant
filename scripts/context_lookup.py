from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from donna.glue.test_data import search_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the seed M3 context database.")
    parser.add_argument("query")
    parser.add_argument("--db", type=Path, default=Path("data/donna_m3_context.sqlite"))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    hits = search_context(args.db, args.query, args.limit)
    print(json.dumps({"ok": True, "hits": [asdict(hit) for hit in hits]}, indent=2))


if __name__ == "__main__":
    main()
