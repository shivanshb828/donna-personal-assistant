from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from donna.glue.export_openclaw_memory import export_openclaw_memory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export M3 context SQLite into OpenClaw MEMORY.md + memory/*.md"
    )
    parser.add_argument(
        "--context-db",
        type=Path,
        default=Path("data/donna_m3_context.sqlite"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("openclaw/workspace"),
        help="OpenClaw agent workspace directory",
    )
    args = parser.parse_args()

    paths = export_openclaw_memory(args.context_db, args.output)
    print(f"exported {len(paths)} files to {args.output}")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
