"""Seed demo data for Donna hackathon presentation."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge.db import (
    init_db, insert_client, insert_case, add_case_note,
    book_calendar_event, register_document, update_client_consent,
)
from knowledge.chroma_store import ingest_document


def seed():
    print("Initializing database...")
    init_db()

    # --- Client 1: Sarah Chen — Slip and Fall (new intake) ---
    sarah_id = insert_client("Sarah Chen", "+14155551234", "sarah.chen@email.com")
    update_client_consent(sarah_id, "consent_recording", True)
    update_client_consent(sarah_id, "consent_ai_disclosure", True)

    sarah_case = insert_case(
        client_id=sarah_id,
        case_type="slip_fall",
        incident_date="2026-03-03",
        at_fault_party="Westfield Shopping Center",
        injuries="Fractured left wrist, bruised ribs, soft tissue damage to lower back",
        state="CA",
        incident_location="Westfield Valley Fair, Santa Clara, CA",
        treatment_received="ER visit at Kaiser, X-rays, cast applied, follow-up with orthopedist",
        witnesses="Marcus Johnson (security guard), Emily Park (bystander)",
    )

    add_case_note(sarah_case, "intake_transcript",
        "Client reports slipping on wet floor near food court entrance. "
        "No wet floor sign was posted. Security camera footage may be available. "
        "Client was carrying groceries and fell forward onto left hand.")

    # Ingest a fake police report for demo
    police_report = """
    INCIDENT REPORT — Santa Clara Police Department
    Case #: 2026-SC-04182
    Date: March 3, 2026
    Location: Westfield Valley Fair, 2855 Stevens Creek Blvd, Santa Clara, CA 95050

    INCIDENT: Slip and fall on wet surface in commercial property.

    REPORTING PARTY: Sarah Chen, age 34, of San Jose, CA.

    SUMMARY: At approximately 14:30 hours, reporting party slipped on an unmarked
    wet floor surface near the food court entrance of the above location. Responding
    officers observed no wet floor signage in the immediate area. Property security
    (Marcus Johnson, badge #447) confirmed that the floor had been mopped approximately
    20 minutes prior to the incident. No wet floor signs were deployed.

    INJURIES: Reporting party complained of left wrist pain and lower back pain.
    Paramedics responded and transported to Kaiser Permanente Santa Clara.

    WITNESSES: Marcus Johnson (Westfield Security), Emily Park (bystander, contact
    provided to RP).

    EVIDENCE: Surveillance footage requested from property management. Photos of
    scene taken by responding officer (attached).

    OFFICER: Sgt. R. Martinez, Badge #2891
    """

    ingest_document(sarah_case, police_report, "police_report", "sarah_chen_police_report.txt")
    register_document(sarah_case, "sarah_chen_police_report.txt", "police_report")

    print(f"  Sarah Chen (ID: {sarah_id}) — slip-and-fall, case {sarah_case}")

    # --- Client 2: Marcus Williams — Auto Accident (URGENT SOL) ---
    marcus_id = insert_client("Marcus Williams", "+14155552345", "marcus.w@email.com")
    update_client_consent(marcus_id, "consent_recording", True)
    update_client_consent(marcus_id, "consent_ai_disclosure", True)

    # Set incident date so SOL is ~28 days away
    urgent_incident = (datetime.now() - timedelta(days=365 * 2 - 28)).strftime("%Y-%m-%d")
    marcus_case = insert_case(
        client_id=marcus_id,
        case_type="auto_accident",
        incident_date=urgent_incident,
        at_fault_party="James Cooper (ran red light)",
        injuries="Whiplash, herniated disc L4-L5, chronic neck pain",
        state="CA",
        incident_location="Intersection of El Camino Real and Lawrence Expy, Sunnyvale, CA",
        treatment_received="Ongoing physical therapy, MRI completed, pain management",
    )

    add_case_note(marcus_case, "attorney_note",
        "Settlement negotiation in progress with Allstate. "
        "Demand letter sent 2026-04-15 for $285,000. "
        "Counter-offer received: $120,000. Client wants to proceed to mediation.")

    book_calendar_event(
        client_id=marcus_id,
        case_id=marcus_case,
        event_type="deposition",
        title="Marcus Williams — Deposition of James Cooper",
        scheduled_at=(datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT10:00:00"),
        duration_minutes=120,
        notes="Opposing counsel: Smith & Associates. Location: their office.",
    )

    print(f"  Marcus Williams (ID: {marcus_id}) — auto accident, URGENT SOL, case {marcus_case}")

    # --- Client 3: Elena Rodriguez — Workplace Injury (settled) ---
    elena_id = insert_client("Elena Rodriguez", "+14155553456", "elena.r@email.com")
    update_client_consent(elena_id, "consent_recording", True)

    elena_case = insert_case(
        client_id=elena_id,
        case_type="workplace",
        incident_date="2025-09-15",
        at_fault_party="Pacific Coast Construction LLC",
        injuries="Torn rotator cuff, required surgery",
        state="CA",
        incident_location="Construction site, 450 Mission St, SF",
        treatment_received="Arthroscopic surgery, 6 months PT, full recovery",
    )

    add_case_note(elena_case, "attorney_note",
        "Case settled for $175,000. Client satisfied with outcome. "
        "Settlement check received and disbursed. Case closed 2026-05-20.")

    # Update status to settled
    from knowledge.db import get_conn
    conn = get_conn()
    conn.execute("UPDATE cases SET status = 'settled' WHERE id = ?", (elena_case,))
    conn.commit()
    conn.close()

    print(f"  Elena Rodriguez (ID: {elena_id}) — workplace injury, settled, case {elena_case}")

    # --- Upcoming calendar events ---
    book_calendar_event(
        client_id=sarah_id,
        case_id=sarah_case,
        event_type="follow_up",
        title="Sarah Chen — Follow-up call re: medical records",
        scheduled_at=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT14:00:00"),
        duration_minutes=30,
    )

    print("\nDemo data seeded. Ready for pitch.")
    print(f"  3 clients, 3 cases, 1 police report in ChromaDB")
    print(f"  URGENT: Marcus Williams SOL in ~28 days")


if __name__ == "__main__":
    seed()
