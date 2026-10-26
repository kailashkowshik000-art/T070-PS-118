"""Bench Allocation module for assigning cases to eligible judicial benches.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from config import COMMERCIAL_CLAIM_THRESHOLD
from models import (
    AllocationResult,
    Bench,
    Case,
    CaseStatus,
    SubjectType,
)


class BenchAllocator:
    """Manages deterministic round-robin bench allocation complying with BR-01 through BR-06."""

    def __init__(self, benches: list[Bench]) -> None:
        # Sort benches by bench_id to guarantee deterministic ordering
        self.benches: list[Bench] = sorted(benches, key=lambda b: b.bench_id)
        # Track round-robin index per subject/roster key
        self._roster_indices: dict[str, int] = {}

    def get_eligible_benches(
        self,
        subject: SubjectType,
        party_ids: list[str],
        claim_value: Decimal = Decimal("0"),
        on_date: date | None = None,
    ) -> list[Bench]:
        """Filter benches by subject jurisdiction, commercial threshold, party conflicts, and calendar."""
        eligible: list[Bench] = []

        requires_commercial_bench = (
            subject == SubjectType.COMMERCIAL and claim_value > COMMERCIAL_CLAIM_THRESHOLD
        )

        for bench in self.benches:
            # Check subject jurisdiction
            if subject not in bench.subject_jurisdictions:
                continue

            # Check commercial bench requirement (BR-03)
            if requires_commercial_bench and not bench.commercial_jurisdiction:
                continue

            # Check party conflicts (BR-04)
            has_conflict = any(party in bench.conflict_party_ids for party in party_ids)
            if has_conflict:
                continue

            # Check sitting day and leave if a specific date is given
            if on_date is not None:
                if on_date in bench.leave_dates:
                    continue
                if on_date.weekday() not in bench.sitting_days:
                    continue

            eligible.append(bench)

        return sorted(eligible, key=lambda b: b.bench_id)

    def allocate(self, case: Case, on_date: date | None = None) -> AllocationResult:
        """Allocate a case to an eligible bench using deterministic round-robin (BR-05)."""
        eligible = self.get_eligible_benches(
            subject=case.subject,
            party_ids=case.party_ids,
            claim_value=case.claim_value,
            on_date=on_date,
        )

        if not eligible:
            # Diagnose specific reason for unallocated status (BR-06)
            requires_commercial_bench = (
                case.subject == SubjectType.COMMERCIAL
                and case.claim_value > COMMERCIAL_CLAIM_THRESHOLD
            )
            subject_matches = [b for b in self.benches if case.subject in b.subject_jurisdictions]
            if not subject_matches:
                reason = f"No eligible bench: no bench has subject jurisdiction for {case.subject.value}."
            elif requires_commercial_bench and not any(b.commercial_jurisdiction for b in subject_matches):
                reason = (
                    f"No eligible bench: commercial claim {case.claim_value} exceeds "
                    f"threshold {COMMERCIAL_CLAIM_THRESHOLD} but no commercial bench exists."
                )
            elif any(
                any(p in b.conflict_party_ids for p in case.party_ids) for b in subject_matches
            ):
                reason = "No eligible bench: all subject-eligible benches have party conflicts."
            elif on_date is not None and all(
                (on_date in b.leave_dates or on_date.weekday() not in b.sitting_days)
                for b in subject_matches
            ):
                reason = f"No eligible bench: all benches are on leave or not sitting on {on_date}."
            else:
                reason = "No eligible bench available matching criteria."

            return AllocationResult(
                case_id=case.case_id,
                allocated_bench_id=None,
                success=False,
                reason=reason,
            )

        # Build roster key
        roster_key = case.subject.value
        if case.subject == SubjectType.COMMERCIAL and case.claim_value > COMMERCIAL_CLAIM_THRESHOLD:
            roster_key += "_COMMERCIAL_SPECIAL"

        # Determine round-robin index
        current_index = self._roster_indices.get(roster_key, -1)
        next_index = (current_index + 1) % len(eligible)
        self._roster_indices[roster_key] = next_index

        chosen_bench = eligible[next_index]
        case.assigned_bench = chosen_bench.bench_id
        case.status = CaseStatus.ALLOCATED

        return AllocationResult(
            case_id=case.case_id,
            allocated_bench_id=chosen_bench.bench_id,
            success=True,
            reason=None,
        )
