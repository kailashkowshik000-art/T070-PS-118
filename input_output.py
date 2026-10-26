"""Input/Output and validation module for Court Case Listing Engine.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from models import (
    AdmissionDecision,
    AdmissionResult,
    AdjournmentReason,
    AllocationResult,
    Bench,
    Case,
    CaseStage,
    CaseStatus,
    CauseListEntry,
    HearingEvent,
    HearingOutcome,
    PriorityBand,
    SubjectType,
)


class ValidationError(Exception):
    """Raised when data fails schema or domain validation."""
    pass


def parse_date(date_str: str | None, field_name: str) -> date | None:
    """Safely parse ISO YYYY-MM-DD date."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid date format for '{field_name}': expected YYYY-MM-DD, got '{date_str}'.")


def parse_decimal(value: Any, field_name: str) -> Decimal:
    """Safely parse positive monetary decimal."""
    try:
        d = Decimal(str(value))
        if d < Decimal("0"):
            raise ValidationError(f"Field '{field_name}' cannot be negative, got {value}.")
        return d
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"Invalid monetary value for '{field_name}': got '{value}'.")


def load_holidays(file_path: Path | str) -> set[date]:
    """Load court holidays from JSON file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Holidays file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValidationError("Holidays file must contain a JSON array.")

    holidays: set[date] = set()
    for item in data:
        if isinstance(item, str):
            dt = parse_date(item, "holiday")
            if dt:
                holidays.add(dt)
        elif isinstance(item, dict) and "date" in item:
            dt = parse_date(item["date"], "holiday.date")
            if dt:
                holidays.add(dt)
        else:
            raise ValidationError(f"Invalid holiday entry format: {item}")

    return holidays


def load_benches(file_path: Path | str) -> list[Bench]:
    """Load and validate bench definitions from JSON file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Benches file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValidationError("Benches file must contain a JSON array.")

    benches: list[Bench] = []
    seen_bench_ids: set[str] = set()

    for item in data:
        if not isinstance(item, dict):
            raise ValidationError(f"Bench entry must be an object, got {item}.")

        bench_id = item.get("bench_id")
        if not bench_id or not isinstance(bench_id, str):
            raise ValidationError("Bench entry missing valid 'bench_id'.")

        if bench_id in seen_bench_ids:
            raise ValidationError(f"Duplicate bench_id detected: '{bench_id}'.")
        seen_bench_ids.add(bench_id)

        raw_jurisdictions = item.get("subject_jurisdictions", [])
        if not isinstance(raw_jurisdictions, list) or not raw_jurisdictions:
            raise ValidationError(f"Bench '{bench_id}' must have non-empty 'subject_jurisdictions'.")

        jurisdictions: list[SubjectType] = []
        for j in raw_jurisdictions:
            try:
                jurisdictions.append(SubjectType(str(j).upper()))
            except ValueError:
                raise ValidationError(f"Invalid subject jurisdiction '{j}' in bench '{bench_id}'.")

        commercial_jurisdiction = bool(item.get("commercial_jurisdiction", False))
        sitting_days = item.get("sitting_days", [0, 1, 2, 3, 4])
        if not isinstance(sitting_days, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in sitting_days):
            raise ValidationError(f"Bench '{bench_id}' sitting_days must be integers between 0 and 6.")

        capacity = item.get("daily_board_capacity", 40)
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValidationError(f"Bench '{bench_id}' daily_board_capacity must be a positive integer.")

        raw_leave = item.get("leave_dates", [])
        leave_dates: set[date] = set()
        for ld in raw_leave:
            dt = parse_date(ld, f"{bench_id}.leave_date")
            if dt:
                leave_dates.add(dt)

        raw_conflicts = item.get("conflict_party_ids", [])
        conflict_party_ids = {str(cp) for cp in raw_conflicts}

        designated_family_days = item.get("designated_family_hearing_days", [3])

        benches.append(
            Bench(
                bench_id=bench_id,
                subject_jurisdictions=jurisdictions,
                commercial_jurisdiction=commercial_jurisdiction,
                sitting_days=sitting_days,
                daily_board_capacity=capacity,
                leave_dates=leave_dates,
                conflict_party_ids=conflict_party_ids,
                designated_family_hearing_days=designated_family_days,
            )
        )

    return benches


def load_filings(file_path: Path | str) -> list[Case]:
    """Load and validate case filings from JSON file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Filings file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValidationError("Filings file must contain a JSON array.")

    cases: list[Case] = []
    seen_case_ids: set[str] = set()

    for item in data:
        if not isinstance(item, dict):
            raise ValidationError(f"Filing entry must be an object, got {item}.")

        case_id = item.get("case_id")
        if not case_id or not isinstance(case_id, str):
            raise ValidationError("Filing entry missing valid 'case_id'.")

        if case_id in seen_case_ids:
            raise ValidationError(f"Duplicate case_id detected: '{case_id}'.")
        seen_case_ids.add(case_id)

        case_type = item.get("case_type")
        if not case_type or not isinstance(case_type, str):
            raise ValidationError(f"Case '{case_id}' missing valid 'case_type'.")

        subject_raw = item.get("subject")
        try:
            subject = SubjectType(str(subject_raw).upper())
        except (ValueError, TypeError):
            raise ValidationError(f"Case '{case_id}' has invalid subject '{subject_raw}'.")

        party_ids = item.get("party_ids", [])
        if not isinstance(party_ids, list) or not party_ids:
            raise ValidationError(f"Case '{case_id}' must have a non-empty list of 'party_ids'.")

        filing_date_parsed = parse_date(item.get("filing_date"), f"{case_id}.filing_date")
        if not filing_date_parsed:
            raise ValidationError(f"Case '{case_id}' missing required 'filing_date'.")

        cause_of_action_date = parse_date(item.get("cause_of_action_date"), f"{case_id}.cause_of_action_date")
        order_date = parse_date(item.get("order_date"), f"{case_id}.order_date")

        claim_value = parse_decimal(item.get("claim_value", "0"), f"{case_id}.claim_value")
        court_fee_paid = parse_decimal(item.get("court_fee_paid", "0"), f"{case_id}.court_fee_paid")

        urgency = bool(item.get("urgency", False))
        wrong_forum_days = int(item.get("wrong_forum_days", 0))
        has_condonation_application = bool(item.get("has_condonation_application", False))
        involves_minor = bool(item.get("involves_minor", False))
        is_part_heard = bool(item.get("is_part_heard", False))

        raw_stage = item.get("stage", "PLEADINGS")
        try:
            stage = CaseStage(str(raw_stage).upper())
        except ValueError:
            raise ValidationError(f"Case '{case_id}' has invalid stage '{raw_stage}'.")

        cases.append(
            Case(
                case_id=case_id,
                case_type=case_type,
                subject=subject,
                party_ids=[str(p) for p in party_ids],
                filing_date=filing_date_parsed,
                cause_of_action_date=cause_of_action_date,
                order_date=order_date,
                claim_value=claim_value,
                court_fee_paid=court_fee_paid,
                urgency=urgency,
                wrong_forum_days=wrong_forum_days,
                has_condonation_application=has_condonation_application,
                involves_minor=involves_minor,
                is_part_heard=is_part_heard,
                stage=stage,
            )
        )

    return cases


def load_events(file_path: Path | str, known_cases: dict[str, Case] | None = None) -> list[HearingEvent]:
    """Load and validate hearing events from JSON file."""
    path = Path(file_path)
    if not path.exists():
        # Events file might be empty or optional in some initial setups
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValidationError("Events file must contain a JSON array.")

    events: list[HearingEvent] = []
    seen_event_ids: set[str] = set()

    for item in data:
        if not isinstance(item, dict):
            raise ValidationError(f"Event entry must be an object, got {item}.")

        event_id = item.get("event_id")
        if not event_id or not isinstance(event_id, str):
            raise ValidationError("Event entry missing valid 'event_id'.")

        if event_id in seen_event_ids:
            raise ValidationError(f"Duplicate event_id detected: '{event_id}'.")
        seen_event_ids.add(event_id)

        case_id = item.get("case_id")
        if not case_id or not isinstance(case_id, str):
            raise ValidationError(f"Event '{event_id}' missing valid 'case_id'.")

        if known_cases is not None and case_id not in known_cases:
            raise ValidationError(f"Event '{event_id}' references unknown case_id '{case_id}'.")

        hearing_date = parse_date(item.get("hearing_date"), f"{event_id}.hearing_date")
        if not hearing_date:
            raise ValidationError(f"Event '{event_id}' missing required 'hearing_date'.")

        raw_outcome = item.get("outcome")
        try:
            outcome = HearingOutcome(str(raw_outcome).upper())
        except (ValueError, TypeError):
            raise ValidationError(f"Event '{event_id}' has invalid outcome '{raw_outcome}'.")

        raw_reason = item.get("adjournment_reason")
        adjournment_reason = None
        if raw_reason:
            try:
                adjournment_reason = AdjournmentReason(str(raw_reason).upper())
            except ValueError:
                raise ValidationError(f"Event '{event_id}' has invalid adjournment_reason '{raw_reason}'.")

        consent_indicator = bool(item.get("consent_indicator", False))
        requesting_party = item.get("requesting_party")
        mentioned_at = item.get("mentioned_at")
        notes = item.get("notes", "")

        events.append(
            HearingEvent(
                event_id=event_id,
                case_id=case_id,
                hearing_date=hearing_date,
                outcome=outcome,
                adjournment_reason=adjournment_reason,
                requesting_party=requesting_party,
                consent_indicator=consent_indicator,
                mentioned_at=mentioned_at,
                notes=notes,
            )
        )

    return events


def save_admission_results(results: list[AdmissionResult], output_path: Path | str) -> None:
    """Save structured admission results to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [
        {
            "case_id": r.case_id,
            "decision": r.decision.value,
            "limitation_deadline": r.limitation_deadline.isoformat(),
            "applicable_fee": str(r.applicable_fee),
            "paid_fee": str(r.paid_fee),
            "defect_or_rejection_reason": r.defect_or_rejection_reason,
            "required_flags": r.required_flags,
            "cure_deadline": r.cure_deadline.isoformat() if r.cure_deadline else None,
        }
        for r in results
    ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_allocation_results(results: list[AllocationResult], output_path: Path | str) -> None:
    """Save bench allocation results to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [
        {
            "case_id": r.case_id,
            "allocated_bench_id": r.allocated_bench_id,
            "success": r.success,
            "reason": r.reason,
        }
        for r in results
    ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_cause_lists(
    cause_lists: dict[str, list[CauseListEntry]],
    output_path: Path | str,
) -> None:
    """Save generated cause lists to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        bench_id: [
            {
                "case_id": e.case_id,
                "bench_id": e.bench_id,
                "listing_date": e.listing_date.isoformat(),
                "priority_band": e.priority_band.value,
                "position": e.position,
                "carry_over_indicator": e.carry_over_indicator,
                "final_hearing_indicator": e.final_hearing_indicator,
                "flags": e.flags,
            }
            for e in entries
        ]
        for bench_id, entries in cause_lists.items()
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_execution_summary(summary_text: str, output_path: Path | str) -> None:
    """Save execution summary to text file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(summary_text)
