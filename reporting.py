"""Reporting module for cause lists, case diaries, pendency, and run summaries.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date
from typing import Any

from config import (
    COMMERCIAL_DISPOSAL_TARGET_DAYS,
    EVIDENCE_DELAY_THRESHOLD_DAYS,
    FLAG_DELAY,
)
from models import (
    Case,
    CaseStage,
    CaseStatus,
    CauseListEntry,
    SubjectType,
)


def generate_cause_list_report(
    bench_id: str,
    listing_date: date,
    entries: list[CauseListEntry],
) -> str:
    """Format daily cause list for a judicial bench (BR-49)."""
    lines = [
        "=" * 80,
        f"DISTRICT COURT CAUSE LIST - BENCH: {bench_id}",
        f"Sitting Date: {listing_date.isoformat()} | Total Matters Scheduled: {len(entries)}",
        "=" * 80,
        f"{'Pos':<5} | {'Case ID':<16} | {'Band':<6} | {'Carry-Over':<10} | {'Final':<6} | Flags",
        "-" * 80,
    ]

    for e in entries:
        pos_str = f"Pos: {e.position}"
        band_str = f"Band {e.priority_band.value}"
        carry_str = "YES" if e.carry_over_indicator else "NO"
        final_str = "YES" if e.final_hearing_indicator else "NO"
        flags_str = ", ".join(e.flags) if e.flags else "-"
        lines.append(
            f"{pos_str:<5} | {e.case_id:<16} | {band_str:<6} | {carry_str:<10} | {final_str:<6} | {flags_str}"
        )

    lines.append("=" * 80)
    return "\n".join(lines)


def generate_case_diary(case: Case) -> str:
    """Format comprehensive case diary showing lifecycle events and status (BR-50)."""
    lines = [
        "=" * 70,
        f"CASE DIARY: {case.case_id} ({case.case_type})",
        "=" * 70,
        f"Subject:           {case.subject.value}",
        f"Parties:           {', '.join(case.party_ids)}",
        f"Filing Date:       {case.filing_date.isoformat()}",
        f"Claim Value:       ₹{case.claim_value:,.2f}",
        f"Court Fee Paid:    ₹{case.court_fee_paid:,.2f}",
        f"Status:            {case.status.value}",
        f"Stage:             {case.stage.value}",
        f"Assigned Bench:    {case.assigned_bench or 'Unallocated'}",
        f"Next Hearing Date: {case.next_hearing_date.isoformat() if case.next_hearing_date else 'Not Scheduled'}",
        f"Flags:             {', '.join(sorted(case.flags)) if case.flags else 'None'}",
        "-" * 70,
        f"Hearing History ({len(case.adjournment_history)} events):",
    ]

    if not case.adjournment_history:
        lines.append("  (No hearing events recorded)")
    else:
        for idx, event in enumerate(case.adjournment_history, 1):
            reason_str = f" [Reason: {event.adjournment_reason.value}]" if event.adjournment_reason else ""
            lines.append(
                f"  {idx}. Date: {event.hearing_date} | Outcome: {event.outcome.value}{reason_str}"
            )

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_pendency_report(cases: list[Case], as_of_date: date) -> dict[str, Any]:
    """Generate pendency report detailing stage breakdown and delay flags (BR-51)."""
    pending_cases = [c for c in cases if c.status not in (CaseStatus.DECIDED, CaseStatus.REJECTED, CaseStatus.RETURNED)]

    by_stage: dict[str, int] = {st.value: 0 for st in CaseStage}
    by_subject: dict[str, int] = {sub.value: 0 for sub in SubjectType}
    overdue_commercial: list[str] = []
    evidence_delay_cases: list[str] = []

    for c in pending_cases:
        by_stage[c.stage.value] = by_stage.get(c.stage.value, 0) + 1
        by_subject[c.subject.value] = by_subject.get(c.subject.value, 0) + 1

        age_days = (as_of_date - c.filing_date).days
        if c.subject == SubjectType.COMMERCIAL and age_days > COMMERCIAL_DISPOSAL_TARGET_DAYS:
            overdue_commercial.append(c.case_id)

        # Check evidence delay (>180 days in evidence) (BR-33)
        if c.stage == CaseStage.EVIDENCE:
            if FLAG_DELAY in c.flags or (c.stage_start_date and (as_of_date - c.stage_start_date).days > EVIDENCE_DELAY_THRESHOLD_DAYS):
                evidence_delay_cases.append(c.case_id)

    return {
        "as_of_date": as_of_date.isoformat(),
        "total_pending": len(pending_cases),
        "by_stage": by_stage,
        "by_subject": by_subject,
        "overdue_commercial": overdue_commercial,
        "evidence_delay_cases": evidence_delay_cases,
    }


def generate_execution_summary(
    run_date: date,
    filings_count: int,
    admitted_count: int,
    defective_count: int,
    rejected_count: int,
    allocated_count: int,
    listed_count: int,
) -> str:
    """Produce concise execution summary text."""
    lines = [
        "==================================================",
        "COURT REGISTRY ENGINE - EXECUTION SUMMARY",
        "==================================================",
        f"Execution Date:     {run_date.isoformat()}",
        f"Total Filings:      {filings_count}",
        f"Cases Admitted:     {admitted_count}",
        f"Cases Defective:    {defective_count}",
        f"Cases Rejected:     {rejected_count}",
        f"Cases Allocated:    {allocated_count}",
        f"Cause-List Entries: {listed_count}",
        "Status:             COMPLETED SUCCESSFULLY",
        "==================================================",
    ]
    return "\n".join(lines)
