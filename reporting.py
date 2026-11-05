"""Reporting module for cause lists, case diaries, pendency, and run summaries.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from config import (
    COMMERCIAL_DISPOSAL_TARGET_DAYS,
    EVIDENCE_DELAY_THRESHOLD_DAYS,
    FLAG_DELAY,
    FLAG_EVIDENCE_DELAY,
    FLAG_OVERBOARD,
)
from models import (
    Bench,
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
    """Format comprehensive case diary showing lifecycle events, costs, and status (BR-50)."""
    outstanding_cost = max(Decimal("0.00"), case.costs_assessed - case.costs_paid)
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
        f"Transfer Count:    {case.transferred_count}",
        f"Costs Assessed:    ₹{case.costs_assessed:,.2f}",
        f"Costs Paid:        ₹{case.costs_paid:,.2f}",
        f"Costs Due:         ₹{outstanding_cost:,.2f}",
        f"Flags:             {', '.join(sorted(case.flags)) if case.flags else 'None'}",
        "-" * 70,
        f"Hearing History ({len(case.adjournment_history)} events):",
    ]

    if not case.adjournment_history:
        lines.append("  (No hearing events recorded)")
    else:
        for idx, event in enumerate(case.adjournment_history, 1):
            details = [f"Outcome: {event.outcome.value}"]
            if event.adjournment_reason:
                details.append(f"Reason: {event.adjournment_reason.value}")
            if event.requesting_party:
                details.append(f"By: {event.requesting_party}")
            if event.cost_assessed > Decimal("0"):
                paid_str = "PAID" if event.cost_paid else "PENDING"
                details.append(f"Cost: ₹{event.cost_assessed} ({paid_str})")
            if event.target_bench_id:
                details.append(f"To Bench: {event.target_bench_id}")
            if event.notes:
                details.append(f"Notes: {event.notes}")

            lines.append(f"  {idx}. Date: {event.hearing_date.isoformat()} | {' | '.join(details)}")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_all_case_diaries(cases: list[Case]) -> str:
    """Format combined case diaries for all registered cases (BR-50)."""
    sorted_cases = sorted(cases, key=lambda c: c.case_id)
    return "\n\n".join(generate_case_diary(c) for c in sorted_cases)


def generate_evidence_delay_report(cases: list[Case], as_of_date: date) -> tuple[str, dict[str, Any]]:
    """Generate specialized report for matters exceeding 180 days in EVIDENCE (BR-33)."""
    delayed_cases = []
    lines = [
        "=" * 85,
        "PRINCIPAL DISTRICT JUDGE - EVIDENCE DELAY REPORT (BR-33)",
        f"As of Date: {as_of_date.isoformat()} | Delay Threshold: > {EVIDENCE_DELAY_THRESHOLD_DAYS} Days in EVIDENCE",
        "=" * 85,
        f"{'Case ID':<16} | {'Subject':<10} | {'Assigned Bench':<16} | {'Days in Ev':<11} | {'Parties'}",
        "-" * 85,
    ]

    for c in sorted(cases, key=lambda x: x.case_id):
        if c.stage == CaseStage.EVIDENCE:
            ref_date = c.stage_start_date or c.filing_date
            days_in_ev = (as_of_date - ref_date).days
            if days_in_ev > EVIDENCE_DELAY_THRESHOLD_DAYS or FLAG_DELAY in c.flags or FLAG_EVIDENCE_DELAY in c.flags:
                delayed_cases.append({
                    "case_id": c.case_id,
                    "subject": c.subject.value,
                    "assigned_bench": c.assigned_bench or "Unallocated",
                    "days_in_evidence": days_in_ev,
                    "parties": c.party_ids,
                    "stage_start_date": ref_date.isoformat(),
                })
                parties_str = ", ".join(c.party_ids)
                lines.append(
                    f"{c.case_id:<16} | {c.subject.value:<10} | {c.assigned_bench or 'Unallocated':<16} | {days_in_ev:<11} | {parties_str}"
                )

    if not delayed_cases:
        lines.append("  (No matters currently exceed 180 days in the Evidence stage)")

    lines.append("=" * 85)
    lines.append(f"Total Evidence Delay Matters: {len(delayed_cases)}")
    lines.append("=" * 85)

    report_data = {
        "as_of_date": as_of_date.isoformat(),
        "threshold_days": EVIDENCE_DELAY_THRESHOLD_DAYS,
        "total_delayed": len(delayed_cases),
        "cases": delayed_cases,
    }
    return "\n".join(lines), report_data


def generate_principal_judge_report(
    cases: list[Case],
    benches: list[Bench],
    as_of_date: date,
    cause_lists: dict[str, list[CauseListEntry]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generate comprehensive administrative oversight report for the Principal District Judge."""
    total_cases = len(cases)
    admitted_cases = [c for c in cases if c.status == CaseStatus.ADMITTED or c.assigned_bench]
    decided_cases = [c for c in cases if c.status == CaseStatus.DECIDED]
    active_pending = [c for c in cases if c.status not in (CaseStatus.DECIDED, CaseStatus.REJECTED, CaseStatus.RETURNED)]

    # Overdue commercial
    overdue_commercial = [
        c.case_id for c in active_pending
        if c.subject == SubjectType.COMMERCIAL and (as_of_date - c.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
    ]

    # Evidence delay
    _, ev_data = generate_evidence_delay_report(cases, as_of_date)
    evidence_delay_ids = [item["case_id"] for item in ev_data["cases"]]

    # Overboard matters
    overboard_cases = [c.case_id for c in cases if FLAG_OVERBOARD in c.flags]

    # Delay condonation pending
    condonation_pending = [c.case_id for c in cases if "DELAY_CONDONATION_PENDING" in c.flags]

    # Defective fee filings
    defective_cases = [c.case_id for c in cases if c.status == CaseStatus.DEFECTIVE]

    # Outstanding costs
    cost_pending = [c.case_id for c in cases if (c.costs_assessed - c.costs_paid) > Decimal("0")]

    lines = [
        "#" * 85,
        "PRINCIPAL DISTRICT JUDGE - COMPREHENSIVE ADMINISTRATIVE OVERSIGHT REPORT",
        f"Registry Snapshot as of: {as_of_date.isoformat()}",
        "#" * 85,
        "",
        "--- 1. OVERALL REGISTRY SUMMARY ---",
        f"Total Filings Registered:       {total_cases}",
        f"Active Pending Cases:           {len(active_pending)}",
        f"Cases Decided / Disposed:       {len(decided_cases)}",
        f"Defective Filings Pending Cure: {len(defective_cases)}",
        f"Overdue Commercial (BR-25):     {len(overdue_commercial)}",
        f"Evidence Delay Matters (BR-33): {len(evidence_delay_ids)}",
        f"Overboard Matters (BR-42):      {len(overboard_cases)}",
        f"Delay Condonation (BR-10):      {len(condonation_pending)}",
        f"Outstanding Costs Due (BR-38):  {len(cost_pending)}",
        "",
        "--- 2. BENCH UTILIZATION & CAPACITY ---",
    ]

    bench_stats = {}
    for b in sorted(benches, key=lambda x: x.bench_id):
        assigned = [c for c in active_pending if c.assigned_bench == b.bench_id]
        scheduled_count = 0
        if cause_lists:
            # Check cause lists matching this bench
            for k, entries in cause_lists.items():
                if k.startswith(b.bench_id):
                    scheduled_count += len(entries)

        bench_stats[b.bench_id] = {
            "jurisdictions": [j.value for j in b.subject_jurisdictions],
            "daily_capacity": b.daily_board_capacity,
            "active_pending_assigned": len(assigned),
            "sitting_today": as_of_date.weekday() in b.sitting_days and as_of_date not in b.leave_dates,
        }
        status_sit = "SITTING" if bench_stats[b.bench_id]["sitting_today"] else "NOT SITTING / ON LEAVE"
        lines.append(
            f"  * Bench: {b.bench_id:<16} | Capacity: {b.daily_board_capacity:<3} | Pending: {len(assigned):<4} | Status: {status_sit}"
        )

    lines.extend([
        "",
        "--- 3. CRITICAL ACTION LISTS ---",
        f"Overdue Commercial Cases (>365d): {', '.join(overdue_commercial) if overdue_commercial else 'None'}",
        f"Evidence Delay Cases (>180d):     {', '.join(evidence_delay_ids) if evidence_delay_ids else 'None'}",
        f"Overboard Cases (Day 60):         {', '.join(overboard_cases) if overboard_cases else 'None'}",
        f"Delay Condonation Applications:   {', '.join(condonation_pending) if condonation_pending else 'None'}",
        f"Defective Fee Filings:            {', '.join(defective_cases) if defective_cases else 'None'}",
        f"Cases with Costs Outstanding:     {', '.join(cost_pending) if cost_pending else 'None'}",
        "#" * 85,
    ])

    report_dict = {
        "as_of_date": as_of_date.isoformat(),
        "total_registered": total_cases,
        "active_pending": len(active_pending),
        "decided": len(decided_cases),
        "defective_pending_cure": len(defective_cases),
        "overdue_commercial": overdue_commercial,
        "evidence_delay": evidence_delay_ids,
        "overboard": overboard_cases,
        "condonation_pending": condonation_pending,
        "costs_pending": cost_pending,
        "bench_statistics": bench_stats,
    }

    return "\n".join(lines), report_dict


def generate_pendency_report_text(report_data: dict[str, Any]) -> str:
    """Format pendency dictionary into human-readable text report."""
    lines = [
        "=" * 70,
        "DISTRICT COURT PENDENCY REPORT",
        f"As of Date: {report_data.get('as_of_date')} | Total Pending: {report_data.get('total_pending')}",
        "=" * 70,
        "Pendency by Stage:",
    ]
    for stage, count in report_data.get("by_stage", {}).items():
        lines.append(f"  - {stage:<15}: {count}")

    lines.append("")
    lines.append("Pendency by Subject:")
    for subject, count in report_data.get("by_subject", {}).items():
        lines.append(f"  - {subject:<15}: {count}")

    overdue_comm = report_data.get("overdue_commercial", [])
    lines.append("")
    lines.append(f"Overdue Commercial Cases (>365 days): {len(overdue_comm)}")
    if overdue_comm:
        lines.append(f"  Cases: {', '.join(overdue_comm)}")

    ev_delay = report_data.get("evidence_delay_cases", [])
    lines.append(f"Evidence Delay Cases (>180 days in Evidence): {len(ev_delay)}")
    if ev_delay:
        lines.append(f"  Cases: {', '.join(ev_delay)}")

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
