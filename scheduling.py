"""Cause-List Generation and Scheduling module complying with BR-19 through BR-28.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from config import (
    COMMERCIAL_DISPOSAL_TARGET_DAYS,
    DAILY_BOARD_CAPACITY,
    DAILY_FINAL_HEARING_CAP,
    FLAG_CARRIED_OVER,
    FLAG_ESCALATED,
    FLAG_IN_CAMERA,
    UNREACHED_ESCALATION_THRESHOLD,
    URGENT_MENTION_CUTOFF_TIME,
)
from models import (
    Bench,
    Case,
    CaseStage,
    CaseStatus,
    CauseListEntry,
    PriorityBand,
    SubjectType,
)


@dataclass
class ScheduleUrgentResult:
    case_id: str
    scheduled_date: date
    position: int
    listed_same_day: bool
    reason: str


def get_next_sitting_day(
    bench: Bench,
    from_date: date,
    holidays: set[date] | None = None,
) -> date:
    """Find the next eligible sitting day for a bench skipping holidays and bench leave (BR-40)."""
    holiday_set = holidays or set()
    current = from_date + timedelta(days=1)
    while (
        current.weekday() not in bench.sitting_days
        or current in bench.leave_dates
        or current in holiday_set
    ):
        current += timedelta(days=1)
    return current


def determine_priority_band(case: Case, listing_date: date) -> PriorityBand:
    """Determine priority band (1 through 6) according to BR-19, BR-24, BR-25, and BR-32."""
    # BR-25: Commercial case past 12 months target overrides ordinary priorities
    if case.subject == SubjectType.COMMERCIAL and (listing_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS:
        base_band = PriorityBand.BAND_1_URGENT
    # BR-19 Band 1: Urgent / bail matters
    elif case.urgency:
        base_band = PriorityBand.BAND_1_URGENT
    # BR-19 Band 2: Part-heard matters
    elif case.is_part_heard:
        base_band = PriorityBand.BAND_2_PART_HEARD
    # BR-19 Band 3: Cases with 3 or more adjournments
    elif len(case.adjournment_history) >= 3:
        base_band = PriorityBand.BAND_3_THREE_PLUS_ADJOURNMENTS
    # BR-19 Band 4: Cases older than 2 years (approx 730 days)
    elif (listing_date - case.filing_date).days >= 730:
        base_band = PriorityBand.BAND_4_OLDER_THAN_TWO_YEARS
    # BR-19 Band 5: Final-hearing-stage matters (BR-32: reaching ARGUMENTS gives final-hearing priority)
    elif case.stage == CaseStage.ARGUMENTS or case.final_hearing:
        base_band = PriorityBand.BAND_5_FINAL_HEARING
    # BR-19 Band 6: All other cases
    else:
        base_band = PriorityBand.BAND_6_REGULAR

    # BR-24: Unreached on 3 consecutive sittings moves up one band
    if case.consecutive_unreached_count >= UNREACHED_ESCALATION_THRESHOLD:
        escalated_val = max(1, base_band.value - 1)
        return PriorityBand(escalated_val)

    return base_band


def generate_cause_list(
    bench: Bench,
    cases: list[Case],
    listing_date: date,
) -> tuple[list[CauseListEntry], list[Case]]:
    """Generate deterministic cause list for a bench on a specific sitting day.

    Complying with:
    - BR-19 (Priority bands)
    - BR-20 (Oldest filing date first within band)
    - BR-21 (Daily board capacity <= 40)
    - BR-22 (Final-hearing cap <= 8)
    - BR-23 (Carry-over matters go first within band)
    - BR-24 (Priority escalation)
    - BR-26 (Family matters involving minor on designated days only)

    Returns (cause_list_entries, unreached_cases).
    """
    cause_list: list[CauseListEntry] = []
    unreached: list[Case] = []

    # Filter to cases assigned to this bench that are eligible for listing
    bench_cases = [c for c in cases if c.assigned_bench == bench.bench_id]

    # Pre-sort: assign priority band and sort tuples:
    # 1. priority_band (ascending, 1 to 6)
    # 2. carry_over_indicator (carry-over cases first, so carry_over_count > 0 -> 0, else 1)
    # 3. filing_date (oldest first)
    # 4. case_id (deterministic tie-breaker)
    case_entries = []
    for c in bench_cases:
        band = determine_priority_band(c, listing_date)
        is_carry = c.carry_over_count > 0
        is_escalated = c.consecutive_unreached_count >= UNREACHED_ESCALATION_THRESHOLD
        case_entries.append((band, 0 if is_carry else 1, c.filing_date, c.case_id, c, is_escalated))

    case_entries.sort(key=lambda t: (t[0].value, t[1], t[2], t[3]))

    final_hearing_count = 0
    capacity_limit = bench.daily_board_capacity

    for band, _, _, _, c, is_escalated in case_entries:
        # Check BR-26: Family cases involving minor only on designated days
        if c.subject == SubjectType.FAMILY and c.involves_minor:
            if listing_date.weekday() not in bench.designated_family_hearing_days:
                # Cannot be listed today
                c.carry_over_count += 1
                c.consecutive_unreached_count += 1
                unreached.append(c)
                continue

        is_final = (c.stage == CaseStage.ARGUMENTS or c.final_hearing or band == PriorityBand.BAND_5_FINAL_HEARING)

        # Check BR-22: Final-hearing cap (max 8)
        if is_final and final_hearing_count >= DAILY_FINAL_HEARING_CAP:
            c.carry_over_count += 1
            c.consecutive_unreached_count += 1
            unreached.append(c)
            continue

        # Check BR-21: Daily board capacity (max 40)
        if len(cause_list) >= capacity_limit:
            c.carry_over_count += 1
            c.consecutive_unreached_count += 1
            unreached.append(c)
            continue

        # Can be listed!
        if is_final:
            final_hearing_count += 1

        entry_flags: list[str] = list(c.flags)
        if c.carry_over_count > 0 and FLAG_CARRIED_OVER not in entry_flags:
            entry_flags.append(FLAG_CARRIED_OVER)
        if is_escalated and FLAG_ESCALATED not in entry_flags:
            entry_flags.append(FLAG_ESCALATED)
        if c.subject == SubjectType.FAMILY and c.involves_minor and FLAG_IN_CAMERA not in entry_flags:
            entry_flags.append(FLAG_IN_CAMERA)

        position = len(cause_list) + 1
        entry = CauseListEntry(
            case_id=c.case_id,
            bench_id=bench.bench_id,
            listing_date=listing_date,
            priority_band=band,
            position=position,
            carry_over_indicator=(c.carry_over_count > 0),
            final_hearing_indicator=is_final,
            flags=entry_flags,
        )
        cause_list.append(entry)

        # Update case lifecycle attributes
        c.status = CaseStatus.LISTED
        c.next_hearing_date = listing_date
        c.consecutive_unreached_count = 0  # Reached, reset consecutive unreached count

    return cause_list, unreached


def schedule_urgent_mention(
    case: Case,
    bench: Bench,
    current_date: date,
    mentioned_at: str,
    current_board_size: int,
    holidays: set[date] | None = None,
) -> ScheduleUrgentResult:
    """Schedule an urgent/bail matter mentioned on a sitting day (BR-27)."""
    # Mentioned before 10:30
    if mentioned_at < URGENT_MENTION_CUTOFF_TIME:
        if current_board_size < bench.daily_board_capacity:
            position = current_board_size + 1
            case.status = CaseStatus.LISTED
            case.next_hearing_date = current_date
            return ScheduleUrgentResult(
                case_id=case.case_id,
                scheduled_date=current_date,
                position=position,
                listed_same_day=True,
                reason="Mentioned before 10:30 and board capacity available; listed same day.",
            )
        else:
            # Board full -> next sitting day at position 1
            next_date = get_next_sitting_day(bench, current_date, holidays)
            case.status = CaseStatus.LISTED
            case.next_hearing_date = next_date
            return ScheduleUrgentResult(
                case_id=case.case_id,
                scheduled_date=next_date,
                position=1,
                listed_same_day=False,
                reason="Mentioned before 10:30 but board full (40 matters); listed next sitting day at position 1.",
            )
    else:
        # Mentioned at or after 10:30 -> next sitting day
        next_date = get_next_sitting_day(bench, current_date, holidays)
        case.status = CaseStatus.LISTED
        case.next_hearing_date = next_date
        return ScheduleUrgentResult(
            case_id=case.case_id,
            scheduled_date=next_date,
            position=1,
            listed_same_day=False,
            reason="Mentioned at or after 10:30 cutoff; listed on next sitting day.",
        )
