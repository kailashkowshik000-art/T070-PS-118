"""Case Admission module implementing limitation checks and court fee scrutiny.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import calendar

from config import (
    CIVIL_LIMITATION_YEARS,
    MONEY_RECOVERY_LIMITATION_YEARS,
    APPEAL_LIMITATION_DAYS,
    REVISION_LIMITATION_DAYS,
    FEE_BAND_1_THRESHOLD,
    FEE_BAND_1_RATE,
    FEE_BAND_2_THRESHOLD,
    FEE_BAND_2_RATE,
    FEE_BAND_3_RATE,
    FEE_CAP,
    APPEAL_FEE_FACTOR,
    FEE_CURE_PERIOD_DAYS,
    FLAG_DELAY_CONDONATION_PENDING,
    FLAG_DEFECTIVE,
    FLAG_FEE_DEFICIENT,
)
from models import (
    AdmissionDecision,
    AdmissionResult,
    Case,
    CaseStatus,
)


def add_years(d: date, years: int) -> date:
    """Add years to date, handling leap year Feb 29 gracefully."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # Occurs when d is Feb 29 and target year is not a leap year
        return d.replace(year=d.year + years, day=28)


def adjust_for_holidays_and_weekends(target_date: date, holidays: set[date] | None = None) -> date:
    """Extend deadline to next working day if it falls on weekend or court holiday (BR-09)."""
    holiday_set = holidays or set()
    current = target_date
    while current.weekday() >= 5 or current in holiday_set:
        current += timedelta(days=1)
    return current


def calculate_limitation_deadline(
    case_type: str,
    base_date: date,
    wrong_forum_days: int = 0,
    holidays: set[date] | None = None,
) -> date:
    """Calculate the final limitation deadline including wrong-forum exclusion and holiday extension.

    Rules applied: BR-07, BR-08, BR-09
    """
    case_type_upper = case_type.upper()
    if "APPEAL" in case_type_upper:
        raw_deadline = base_date + timedelta(days=APPEAL_LIMITATION_DAYS)
    elif "REVISION" in case_type_upper:
        raw_deadline = base_date + timedelta(days=REVISION_LIMITATION_DAYS)
    elif "MONEY" in case_type_upper or "RECOVERY" in case_type_upper:
        raw_deadline = add_years(base_date, MONEY_RECOVERY_LIMITATION_YEARS)
    else:
        # Default civil suit limitation is 3 years
        raw_deadline = add_years(base_date, CIVIL_LIMITATION_YEARS)

    # Exclude time spent in wrong forum (BR-08)
    if wrong_forum_days > 0:
        raw_deadline += timedelta(days=wrong_forum_days)

    # Extend if falling on holiday or weekend (BR-09)
    return adjust_for_holidays_and_weekends(raw_deadline, holidays)


def calculate_court_fee(claim_value: Decimal, is_appeal: bool = False) -> Decimal:
    """Calculate progressive court fee with marginal bands and cap.

    Rules applied: BR-13, BR-14, BR-15, BR-18
    - 5% up to 1,00,000
    - 4% above 1,00,000 up to 10,00,000
    - 2% above 10,00,000
    - Cap at 3,00,000
    - Appeals pay 50%
    """
    if claim_value <= Decimal("0"):
        return Decimal("0.00")

    fee = Decimal("0.00")

    # Band 1: Up to 1,00,000 (5%)
    band1_portion = min(claim_value, FEE_BAND_1_THRESHOLD)
    fee += band1_portion * FEE_BAND_1_RATE

    # Band 2: Portion from 1,00,000 to 10,00,000 (4%)
    if claim_value > FEE_BAND_1_THRESHOLD:
        band2_portion = min(claim_value, FEE_BAND_2_THRESHOLD) - FEE_BAND_1_THRESHOLD
        fee += band2_portion * FEE_BAND_2_RATE

    # Band 3: Portion above 10,00,000 (2%)
    if claim_value > FEE_BAND_2_THRESHOLD:
        band3_portion = claim_value - FEE_BAND_2_THRESHOLD
        fee += band3_portion * FEE_BAND_3_RATE

    # Cap at 3,00,000 (BR-14)
    fee = min(fee, FEE_CAP)

    # Appeals pay 50% (BR-15)
    if is_appeal:
        fee = fee * APPEAL_FEE_FACTOR

    return fee.quantize(Decimal("0.01"))


def process_admission(case: Case, holidays: set[date] | None = None) -> AdmissionResult:
    """Process a case through the admission workflow.

    Rules applied: BR-07 through BR-18.
    Order: Limitation -> Condonation check -> Court fee calculation -> Defect handling.
    """
    # Determine base date: order_date for appeals/revisions, cause_of_action_date for suits
    base_date = case.order_date or case.cause_of_action_date or case.filing_date
    limitation_deadline = calculate_limitation_deadline(
        case_type=case.case_type,
        base_date=base_date,
        wrong_forum_days=case.wrong_forum_days,
        holidays=holidays,
    )

    applicable_fee = calculate_court_fee(case.claim_value, is_appeal=case.is_appeal)
    required_flags: list[str] = list(case.flags)

    # Check limitation
    is_late = case.filing_date > limitation_deadline
    if is_late:
        if not case.has_condonation_application:
            case.status = CaseStatus.REJECTED
            return AdmissionResult(
                case_id=case.case_id,
                decision=AdmissionDecision.REJECTED,
                limitation_deadline=limitation_deadline,
                applicable_fee=applicable_fee,
                paid_fee=case.court_fee_paid,
                defect_or_rejection_reason="Filing is time-barred and lacks delay condonation application.",
                required_flags=required_flags,
            )
        else:
            if FLAG_DELAY_CONDONATION_PENDING not in required_flags:
                required_flags.append(FLAG_DELAY_CONDONATION_PENDING)
            case.flags.add(FLAG_DELAY_CONDONATION_PENDING)

    # Check fee sufficiency
    if case.court_fee_paid < applicable_fee:
        cure_deadline = case.filing_date + timedelta(days=FEE_CURE_PERIOD_DAYS)
        if FLAG_DEFECTIVE not in required_flags:
            required_flags.append(FLAG_DEFECTIVE)
        if FLAG_FEE_DEFICIENT not in required_flags:
            required_flags.append(FLAG_FEE_DEFICIENT)
        case.flags.add(FLAG_DEFECTIVE)
        case.flags.add(FLAG_FEE_DEFICIENT)
        case.status = CaseStatus.DEFECTIVE
        case.cure_deadline = cure_deadline
        return AdmissionResult(
            case_id=case.case_id,
            decision=AdmissionDecision.DEFECTIVE,
            limitation_deadline=limitation_deadline,
            applicable_fee=applicable_fee,
            paid_fee=case.court_fee_paid,
            defect_or_rejection_reason=f"Deficient court fee paid: {case.court_fee_paid} < {applicable_fee}.",
            required_flags=required_flags,
            cure_deadline=cure_deadline,
        )

    # Admitted
    case.status = CaseStatus.ADMITTED
    return AdmissionResult(
        case_id=case.case_id,
        decision=AdmissionDecision.ADMITTED,
        limitation_deadline=limitation_deadline,
        applicable_fee=applicable_fee,
        paid_fee=case.court_fee_paid,
        defect_or_rejection_reason=None,
        required_flags=required_flags,
        cure_deadline=None,
    )


def check_cure_status(case: Case, current_date: date) -> AdmissionDecision:
    """Check whether a defective filing was cured within 7 days (BR-17)."""
    if case.status == CaseStatus.DEFECTIVE:
        if case.cure_deadline and current_date > case.cure_deadline:
            case.status = CaseStatus.RETURNED
            return AdmissionDecision.RETURNED
        return AdmissionDecision.DEFECTIVE
    return AdmissionDecision(case.status.value)
