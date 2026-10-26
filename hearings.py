"""Hearing Management module implementing stage progression, adjournments, and next dates.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from config import (
    COMMERCIAL_ADJOURNMENT_COST,
    FLAG_OVERBOARD,
    MAX_ADJOURNMENTS_PER_STAGE,
    MAX_SCHEDULING_LOOKAHEAD_DAYS,
    MIN_NEXT_DATE_INTERVAL_DAYS,
    MIN_NEXT_DATE_URGENT_INTERVAL_DAYS,
    PARTY_ADJOURNMENT_COST,
)
from models import (
    AdjournmentReason,
    Bench,
    Case,
    CaseStage,
    CaseStatus,
    HearingEvent,
    HearingOutcome,
    SubjectType,
)

STAGE_ORDER = [
    CaseStage.PLEADINGS,
    CaseStage.ISSUES,
    CaseStage.EVIDENCE,
    CaseStage.ARGUMENTS,
    CaseStage.JUDGMENT,
]


def calculate_adjournment_cost(subject: SubjectType, prior_party_adjournments: int) -> Decimal:
    """Calculate adjournment cost payable by party (BR-36, BR-37).

    A party adjournment after 2 earlier adjournments (i.e. the 3rd) costs ₹2,000.
    Commercial cases double to ₹4,000.
    """
    if prior_party_adjournments >= 2:
        if subject == SubjectType.COMMERCIAL:
            return COMMERCIAL_ADJOURNMENT_COST
        return PARTY_ADJOURNMENT_COST
    return Decimal("0.00")


def calculate_next_hearing_date(
    bench: Bench,
    from_date: date,
    is_urgent: bool = False,
    holidays: set[date] | None = None,
    board_counts: dict[date, int] | None = None,
) -> tuple[date, bool]:
    """Calculate the next eligible hearing date adhering to BR-39, BR-40, BR-41, and BR-42.

    Returns (next_date, is_overboard).
    """
    holiday_set = holidays or set()
    board = board_counts or {}

    min_interval = MIN_NEXT_DATE_URGENT_INTERVAL_DAYS if is_urgent else MIN_NEXT_DATE_INTERVAL_DAYS
    earliest_date = from_date + timedelta(days=min_interval)
    max_date = from_date + timedelta(days=MAX_SCHEDULING_LOOKAHEAD_DAYS)

    current = earliest_date
    while current <= max_date:
        if (
            current.weekday() in bench.sitting_days
            and current not in bench.leave_dates
            and current not in holiday_set
        ):
            # Check capacity (BR-41)
            if board.get(current, 0) < bench.daily_board_capacity:
                return current, False
        current += timedelta(days=1)

    # Day 60 fallback (BR-42)
    return max_date, True


class HearingManager:
    """Coordinates hearing events, stage progression, adjournment limits and transfers."""

    def __init__(self, benches: list[Bench], holidays: set[date] | None = None) -> None:
        self.benches: dict[str, Bench] = {b.bench_id: b for b in benches}
        self.holidays: set[date] = holidays or set()

    def advance_stage(
        self,
        case: Case,
        target_stage: CaseStage,
        event: HearingEvent,
    ) -> tuple[bool, str]:
        """Advance case stage complying with BR-30 and BR-31."""
        current_idx = STAGE_ORDER.index(case.stage)
        target_idx = STAGE_ORDER.index(target_stage)

        if target_idx <= current_idx:
            return False, f"Target stage {target_stage.value} must follow current stage {case.stage.value}."

        # Stage skipping rule (BR-31): No skipping unless consent is present
        if target_idx > current_idx + 1 and not event.consent_indicator:
            return False, "Cannot skip stages without mutual consent flag."

        case.stage = target_stage
        case.adjournment_history.append(event)

        # Reaching ARGUMENTS sets final hearing priority (BR-32)
        if target_stage == CaseStage.ARGUMENTS:
            case.final_hearing = True

        if target_stage == CaseStage.JUDGMENT and event.outcome == HearingOutcome.DECIDED:
            case.status = CaseStatus.DECIDED

        return True, f"Successfully advanced case to {target_stage.value}."

    def get_party_adjournment_count(
        self,
        case: Case,
        party_id: str | None,
        stage: CaseStage,
    ) -> int:
        """Count party adjournments in the current stage, excluding court-occasioned (BR-35)."""
        count = 0
        for e in case.adjournment_history:
            if (
                e.outcome == HearingOutcome.ADJOURNED
                and e.adjournment_reason != AdjournmentReason.COURT_OCCASIONED
            ):
                if party_id is None or e.requesting_party == party_id:
                    count += 1
        return count

    def process_adjournment(
        self,
        case: Case,
        event: HearingEvent,
    ) -> tuple[bool, str]:
        """Process an adjournment request complying with BR-34 through BR-38."""
        is_court_occasioned = event.adjournment_reason == AdjournmentReason.COURT_OCCASIONED
        is_medical = event.adjournment_reason == AdjournmentReason.MEDICAL

        prior_count = self.get_party_adjournment_count(
            case, party_id=event.requesting_party, stage=case.stage
        )

        # BR-34: Maximum 3 adjournments per party per stage; refuse 4th unless MEDICAL or COURT_OCCASIONED
        if not is_court_occasioned and prior_count >= MAX_ADJOURNMENTS_PER_STAGE and not is_medical:
            return False, f"Maximum {MAX_ADJOURNMENTS_PER_STAGE} adjournments reached for party; 4th refused."

        case.adjournment_history.append(event)
        case.status = CaseStatus.ADJOURNED

        # Calculate cost
        cost = calculate_adjournment_cost(case.subject, prior_count)
        cost_msg = f" Adjournment cost payable: ₹{cost}." if cost > Decimal("0") else ""

        # Calculate next hearing date
        bench = self.benches.get(case.assigned_bench) if case.assigned_bench else None
        if bench:
            next_date, is_overboard = calculate_next_hearing_date(
                bench, from_date=event.hearing_date, is_urgent=case.urgency, holidays=self.holidays
            )
            case.next_hearing_date = next_date
            if is_overboard:
                case.flags.add(FLAG_OVERBOARD)

        return True, f"Adjournment granted.{cost_msg}"
