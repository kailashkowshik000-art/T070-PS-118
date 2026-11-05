"""Unit tests for Hearing Management module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date, timedelta
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

    def test_adjournment_count_resets_on_new_stage(self):
        """Party adjournment quota is per stage: 3 adjournments in PLEADINGS do not block in ISSUES (BR-34)."""
        case = Case(
            case_id="C-STG-RESET",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P1", "D1"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.ISSUES,
            adjournment_history=[
                HearingEvent("E1", "C-STG-RESET", date(2026, 2, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1", stage=CaseStage.PLEADINGS),
                HearingEvent("E2", "C-STG-RESET", date(2026, 3, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1", stage=CaseStage.PLEADINGS),
                HearingEvent("E3", "C-STG-RESET", date(2026, 4, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1", stage=CaseStage.PLEADINGS),
            ],
        )
        # In ISSUES, P1 has 0 adjournments so far
        p1_issues_count = self.manager.get_party_adjournment_count(case, party_id="P1", stage=CaseStage.ISSUES)
        self.assertEqual(p1_issues_count, 0)

        # 1st adjournment in ISSUES should be permitted without cost
        evt_issues_1 = HearingEvent(
            "E4-ISSUE", "C-STG-RESET", date(2026, 5, 1),
            HearingOutcome.ADJOURNED,
            AdjournmentReason.PARTY_REQUEST,
            requesting_party="P1",
            stage=CaseStage.ISSUES,
        )
        allowed, msg = self.manager.process_adjournment(case, evt_issues_1)
        self.assertTrue(allowed)
        self.assertEqual(evt_issues_1.cost_assessed, Decimal("0.00"))

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

    # ==========================================
    # New Week 3 Tests: BR-25, BR-29, BR-33, BR-38, BR-41, BR-42
    # ==========================================

    def test_hearing_outcomes_all_types(self):
        """Verify support for HEARD, PART_HEARD, ADJOURNED, DECIDED (BR-29)."""
        # 1. HEARD
        c1 = Case("C-H1", "CIVIL", SubjectType.CIVIL, ["P1"], date(2026, 1, 1), assigned_bench="BENCH-H1")
        e_heard = HearingEvent("E-H", "C-H1", date(2026, 10, 29), HearingOutcome.HEARD)
        ok, _ = self.manager.process_hearing_event(c1, e_heard)
        self.assertTrue(ok)
        self.assertEqual(c1.status, CaseStatus.HEARD)

        # 2. PART_HEARD
        c2 = Case("C-H2", "CIVIL", SubjectType.CIVIL, ["P1"], date(2026, 1, 1), assigned_bench="BENCH-H1")
        e_part = HearingEvent("E-PH", "C-H2", date(2026, 10, 29), HearingOutcome.PART_HEARD)
        ok, _ = self.manager.process_hearing_event(c2, e_part)
        self.assertTrue(ok)
        self.assertTrue(c2.is_part_heard)

        # 3. DECIDED
        c3 = Case("C-H3", "CIVIL", SubjectType.CIVIL, ["P1"], date(2026, 1, 1), assigned_bench="BENCH-H1", stage=CaseStage.ARGUMENTS)
        e_dec = HearingEvent("E-DEC", "C-H3", date(2026, 10, 29), HearingOutcome.DECIDED)
        ok, _ = self.manager.process_hearing_event(c3, e_dec)
        self.assertTrue(ok)
        self.assertEqual(c3.status, CaseStatus.DECIDED)
        self.assertIsNone(c3.next_hearing_date)

    def test_evidence_delay_flag_after_180_days(self):
        """More than 180 days in EVIDENCE stage triggers DELAY flag (BR-33)."""
        case = Case(
            case_id="C-EV-DELAY",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P1"],
            filing_date=date(2025, 1, 1),
            stage=CaseStage.EVIDENCE,
            stage_start_date=date(2025, 1, 1),
            assigned_bench="BENCH-H1",
        )
        event = HearingEvent("E-EV", "C-EV-DELAY", date(2025, 8, 1), HearingOutcome.HEARD)
        # Days between 2025-01-01 and 2025-08-01 is 212 days (> 180)
        self.manager.process_hearing_event(case, event)
        self.assertIn("DELAY", case.flags)
        self.assertIn("EVIDENCE_DELAY", case.flags)

    def test_cost_payment_timing_and_flag(self):
        """Adjournment cost assessment sets COST_PAYMENT_PENDING; payment clears it (BR-38)."""
        case = Case(
            case_id="C-COST",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P1"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.PLEADINGS,
            assigned_bench="BENCH-H1",
            adjournment_history=[
                HearingEvent("E1", "C-COST", date(2026, 2, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1"),
                HearingEvent("E2", "C-COST", date(2026, 3, 1), HearingOutcome.ADJOURNED, AdjournmentReason.PARTY_REQUEST, requesting_party="P1"),
            ],
        )
        # 3rd party adjournment -> costs ₹2,000
        e3 = HearingEvent(
            "E3", "C-COST", date(2026, 4, 1), HearingOutcome.ADJOURNED,
            AdjournmentReason.PARTY_REQUEST, requesting_party="P1", cost_paid=False,
        )
        self.manager.process_adjournment(case, e3)
        self.assertEqual(case.costs_assessed, Decimal("2000.00"))
        self.assertIn("COST_PAYMENT_PENDING", case.flags)

        # Pay cost
        self.manager.pay_adjournment_cost(case, Decimal("2000.00"))
        self.assertEqual(case.costs_paid, Decimal("2000.00"))
        self.assertNotIn("COST_PAYMENT_PENDING", case.flags)

    def test_overdue_commercial_case_7_day_interval(self):
        """Commercial cases past 12 months are scheduled every 7 days (BR-25)."""
        old_comm = Case(
            case_id="C-COMM-OLD",
            case_type="COMMERCIAL_SUIT",
            subject=SubjectType.COMMERCIAL,
            party_ids=["CORP1", "CORP2"],
            filing_date=date(2025, 1, 1),  # Over 365 days before 2026-10-29
            assigned_bench="BENCH-H1",
            stage=CaseStage.EVIDENCE,
        )
        event = HearingEvent(
            "E-ADJ-COMM", "C-COMM-OLD", date(2026, 10, 29), HearingOutcome.ADJOURNED,
            AdjournmentReason.PARTY_REQUEST, requesting_party="CORP1"
        )
        self.manager.process_adjournment(case=old_comm, event=event)
        self.assertIn("COMMERCIAL_DISPOSAL_TARGET_OVERDUE", old_comm.flags)
        # 7 days from Thursday 2026-10-29 is Thursday 2026-11-05
        self.assertEqual(old_comm.next_hearing_date, date(2026, 11, 5))

    def test_capacity_on_next_date_and_overboard_fallback(self):
        """When capacity is full across window, falls back to Day 60 with OVERBOARD (BR-41, BR-42)."""
        from_date = date(2026, 1, 1)
        # Fill board for all days from day 14 to day 60
        full_board = {}
        for d in range(14, 61):
            target = from_date + timedelta(days=d)
            full_board[target] = 40  # capacity full

        next_dt, is_overboard = calculate_next_hearing_date(
            bench=self.bench,
            from_date=from_date,
            is_urgent=False,
            holidays=self.holidays,
            board_counts=full_board,
        )
        self.assertTrue(is_overboard)
        self.assertEqual(next_dt, from_date + timedelta(days=60))

    def test_multi_sitting_simulation(self):
        """Simulate court proceedings across consecutive court sitting dates (BR-29 to BR-38)."""
        case = Case(
            case_id="C-SIM-01",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PA", "PB"],
            filing_date=date(2026, 10, 1),
            assigned_bench="BENCH-H1",
            stage=CaseStage.PLEADINGS,
        )
        events = [
            HearingEvent("EVT-S1", "C-SIM-01", date(2026, 10, 29), HearingOutcome.HEARD, new_stage=CaseStage.ISSUES),
            HearingEvent("EVT-S2", "C-SIM-01", date(2026, 11, 12), HearingOutcome.ADJOURNED, AdjournmentReason.COURT_OCCASIONED),
        ]
        sittings = [date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 12)]

        summaries, cause_lists = self.manager.simulate_sittings(
            cases=[case],
            events=events,
            sitting_dates=sittings,
        )
        self.assertGreater(len(summaries), 0)
        # Verify case progressed to ISSUES after 2026-10-29
        self.assertEqual(case.stage, CaseStage.ISSUES)


if __name__ == "__main__":
    unittest.main()
