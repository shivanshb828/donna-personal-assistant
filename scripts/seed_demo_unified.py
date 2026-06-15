"""
Unified demo seed — 2 client profiles + firm profile.
Wipes and reseeds context DB and calendar DB.

Run: python scripts/seed_demo_unified.py
"""

import sqlite3
import sys
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from donna.glue.test_data import connect, init_context_db
from donna.glue.tools.calendar import create_event, init_calendar_db
from donna.telephony.config import TelephonyConfig


def _wipe_context(db_path: Path) -> None:
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in ("memories", "documents", "case_notes", "facts", "cases", "clients", "metadata"):
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        conn.execute("PRAGMA foreign_keys = ON")


def _seed_context(db_path: Path) -> None:
    _wipe_context(db_path)
    init_context_db(db_path)

    with connect(db_path) as conn:

        # ── Client 1: James Carter — Auto Accident ────────────────────────────
        conn.execute(
            "INSERT INTO clients (id, name, phone, email, consent_recording, consent_ai_disclosure, consent_data_storage)"
            " VALUES (?, ?, ?, ?, 1, 1, 1)",
            ("client-james-carter", "James Carter", "+14085550181", "james.carter@example.com"),
        )
        conn.execute(
            """INSERT INTO cases
               (id, client_id, case_type, incident_date, incident_location,
                at_fault_party, injuries, treatment_received, witnesses, status,
                statute_of_limitations_date, state_jurisdiction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "case-2026-jc", "client-james-carter", "auto_accident", "2026-06-02",
                "Intersection of First St and Market Ave, San Jose, CA",
                "Robert Hall — ran red light; insured by Progressive policy #4421-A",
                "Neck pain, lower back pain, concussion symptoms",
                "Urgent care same day, muscle relaxers prescribed, MRI ordered",
                "Rachel Kim (bystander, contact provided)",
                "intake", "2028-06-02", "CA",
            ),
        )
        conn.executemany(
            "INSERT INTO facts (case_id, label, value, verified) VALUES (?, ?, ?, ?)",
            [
                ("case-2026-jc", "Fault", "Other driver ran red light — clear liability", 1),
                ("case-2026-jc", "Insurance", "Progressive policy #4421-A confirmed", 0),
                ("case-2026-jc", "Treatment", "MRI pending — must be scheduled within 7 days", 0),
                ("case-2026-jc", "Evidence", "Client has dashcam footage from incident", 1),
                ("case-2026-jc", "Statute", "SOL expires 2028-06-02 — 2 years CA", 1),
            ],
        )
        conn.executemany(
            "INSERT INTO case_notes (id, case_id, note_type, content, created_by) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "note-jc-1", "case-2026-jc", "intake_transcript",
                    "James Carter called reporting rear-end collision at First and Market, San Jose. "
                    "Robert Hall ran red light. Client has dashcam footage — secured. "
                    "Neck/back pain and concussion symptoms. Progressive confirmed as at-fault insurer.",
                    "donna",
                ),
                (
                    "note-jc-2", "case-2026-jc", "attorney_note",
                    "Strong liability — dashcam makes fault unambiguous. "
                    "Push MRI within 7 days before Progressive tries to argue pre-existing. "
                    "Issue preservation demand for Hall's phone records (distracted driving angle).",
                    "attorney",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO memories (case_id, kind, content) VALUES (?, ?, ?)",
            [
                (
                    "case-2026-jc", "case_summary",
                    "James Carter: auto accident 2026-06-02, clear fault (dashcam), MRI pending. "
                    "Progressive insurer. Follow up: confirm MRI booked, request police report.",
                ),
                (
                    "case-2026-jc", "next_action",
                    "Book MRI within 7 days. Order police report. "
                    "Send preservation letter for Hall's phone records. Calendar follow-up June 16.",
                ),
            ],
        )

        # ── Client 2: Sofia Nguyen — Slip & Fall ──────────────────────────────
        conn.execute(
            "INSERT INTO clients (id, name, phone, email, consent_recording, consent_ai_disclosure, consent_data_storage)"
            " VALUES (?, ?, ?, ?, 1, 1, 1)",
            ("client-sofia-nguyen", "Sofia Nguyen", "+14085550242", "sofia.nguyen@example.com"),
        )
        conn.execute(
            """INSERT INTO cases
               (id, client_id, case_type, incident_date, incident_location,
                at_fault_party, injuries, treatment_received, witnesses, status,
                statute_of_limitations_date, state_jurisdiction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "case-2026-sn", "client-sofia-nguyen", "slip_fall", "2026-05-19",
                "Valley Foods Grocery, 1420 Blossom Hill Rd, San Jose, CA",
                "Valley Foods Grocery — wet floor, no warning signs posted; insured by Zurich North America",
                "Fractured left wrist (distal radius), bruised right knee",
                "ER at Good Samaritan Hospital — wrist cast applied; orthopedist follow-up scheduled",
                "Jordan (store employee, badge #14) admitted floor was mopped 10 min prior with no sign placed",
                "qualification", "2028-05-19", "CA",
            ),
        )
        conn.executemany(
            "INSERT INTO facts (case_id, label, value, verified) VALUES (?, ?, ?, ?)",
            [
                ("case-2026-sn", "Fault", "No wet floor sign posted — premises liability clear", 1),
                ("case-2026-sn", "Witness", "Employee Jordan (badge #14) admitted no signage was placed", 1),
                ("case-2026-sn", "Evidence", "Store surveillance camera covers fall location — spoliation risk", 0),
                ("case-2026-sn", "Treatment", "Wrist cast 6 weeks + ~4 months PT post-cast expected", 0),
                ("case-2026-sn", "Insurance", "Valley Foods insured by Zurich North America", 0),
            ],
        )
        conn.executemany(
            "INSERT INTO case_notes (id, case_id, note_type, content, created_by) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "note-sn-1", "case-2026-sn", "intake_transcript",
                    "Sofia Nguyen slipped on wet floor at Valley Foods, Blossom Hill Rd, May 19. "
                    "No signage posted. Employee Jordan (badge #14) admitted floor was mopped 10 min prior. "
                    "Wrist fracture confirmed at ER. Surveillance footage must be preserved immediately.",
                    "donna",
                ),
                (
                    "note-sn-2", "case-2026-sn", "attorney_note",
                    "Send spoliation letter to Valley Foods within 24h — surveillance is make-or-break. "
                    "Jordan's admission is gold. Zurich settles premises liability fast when liability is clear. "
                    "Expected range: $80k–$200k depending on PT duration and lost wages.",
                    "attorney",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO memories (case_id, kind, content) VALUES (?, ?, ?)",
            [
                (
                    "case-2026-sn", "case_summary",
                    "Sofia Nguyen: slip & fall Valley Foods 2026-05-19, wrist fracture, employee witness confirmed "
                    "no signage. Send spoliation letter immediately. Strong premises liability. Zurich insurer.",
                ),
                (
                    "case-2026-sn", "next_action",
                    "Spoliation letter to Valley Foods within 24h. Formally request surveillance footage. "
                    "Book orthopedist follow-up. Demand Zurich policy number from store management.",
                ),
            ],
        )

        # ── Firm Profile — Harrington & Kim ───────────────────────────────────
        conn.execute(
            "INSERT INTO clients (id, name, phone, email) VALUES (?, ?, ?, ?)",
            ("client-firm", "Harrington & Kim Personal Injury Law", None, "info@hklaw.example.com"),
        )
        conn.execute(
            """INSERT INTO cases
               (id, client_id, case_type, incident_date, incident_location,
                at_fault_party, injuries, treatment_received, witnesses, status,
                statute_of_limitations_date, state_jurisdiction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "case-firm-profile", "client-firm", "auto_accident", "2012-01-01",
                "California", "N/A", "N/A", "N/A", "", "settled", "N/A", "CA",
            ),
        )
        conn.executemany(
            "INSERT INTO memories (case_id, kind, content) VALUES (?, ?, ?)",
            [
                (
                    "case-firm-profile", "firm_stats",
                    "Harrington & Kim Personal Injury Law: founded 2012, 12 years in California. "
                    "847 total cases handled. 94% success rate. Average settlement $185,000. "
                    "Largest settlement $2.3M (commercial trucking accident, 2023). "
                    "No win no fee — contingency 33% pre-litigation, 40% post-litigation.",
                ),
                (
                    "case-firm-profile", "firm_practice_areas",
                    "Case breakdown: 510 auto accidents (60%), 212 slip & fall (25%), 125 workplace injuries (15%). "
                    "Licensed in California only. Personal injury SOL in CA: 2 years from incident date. "
                    "We do NOT handle criminal, family law, or immigration matters.",
                ),
                (
                    "case-firm-profile", "firm_track_record",
                    "Notable wins: $2.3M trucking accident Fresno 2023, $1.1M construction site fall SF 2022, "
                    "$875K rear-end freeway collision San Jose 2024, $650K grocery store slip Oakland 2023. "
                    "Average auto accident case: 8–14 months. Average slip & fall: 6–18 months.",
                ),
                (
                    "case-firm-profile", "firm_process",
                    "Intake process: free consultation → case qualification → investigation → demand letter → "
                    "negotiation → mediation → litigation if needed. "
                    "We handle all medical lien coordination, police report retrieval, and spoliation letters. "
                    "Client portal available for document uploads and case status updates.",
                ),
            ],
        )


def _seed_calendar(db_path: Path) -> None:
    init_calendar_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM calendar")

    create_event(
        db_path,
        title="James Carter — MRI scheduling follow-up",
        start="2026-06-16T10:00:00-07:00",
        end="2026-06-16T10:30:00-07:00",
        event_type="follow_up",
        client_id="client-james-carter",
        attendee="James Carter",
        case_id="case-2026-jc",
        notes="Confirm MRI booked. Ask about police report request status. Discuss dashcam transfer.",
    )
    create_event(
        db_path,
        title="Sofia Nguyen — Initial consultation",
        start="2026-06-17T14:00:00-07:00",
        end="2026-06-17T15:00:00-07:00",
        event_type="consult",
        client_id="client-sofia-nguyen",
        attendee="Sofia Nguyen",
        case_id="case-2026-sn",
        notes="Review ER records. Confirm spoliation letter sent to Valley Foods. Discuss Zurich claim.",
    )


def main() -> None:
    cfg = TelephonyConfig.from_env()
    print(f"Context DB: {cfg.context_db}")
    _seed_context(cfg.context_db)
    print("  2 clients + firm profile seeded")
    print(f"Calendar DB: {cfg.calendar_db}")
    _seed_calendar(cfg.calendar_db)
    print("  2 calendar events seeded")
    print("Done.")


if __name__ == "__main__":
    main()
