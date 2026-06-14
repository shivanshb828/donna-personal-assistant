"""Export M3 seed SQLite rows into OpenClaw memory markdown files."""

from __future__ import annotations

from pathlib import Path
import sqlite3


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _case_page(case: sqlite3.Row, client_name: str, facts: list[sqlite3.Row], notes: list[sqlite3.Row], memories: list[sqlite3.Row]) -> str:
    lines = [
        f"# {client_name} — {case['id']}",
        "",
        "## Compiled truth",
        "",
        f"- **Type:** {case['case_type']}",
        f"- **Status:** {case['status']}",
        f"- **Incident:** {case['incident_date']} at {case['incident_location']}",
        f"- **Injuries:** {case['injuries']}",
        f"- **Treatment:** {case['treatment_received']}",
        f"- **Jurisdiction:** {case['state_jurisdiction']} (SOL {case['statute_of_limitations_date']})",
        "",
    ]
    if facts:
        lines.append("## Facts")
        lines.append("")
        for fact in facts:
            verified = "verified" if fact["verified"] else "unverified"
            lines.append(f"- **{fact['label']}** ({verified}): {fact['value']}")
        lines.append("")

    lines.extend(["---", "", "## Timeline", ""])
    for note in notes:
        lines.append(f"- **{note['note_type']}:** {note['content']}")
    for memory in memories:
        lines.append(f"- **{memory['kind']}:** {memory['content']}")
    lines.append("")
    return "\n".join(lines)


def export_openclaw_memory(context_db: Path, output_dir: Path) -> list[Path]:
    """Write MEMORY.md and memory/**/*.md from the M3 context SQLite DB."""
    output_dir.mkdir(parents=True, exist_ok=True)
    memory_dir = output_dir / "memory"
    cases_dir = memory_dir / "cases"
    clients_dir = memory_dir / "clients"
    cases_dir.mkdir(parents=True, exist_ok=True)
    clients_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    with _connect(context_db) as conn:
        clients = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
        cases = conn.execute(
            """
            SELECT c.*, cl.name AS client_name
            FROM cases c
            JOIN clients cl ON cl.id = c.client_id
            ORDER BY c.id
            """
        ).fetchall()

        for client in clients:
            path = clients_dir / f"{client['id'].replace('client-', '')}.md"
            path.write_text(
                "\n".join(
                    [
                        f"# {client['name']}",
                        "",
                        f"- Phone: {client['phone']}",
                        f"- Email: {client['email']}",
                        f"- Consent (recording / AI / storage): {client['consent_recording']} / "
                        f"{client['consent_ai_disclosure']} / {client['consent_data_storage']}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            written.append(path)

        summaries: list[str] = []
        for case in cases:
            facts = conn.execute(
                "SELECT label, value, verified FROM facts WHERE case_id = ? ORDER BY label",
                (case["id"],),
            ).fetchall()
            notes = conn.execute(
                "SELECT note_type, content FROM case_notes WHERE case_id = ? ORDER BY id",
                (case["id"],),
            ).fetchall()
            memories = conn.execute(
                "SELECT kind, content FROM memories WHERE case_id = ? ORDER BY id",
                (case["id"],),
            ).fetchall()

            case_path = cases_dir / f"{case['id']}.md"
            case_path.write_text(
                _case_page(case, case["client_name"], facts, notes, memories),
                encoding="utf-8",
            )
            written.append(case_path)
            summaries.append(f"- [[memory/cases/{case['id']}]] — {case['client_name']}, {case['status']}")

    memory_md = output_dir / "MEMORY.md"
    memory_md.write_text(
        "\n".join(
            [
                "# Donna — active case index",
                "",
                "Auto-exported from M3 SQLite seed data. OpenClaw indexes this file plus",
                "`memory/**/*.md` into `~/.openclaw/memory/donna.sqlite`.",
                "",
                "## Active matters",
                "",
                *summaries,
                "",
            ]
        ),
        encoding="utf-8",
    )
    written.insert(0, memory_md)
    return written
