"""Hearing Management module implementing stage progression, adjournments, and next dates.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from config import (
    COMMERCIAL_ADJOURNMENT_COST,
    COMMERCIAL_CLAIM_THRESHOLD,
    COMMERCIAL_DISPOSAL_TARGET_DAYS,
    EVIDENCE_DELAY_THRESHOLD_DAYS,
    FLAG_COMMERCIAL_OVERDUE,
    FLAG_COST_PAYMENT_PENDING,
    FLAG_DELAY,
    FLAG_EVIDENCE_DELAY,
    FLAG_OVERBOARD,
    FLAG_TRANSFERRED,
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
    SittingSimulationSummary,
    SubjectType,
    TransferResult,
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
    is_commercial_overdue: bool = False,
    holidays: set[date] | None = None,
    board_counts: dict[date, int] | None = None,
) -> tuple[date, bool]:
    """Calculate the next eligible hearing date adhering to BR-25, BR-39, BR-40, BR-41, and BR-42.

    Returns (next_date, is_overboard).
    """
    holiday_set = holidays or set()
    board = board_counts or {}

    # BR-25: Overdue commercial cases (past 12 months) are listed every 7 days until decided.
    # BR-39: Urgent cases interval is 7 days; regular cases interval is 14 days.
    min_interval = MIN_NEXT_DATE_URGENT_INTERVAL_DAYS if (is_urgent or is_commercial_overdue) else MIN_NEXT_DATE_INTERVAL_DAYS
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
            count = board.get((bench.bench_id, current), board.get(current, 0))
            if count < bench.daily_board_capacity:
                return current, False
        current += timedelta(days=1)

    # Day 60 fallback (BR-42): Anchor on Day 60, adjust to next sitting day if on holiday/weekend
    fallback = max_date
    while (
        fallback.weekday() not in bench.sitting_days
        or fallback in bench.leave_dates
        or fallback in holiday_set
    ):
        fallback += timedelta(days=1)
    return fallback, True


class HearingManager:
    """Coordinates hearing events, stage progression, adjournment limits, transfers, and multi-sitting simulations."""

    def __init__(self, benches: list[Bench], holidays: set[date] | None = None) -> None:
        self.benches: dict[str, Bench] = {b.bench_id: b for b in benches}
        self.holidays: set[date] = holidays or set()

    def advance_stage(
        self,
        case: Case,
        target_stage: CaseStage,
        event: HearingEvent,
    ) -> tuple[bool, str]:
        """Advance case stage complying with BR-30, BR-31, BR-32, and BR-33."""
        current_idx = STAGE_ORDER.index(case.stage)
        target_idx = STAGE_ORDER.index(target_stage)

        if target_idx <= current_idx:
            return False, f"Target stage {target_stage.value} must follow current stage {case.stage.value}."

        # Stage skipping rule (BR-31): No skipping unless consent is present
        if target_idx > current_idx + 1 and not event.consent_indicator:
            return False, "Cannot skip stages without mutual consent flag."

        # BR-33: Evidence delay check if transitioning out of or remaining in EVIDENCE
        if case.stage == CaseStage.EVIDENCE and case.stage_start_date:
            days_in_evidence = (event.hearing_date - case.stage_start_date).days
            if days_in_evidence > EVIDENCE_DELAY_THRESHOLD_DAYS:
                case.flags.add(FLAG_DELAY)
                case.flags.add(FLAG_EVIDENCE_DELAY)

        case.stage = target_stage
        case.stage_start_date = event.hearing_date
        if event.stage is None:
            event.stage = target_stage
        case.adjournment_history.append(event)

        # Reaching ARGUMENTS sets final hearing priority (BR-32)
        if target_stage == CaseStage.ARGUMENTS:
            case.final_hearing = True

        if target_stage == CaseStage.JUDGMENT and event.outcome == HearingOutcome.DECIDED:
            case.status = CaseStatus.DECIDED
            case.next_hearing_date = None

        return True, f"Successfully advanced case to {target_stage.value}."

    def get_party_adjournment_count(
        self,
        case: Case,
        party_id: str | None,
        stage: CaseStage | None = None,
    ) -> int:
        """Count party adjournments in the current stage, excluding court-occasioned and systemic reasons (BR-35)."""
        count = 0
        systemic_reasons = {
            AdjournmentReason.COURT_OCCASIONED,
            AdjournmentReason.ROSTER_CHANGE,
            AdjournmentReason.CONFLICT,
        }
        for e in case.adjournment_history:
            if (
                e.outcome == HearingOutcome.ADJOURNED
                and e.adjournment_reason not in systemic_reasons
            ):
                if stage is not None and e.stage is not None and e.stage != stage:
                    continue
                if party_id is None or e.requesting_party == party_id:
                    count += 1
        return count

    def process_adjournment(
        self,
        case: Case,
        event: HearingEvent,
        board_counts: dict[date, int] | None = None,
    ) -> tuple[bool, str]:
        """Process an adjournment request complying with BR-34 through BR-38."""
        if event.stage is None:
            event.stage = case.stage
        is_court_occasioned = event.adjournment_reason == AdjournmentReason.COURT_OCCASIONED
        is_medical = event.adjournment_reason == AdjournmentReason.MEDICAL

        prior_count = self.get_party_adjournment_count(
            case, party_id=event.requesting_party, stage=case.stage
        )

        # BR-34: Maximum 3 adjournments per party per stage; refuse 4th unless MEDICAL or COURT_OCCASIONED
        if not is_court_occasioned and prior_count >= MAX_ADJOURNMENTS_PER_STAGE and not is_medical:
            return False, f"Maximum {MAX_ADJOURNMENTS_PER_STAGE} adjournments reached for party; 4th refused."

        # Calculate cost (BR-36, BR-37, BR-43)
        cost = Decimal("0.00")
        if not is_court_occasioned and not is_medical:
            cost = calculate_adjournment_cost(case.subject, prior_count)

        event.cost_assessed = cost
        case.costs_assessed += cost

        # Payment tracking (BR-38)
        if event.cost_paid:
            case.costs_paid += cost
        elif cost > Decimal("0"):
            case.flags.add(FLAG_COST_PAYMENT_PENDING)

        case.adjournment_history.append(event)
        case.status = CaseStatus.ADJOURNED

        cost_msg = f" Adjournment cost payable: ₹{cost}." if cost > Decimal("0") else ""

        # BR-25: Commercial disposal target check (> 365 days)
        is_comm_overdue = (
            case.subject == SubjectType.COMMERCIAL
            and (event.hearing_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
        )
        if is_comm_overdue:
            case.flags.add(FLAG_COMMERCIAL_OVERDUE)

        # Calculate next hearing date (BR-39, BR-40, BR-41, BR-42)
        bench = self.benches.get(case.assigned_bench) if case.assigned_bench else None
        if bench:
            next_date, is_overboard = calculate_next_hearing_date(
                bench,
                from_date=event.hearing_date,
                is_urgent=case.urgency,
                is_commercial_overdue=is_comm_overdue,
                holidays=self.holidays,
                board_counts=board_counts,
            )
            case.next_hearing_date = next_date
            if board_counts is not None:
                board_counts[(bench.bench_id, next_date)] = board_counts.get((bench.bench_id, next_date), 0) + 1
                board_counts[next_date] = board_counts.get(next_date, 0) + 1
            if is_overboard:
                case.flags.add(FLAG_OVERBOARD)

        return True, f"Adjournment granted.{cost_msg}"

    def pay_adjournment_cost(self, case: Case, amount: Decimal) -> Decimal:
        """Record payment towards outstanding adjournment costs (BR-38)."""
        case.costs_paid += amount
        if case.costs_paid >= case.costs_assessed:
            case.flags.discard(FLAG_COST_PAYMENT_PENDING)
        return case.costs_paid

    def transfer_case(
        self,
        case: Case,
        destination_bench_id: str | None,
        reason: AdjournmentReason | str,
        event_date: date,
        board_counts: dict[date, int] | None = None,
    ) -> TransferResult:
        """Execute a case transfer adhering to BR-44, BR-45, BR-46, BR-47, and BR-48."""
        old_bench_id = case.assigned_bench

        # BR-44: Transfer at most once
        if case.transferred_count >= 1:
            return TransferResult(
                case_id=case.case_id,
                from_bench_id=old_bench_id,
                to_bench_id=destination_bench_id,
                success=False,
                reason="Case has reached the maximum lifetime transfer limit of 1.",
            )

        # BR-44: Reason must be ROSTER_CHANGE or CONFLICT
        reason_str = reason.value if isinstance(reason, AdjournmentReason) else str(reason).upper()
        if reason_str not in ("ROSTER_CHANGE", "CONFLICT"):
            return TransferResult(
                case_id=case.case_id,
                from_bench_id=old_bench_id,
                to_bench_id=destination_bench_id,
                success=False,
                reason=f"Transfer refused: invalid reason '{reason_str}'. Permitted reasons are ROSTER_CHANGE or CONFLICT.",
            )
        reason_enum = AdjournmentReason(reason_str)

        # BR-45: Destination eligibility check
        if not destination_bench_id:
            # Auto-find eligible destination bench
            eligible = [
                b for b in self.benches.values()
                if b.bench_id != old_bench_id
                and case.subject in b.subject_jurisdictions
                and not any(p in b.conflict_party_ids for p in case.party_ids)
                and (not (case.subject == SubjectType.COMMERCIAL and case.claim_value > COMMERCIAL_CLAIM_THRESHOLD) or b.commercial_jurisdiction)
            ]
            if not eligible:
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=None,
                    success=False,
                    reason="No eligible destination bench found for transfer.",
                )
            dest_bench = sorted(eligible, key=lambda b: b.bench_id)[0]
        else:
            dest_bench = self.benches.get(destination_bench_id)
            if not dest_bench:
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=destination_bench_id,
                    success=False,
                    reason=f"Destination bench '{destination_bench_id}' does not exist.",
                )
            if dest_bench.bench_id == old_bench_id:
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=destination_bench_id,
                    success=False,
                    reason="Destination bench cannot be the same as the current assigned bench.",
                )
            if case.subject not in dest_bench.subject_jurisdictions:
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=dest_bench.bench_id,
                    success=False,
                    reason=f"Destination bench '{dest_bench.bench_id}' lacks jurisdiction for subject {case.subject.value}.",
                )
            if case.subject == SubjectType.COMMERCIAL and case.claim_value > COMMERCIAL_CLAIM_THRESHOLD and not dest_bench.commercial_jurisdiction:
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=dest_bench.bench_id,
                    success=False,
                    reason=f"Commercial claim {case.claim_value} exceeds threshold but destination bench is not a commercial bench.",
                )
            # Conflict check against all case parties (BR-45)
            if any(p in dest_bench.conflict_party_ids for p in case.party_ids):
                return TransferResult(
                    case_id=case.case_id,
                    from_bench_id=old_bench_id,
                    to_bench_id=dest_bench.bench_id,
                    success=False,
                    reason=f"Destination bench '{dest_bench.bench_id}' has party conflict with case parties.",
                )

        # BR-46: Preserve case stage and history
        # BR-47: Count transfer as an adjournment
        transfer_event = HearingEvent(
            event_id=f"TRF-{case.case_id}-{case.transferred_count + 1}",
            case_id=case.case_id,
            hearing_date=event_date,
            outcome=HearingOutcome.TRANSFERRED,
            adjournment_reason=reason_enum,
            target_bench_id=dest_bench.bench_id,
            stage=case.stage,
            notes=f"Transferred from {old_bench_id} to {dest_bench.bench_id} due to {reason_str}",
        )
        case.adjournment_history.append(transfer_event)

        # BR-48: Recompute next hearing date using destination bench calendar
        is_comm_overdue = (
            case.subject == SubjectType.COMMERCIAL
            and (event_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
        )
        next_date, is_overboard = calculate_next_hearing_date(
            dest_bench,
            from_date=event_date,
            is_urgent=case.urgency,
            is_commercial_overdue=is_comm_overdue,
            holidays=self.holidays,
            board_counts=board_counts,
        )
        case.next_hearing_date = next_date
        if board_counts is not None:
            board_counts[(dest_bench.bench_id, next_date)] = board_counts.get((dest_bench.bench_id, next_date), 0) + 1
            board_counts[next_date] = board_counts.get(next_date, 0) + 1
        if is_overboard:
            case.flags.add(FLAG_OVERBOARD)

        case.assigned_bench = dest_bench.bench_id
        case.transferred_count += 1
        case.status = CaseStatus.TRANSFERRED
        case.flags.add(FLAG_TRANSFERRED)

        return TransferResult(
            case_id=case.case_id,
            from_bench_id=old_bench_id,
            to_bench_id=dest_bench.bench_id,
            success=True,
            reason="Case successfully transferred.",
            next_hearing_date=next_date,
        )

    def process_hearing_event(
        self,
        case: Case,
        event: HearingEvent,
        board_counts: dict[date, int] | None = None,
    ) -> tuple[bool, str]:
        """Dispatch and process any hearing outcome (BR-29 to BR-38, BR-44 to BR-48)."""
        # Ensure stage start date initialized
        if case.stage_start_date is None:
            case.stage_start_date = case.filing_date

        # Check evidence delay if in EVIDENCE stage
        if case.stage == CaseStage.EVIDENCE and (event.hearing_date - case.stage_start_date).days > EVIDENCE_DELAY_THRESHOLD_DAYS:
            case.flags.add(FLAG_DELAY)
            case.flags.add(FLAG_EVIDENCE_DELAY)

        if event.outcome == HearingOutcome.HEARD:
            if event.new_stage and event.new_stage != case.stage:
                success, msg = self.advance_stage(case, event.new_stage, event)
                if not success:
                    return False, msg
            else:
                case.adjournment_history.append(event)

            case.status = CaseStatus.HEARD
            case.is_part_heard = False

            # Recalculate next date if case is not decided
            if case.status != CaseStatus.DECIDED and case.assigned_bench:
                bench = self.benches.get(case.assigned_bench)
                if bench:
                    is_comm_overdue = (
                        case.subject == SubjectType.COMMERCIAL
                        and (event.hearing_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
                    )
                    next_date, is_overboard = calculate_next_hearing_date(
                        bench,
                        from_date=event.hearing_date,
                        is_urgent=case.urgency,
                        is_commercial_overdue=is_comm_overdue,
                        holidays=self.holidays,
                        board_counts=board_counts,
                    )
                    case.next_hearing_date = next_date
                    if is_overboard:
                        case.flags.add(FLAG_OVERBOARD)
            return True, "Hearing recorded."

        elif event.outcome == HearingOutcome.PART_HEARD:
            case.is_part_heard = True
            case.adjournment_history.append(event)
            case.status = CaseStatus.HEARD
            if case.assigned_bench:
                bench = self.benches.get(case.assigned_bench)
                if bench:
                    # Part-heard matters get listed on earliest sitting day
                    earliest_sitting = event.hearing_date + timedelta(days=1)
                    while (
                        earliest_sitting.weekday() not in bench.sitting_days
                        or earliest_sitting in bench.leave_dates
                        or earliest_sitting in self.holidays
                    ):
                        earliest_sitting += timedelta(days=1)
                    case.next_hearing_date = earliest_sitting
            return True, "Part-heard hearing recorded."

        elif event.outcome == HearingOutcome.ADJOURNED:
            return self.process_adjournment(case, event, board_counts=board_counts)

        elif event.outcome == HearingOutcome.DECIDED:
            case.adjournment_history.append(event)
            case.stage = CaseStage.JUDGMENT
            case.status = CaseStatus.DECIDED
            case.next_hearing_date = None
            return True, "Case decided."

        elif event.outcome == HearingOutcome.TRANSFERRED:
            target_bench = event.target_bench_id
            reason = event.adjournment_reason or AdjournmentReason.ROSTER_CHANGE
            tr_res = self.transfer_case(case, target_bench, reason, event.hearing_date, board_counts=board_counts)
            return tr_res.success, tr_res.reason

        return False, f"Unsupported hearing outcome: {event.outcome}"

    def simulate_sittings(
        self,
        cases: list[Case],
        events: list[HearingEvent],
        sitting_dates: list[date],
    ) -> tuple[list[SittingSimulationSummary], dict[str, list[CauseListEntry]]]:
        """Simulate court proceedings across consecutive court sitting dates (BR-29 to BR-38)."""
        from scheduling import generate_cause_list

        events_by_case_and_date: dict[tuple[str, date], HearingEvent] = {
            (e.case_id, e.hearing_date): e for e in events
        }
        cases_by_id = {c.case_id: c for c in cases}

        all_summaries: list[SittingSimulationSummary] = []
        all_cause_lists: dict[str, list[CauseListEntry]] = {}
        board_counts: dict[date, int] = {}

        for sit_date in sorted(sitting_dates):
            # Skip if weekend or court holiday
            if sit_date.weekday() >= 5 or sit_date in self.holidays:
                continue

            for bench_id, bench in sorted(self.benches.items()):
                # Skip if bench not sitting on this weekday or on leave
                if sit_date.weekday() not in bench.sitting_days or sit_date in bench.leave_dates:
                    continue

                # Get eligible cases assigned to this bench
                bench_cases = [
                    c for c in cases
                    if c.assigned_bench == bench_id
                    and c.status not in (CaseStatus.DECIDED, CaseStatus.REJECTED, CaseStatus.RETURNED)
                    and (c.next_hearing_date is None or c.next_hearing_date <= sit_date or c.carry_over_count > 0)
                ]

                cl_entries, unreached = generate_cause_list(bench, bench_cases, sit_date)
                key = f"{bench_id}_{sit_date.isoformat()}"
                all_cause_lists[key] = cl_entries

                board_counts[(bench_id, sit_date)] = len(cl_entries)
                board_counts[sit_date] = board_counts.get(sit_date, 0) + len(cl_entries)

                events_proc = 0
                heard_cnt = 0
                adj_cnt = 0
                dec_cnt = 0
                trf_cnt = 0

                for entry in cl_entries:
                    case = cases_by_id.get(entry.case_id)
                    if not case:
                        continue

                    # Check if there is an event for this case on this sitting date
                    event = events_by_case_and_date.get((case.case_id, sit_date))
                    if event:
                        events_proc += 1
                        self.process_hearing_event(case, event, board_counts=board_counts)
                        if event.outcome == HearingOutcome.HEARD:
                            heard_cnt += 1
                        elif event.outcome == HearingOutcome.ADJOURNED:
                            adj_cnt += 1
                        elif event.outcome == HearingOutcome.DECIDED:
                            dec_cnt += 1
                        elif event.outcome == HearingOutcome.TRANSFERRED:
                            trf_cnt += 1

                summary = SittingSimulationSummary(
                    sitting_date=sit_date,
                    bench_id=bench_id,
                    matters_listed=len(cl_entries),
                    events_processed=events_proc,
                    matters_heard=heard_cnt,
                    matters_adjourned=adj_cnt,
                    matters_decided=dec_cnt,
                    matters_transferred=trf_cnt,
                )
                all_summaries.append(summary)

        return all_summaries, all_cause_lists
