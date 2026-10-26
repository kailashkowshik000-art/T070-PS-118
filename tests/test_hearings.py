"""Unit tests for Hearing Management module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from config import (
    COMMERCIAL_ADJOURNMENT_COST,
    FLAG_OVERBOARD,
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
from hearings import (
    calculate_adjournment_cost,
    calculate_next_hearing_date,
    HearingManager,
)


class TestHearingManagement(unittest.TestCase):
    def setUp(self):
        self.holidays = {date(2026, 11, 8)}
        self.bench = Bench(
            bench_id="BENCH-H1",
            subject_jurisdictions=[SubjectType.CIVIL, SubjectType.COMMERCIAL],
            commercial_jurisdiction=True,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates={date(2026, 11, 13)},  # Leave on Friday 13 Nov 2026
        )
        self.manager = HearingManager(benches=[self.bench], holidays=self.holidays)

    def test_stage_progression_sequential(self):
        """Stages progress sequentially from PLEADINGS to ISSUES (BR-30)."""
        case = Case(
            case_id="C-STG-1",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.PLEADINGS,
            status=CaseStatus.LISTED,
        )
        event = HearingEvent(
            event_id="EVT-01",
            case_id=case.case_id,
            hearing_date=date(2026, 10, 29),
            outcome=HearingOutcome.HEARD,
        )
        success, msg = self.manager.advance_stage(case, target_stage=CaseStage.ISSUES, event=event)
        self.assertTrue(success)
        self.assertEqual(case.stage, CaseStage.ISSUES)

    def test_stage_skipping_prevented_without_consent(self):
        """Skipping a stage without consent flag is disallowed (BR-31)."""
        case = Case(
            case_id="C-STG-2",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.PLEADINGS,
        )
        event = HearingEvent(
            event_id="EVT-02",
            case_id=case.case_id,
            hearing_date=date(2026, 10, 29),
            outcome=HearingOutcome.HEARD,
            consent_indicator=False,
        )
        success, msg = self.manager.advance_stage(case, target_stage=CaseStage.EVIDENCE, event=event)
        self.assertFalse(success)
        self.assertEqual(case.stage, CaseStage.PLEADINGS)
        self.assertIn("consent", msg.lower())

    def test_stage_skipping_allowed_with_consent(self):
        """Skipping a stage with consent flag is allowed (BR-31)."""
        case = Case(
            case_id="C-STG-3",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.PLEADINGS,
        )
        event = HearingEvent(
            event_id="EVT-03",
            case_id=case.case_id,
            hearing_date=date(2026, 10, 29),
            outcome=HearingOutcome.HEARD,
            consent_indicator=True,
        )
        success, msg = self.manager.advance_stage(case, target_stage=CaseStage.ARGUMENTS, event=event)
        self.assertTrue(success)
        self.assertEqual(case.stage, CaseStage.ARGUMENTS)

    def test_adjournment_count_and_fourth_refusal(self):
        """Fourth adjournment by party is refused unless MEDICAL or COURT_OCCASIONED (BR-34)."""
        case = Case(
            case_id="C-ADJ-MAX",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.EVIDENCE,
            adjournment_history=[
                HearingEvent("E1", "C-ADJ-MAX", date(2026, 6, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1"),
                HearingEvent("E2", "C-ADJ-MAX", date(2026, 7, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1"),
                HearingEvent("E3", "C-ADJ-MAX", date(2026, 8, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1"),
            ],
        )

        # 4th party request -> refused
        evt4_party = HearingEvent(
            "E4", "C-ADJ-MAX", date(2026, 9, 1),
            HearingOutcome.ADJOURNED,
            AdjournmentReason.PARTY_REQUEST,
            requesting_party="P1",
        )
        allowed, reason = self.manager.process_adjournment(case, evt4_party)
        self.assertFalse(allowed)
        self.assertIn("Maximum 3 adjournments", reason)

        # 4th request with MEDICAL reason -> allowed under exception (BR-34, BR-43)
        evt4_med = HearingEvent(
            "E4-MED", "C-ADJ-MAX", date(2026, 9, 1),
            HearingOutcome.ADJOURNED,
            AdjournmentReason.MEDICAL,
            requesting_party="P1",
        )
        allowed_med, _ = self.manager.process_adjournment(case, evt4_med)
        self.assertTrue(allowed_med)

    def test_court_occasioned_adjournment_does_not_count_against_party(self):
        """Court-occasioned adjournments do not count towards party limit (BR-35)."""
        case = Case(
            case_id="C-COURT-ADJ",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.EVIDENCE,
            adjournment_history=[
                HearingEvent("E1", "C-COURT-ADJ", date(2026, 6, 1), HearingOutcome.ADJOURNED, AdjournmentReason.COURT_OCCASIONED),
                HearingEvent("E2", "C-COURT-ADJ", date(2026, 7, 1), HearingOutcome.ADJOURNED, AdjournmentReason.COURT_OCCASIONED),
            ],
        )
        party_count = self.manager.get_party_adjournment_count(case, party_id="P1", stage=CaseStage.EVIDENCE)
        self.assertEqual(party_count, 0)

    def test_adjournment_costs(self):
        """Party adjournment after 2 earlier adjournments costs 2,000; commercial costs 4,000 (BR-36, BR-37)."""
        # Third party adjournment in civil case
        cost_civil = calculate_adjournment_cost(SubjectType.CIVIL, prior_party_adjournments=2)
        self.assertEqual(cost_civil, PARTY_ADJOURNMENT_COST)

        # 1st or 2nd adjournment costs 0
        cost_initial = calculate_adjournment_cost(SubjectType.CIVIL, prior_party_adjournments=1)
        self.assertEqual(cost_initial, Decimal("0.00"))

        # Third party adjournment in commercial case
        cost_comm = calculate_adjournment_cost(SubjectType.COMMERCIAL, prior_party_adjournments=2)
        self.assertEqual(cost_comm, COMMERCIAL_ADJOURNMENT_COST)

    def test_next_hearing_date_minimum_interval_and_calendar(self):
        """Next hearing date is at least 14 days ahead on eligible sitting day (BR-39, BR-40)."""
        from_date = date(2026, 10, 29)  # Thursday
        # 14 days later: 2026-11-12 (Thursday)
        # Friday 2026-11-13 is bench leave. 2026-11-12 is not on leave.
        next_dt, is_overboard = calculate_next_hearing_date(
            bench=self.bench,
            from_date=from_date,
            is_urgent=False,
            holidays=self.holidays,
        )
        self.assertEqual(next_dt, date(2026, 11, 12))
        self.assertFalse(is_overboard)


if __name__ == "__main__":
    unittest.main()
