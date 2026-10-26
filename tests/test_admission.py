"""Unit tests for Case Admission module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from config import (
    FLAG_DELAY_CONDONATION_PENDING,
    FLAG_DEFECTIVE,
    FLAG_FEE_DEFICIENT,
)
from models import (
    AdmissionDecision,
    Case,
    CaseStatus,
    SubjectType,
)
from admission import (
    calculate_court_fee,
    calculate_limitation_deadline,
    process_admission,
    check_cure_status,
)


class TestAdmissionModule(unittest.TestCase):
    def setUp(self):
        # Sample court holidays
        self.holidays = {
            date(2026, 1, 26),  # Republic Day
            date(2026, 8, 15),  # Independence Day
            date(2026, 10, 2),  # Gandhi Jayanti
            date(2026, 10, 20), # Dussehra
            date(2026, 11, 8),  # Diwali
        }

    # ==========================================
    # Limitation Period Tests (BR-07, BR-08, BR-09, BR-10, BR-11)
    # ==========================================

    def test_civil_suit_limitation_three_years(self):
        """Civil suit limitation is 3 years from cause of action date."""
        cause_date = date(2023, 3, 15)
        # 3 years later: 2026-03-15 (Sunday -> next working day Monday 2026-03-16)
        deadline = calculate_limitation_deadline(
            case_type="CIVIL_SUIT",
            base_date=cause_date,
            wrong_forum_days=0,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 3, 16))

    def test_money_recovery_limitation_three_years(self):
        """Money recovery limitation is 3 years from due date."""
        due_date = date(2023, 5, 10) # Wednesday -> 2026-05-10 Sunday -> Monday 2026-05-11
        deadline = calculate_limitation_deadline(
            case_type="MONEY_RECOVERY",
            base_date=due_date,
            wrong_forum_days=0,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 5, 11))

    def test_appeal_limitation_thirty_days(self):
        """Appeal limitation is 30 days from order date."""
        order_date = date(2026, 1, 1)
        # 30 days later: 2026-01-31 (Saturday -> Sunday 2026-02-01 -> Monday 2026-02-02)
        deadline = calculate_limitation_deadline(
            case_type="CIVIL_APPEAL",
            base_date=order_date,
            wrong_forum_days=0,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 2, 2))

    def test_revision_limitation_ninety_days(self):
        """Revision limitation is 90 days from order date."""
        order_date = date(2026, 1, 1)
        # 90 days later: 2026-04-01 (Wednesday, not holiday)
        deadline = calculate_limitation_deadline(
            case_type="CIVIL_REVISION",
            base_date=order_date,
            wrong_forum_days=0,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 4, 1))

    def test_wrong_forum_exclusion(self):
        """Excludes qualifying time spent pursuing matter in wrong forum (BR-08)."""
        order_date = date(2026, 1, 1)
        # Appeal: 30 days + 15 days wrong forum = 45 days -> 2026-02-15 (Sunday -> 2026-02-16 Monday)
        deadline = calculate_limitation_deadline(
            case_type="CIVIL_APPEAL",
            base_date=order_date,
            wrong_forum_days=15,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 2, 16))

    def test_holiday_deadline_adjustment(self):
        """Deadline falling on holiday/weekend extends to next working day (BR-09)."""
        # Order date: 2026-09-02 + 30 days = 2026-10-02 (Gandhi Jayanti holiday)
        # 2026-10-02 is Friday (holiday), 2026-10-03 is Saturday, 2026-10-04 is Sunday -> Monday 2026-10-05
        deadline = calculate_limitation_deadline(
            case_type="APPEAL",
            base_date=date(2026, 9, 2),
            wrong_forum_days=0,
            holidays=self.holidays,
        )
        self.assertEqual(deadline, date(2026, 10, 5))

    def test_late_filing_without_condonation_rejected(self):
        """Late filing without condonation application is rejected (BR-11)."""
        case = Case(
            case_id="C-001",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 6, 1),
            cause_of_action_date=date(2022, 1, 1), # deadline was ~2025-01-01
            claim_value=Decimal("50000"),
            court_fee_paid=Decimal("2500"),
            has_condonation_application=False,
        )
        result = process_admission(case, holidays=self.holidays)
        self.assertEqual(result.decision, AdmissionDecision.REJECTED)
        self.assertIn("condonation", result.defect_or_rejection_reason.lower())

    def test_late_filing_with_condonation_flagged(self):
        """Late filing with condonation is admitted pending condonation (BR-10)."""
        case = Case(
            case_id="C-002",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 6, 1),
            cause_of_action_date=date(2022, 1, 1),
            claim_value=Decimal("50000"),
            court_fee_paid=Decimal("2500"),
            has_condonation_application=True,
        )
        result = process_admission(case, holidays=self.holidays)
        self.assertEqual(result.decision, AdmissionDecision.ADMITTED)
        self.assertIn(FLAG_DELAY_CONDONATION_PENDING, result.required_flags)

    # ==========================================
    # Court Fee Tests (BR-13, BR-14, BR-15, BR-16, BR-17, BR-18)
    # ==========================================

    def test_fee_band_1_boundary_one_lakh(self):
        """5% up to 1,00,000. Boundary at exactly 1,00,000 -> 5,000."""
        fee = calculate_court_fee(Decimal("100000"))
        self.assertEqual(fee, Decimal("5000.00"))

    def test_fee_band_1_below_one_lakh(self):
        """5% of 50,000 -> 2,500."""
        fee = calculate_court_fee(Decimal("50000"))
        self.assertEqual(fee, Decimal("2500.00"))

    def test_fee_band_2_boundary_ten_lakh(self):
        """5% on 1L (5,000) + 4% on 9L (36,000) = 41,000 at exactly 10,00,000."""
        fee = calculate_court_fee(Decimal("1000000"))
        self.assertEqual(fee, Decimal("41000.00"))

    def test_fee_band_2_intermediate(self):
        """Claim 5,00,000 -> 5% on 1L (5,000) + 4% on 4L (16,000) = 21,000."""
        fee = calculate_court_fee(Decimal("500000"))
        self.assertEqual(fee, Decimal("21000.00"))

    def test_fee_band_3_above_ten_lakh(self):
        """Claim 20,00,000 -> 41,000 + 2% on 10L (20,000) = 61,000."""
        fee = calculate_court_fee(Decimal("2000000"))
        self.assertEqual(fee, Decimal("61000.00"))

    def test_fee_cap_three_lakh(self):
        """Calculated fee cannot exceed 3,00,000 (BR-14)."""
        fee = calculate_court_fee(Decimal("20000000"))  # 2 Crore -> uncapped would be 41,000 + 3,80,000 = 4,21,000
        self.assertEqual(fee, Decimal("300000.00"))

    def test_appeal_fee_reduction_fifty_percent(self):
        """Appeals pay 50% of original fee (BR-15)."""
        # Claim 10 Lakh -> standard fee 41,000 -> appeal pays 20,500
        fee = calculate_court_fee(Decimal("1000000"), is_appeal=True)
        self.assertEqual(fee, Decimal("20500.00"))

    def test_deficient_fee_marked_defective_with_seven_day_cure(self):
        """Deficient fee marks case DEFECTIVE with 7 days to cure (BR-16)."""
        case = Case(
            case_id="C-003",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 3, 1),
            cause_of_action_date=date(2025, 1, 1),
            claim_value=Decimal("100000"),
            court_fee_paid=Decimal("3000"), # due: 5000
            has_condonation_application=False,
        )
        result = process_admission(case, holidays=self.holidays)
        self.assertEqual(result.decision, AdmissionDecision.DEFECTIVE)
        self.assertEqual(result.cure_deadline, date(2026, 3, 8))
        self.assertIn(FLAG_DEFECTIVE, result.required_flags)
        self.assertIn(FLAG_FEE_DEFICIENT, result.required_flags)

    def test_uncured_defective_filing_returned(self):
        """Uncured defective filing past 7 days is RETURNED (BR-17)."""
        case = Case(
            case_id="C-004",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 3, 1),
            cause_of_action_date=date(2025, 1, 1),
            claim_value=Decimal("100000"),
            court_fee_paid=Decimal("3000"),
            status=CaseStatus.DEFECTIVE,
            cure_deadline=date(2026, 3, 8),
        )
        # Check on day 8 (2026-03-09): cure deadline has passed without payment
        decision = check_cure_status(case, current_date=date(2026, 3, 9))
        self.assertEqual(decision, AdmissionDecision.RETURNED)


if __name__ == "__main__":
    unittest.main()
