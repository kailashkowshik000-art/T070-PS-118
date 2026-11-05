"""Unit tests for Case Transfer Engine (BR-44 to BR-48).

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from config import (
    COMMERCIAL_CLAIM_THRESHOLD,
    FLAG_TRANSFERRED,
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
from hearings import HearingManager


class TestTransferEngine(unittest.TestCase):
    def setUp(self):
        self.holidays = {date(2026, 11, 8)}

        self.bench_civil_1 = Bench(
            bench_id="BENCH-CIVIL-01",
            subject_jurisdictions=[SubjectType.CIVIL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates=set(),
            conflict_party_ids={"CONFLICT_CORP"},
        )
        self.bench_civil_2 = Bench(
            bench_id="BENCH-CIVIL-02",
            subject_jurisdictions=[SubjectType.CIVIL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates=set(),
            conflict_party_ids=set(),
        )
        self.bench_comm = Bench(
            bench_id="BENCH-COMM-01",
            subject_jurisdictions=[SubjectType.COMMERCIAL, SubjectType.CIVIL],
            commercial_jurisdiction=True,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates=set(),
            conflict_party_ids=set(),
        )
        self.bench_crim = Bench(
            bench_id="BENCH-CRIM-01",
            subject_jurisdictions=[SubjectType.CRIMINAL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates=set(),
            conflict_party_ids=set(),
        )

        self.bench_comm_regular = Bench(
            bench_id="BENCH-COMM-REG",
            subject_jurisdictions=[SubjectType.COMMERCIAL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates=set(),
            conflict_party_ids=set(),
        )

        self.all_benches = [
            self.bench_civil_1,
            self.bench_civil_2,
            self.bench_comm,
            self.bench_crim,
            self.bench_comm_regular,
        ]
        self.manager = HearingManager(benches=self.all_benches, holidays=self.holidays)

    def test_transfer_valid_roster_change(self):
        """Case transfers successfully for ROSTER_CHANGE (BR-44, BR-45, BR-48)."""
        case = Case(
            case_id="C-TRF-01",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PARTY_A", "PARTY_B"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
            stage=CaseStage.PLEADINGS,
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        self.assertTrue(result.success)
        self.assertEqual(case.assigned_bench, "BENCH-CIVIL-02")
        self.assertEqual(case.transferred_count, 1)
        self.assertEqual(case.status, CaseStatus.TRANSFERRED)
        self.assertIn(FLAG_TRANSFERRED, case.flags)
        self.assertIsNotNone(case.next_hearing_date)

    def test_transfer_valid_conflict(self):
        """Case transfers successfully for judicial CONFLICT (BR-44)."""
        case = Case(
            case_id="C-TRF-02",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PARTY_A", "PARTY_B"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
            stage=CaseStage.ISSUES,
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.CONFLICT,
            event_date=date(2026, 10, 29),
        )
        self.assertTrue(result.success)
        self.assertEqual(case.assigned_bench, "BENCH-CIVIL-02")

    def test_transfer_refused_second_time_limit(self):
        """Transfer refused when case has already reached lifetime limit of 1 (BR-44)."""
        case = Case(
            case_id="C-TRF-LIMIT",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PARTY_A", "PARTY_B"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-02",
            transferred_count=1,  # Already transferred once!
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-01",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        self.assertFalse(result.success)
        self.assertIn("maximum lifetime transfer limit of 1", result.reason)
        self.assertEqual(case.assigned_bench, "BENCH-CIVIL-02")

    def test_transfer_refused_for_invalid_reason(self):
        """Transfer refused if reason is not ROSTER_CHANGE or CONFLICT (BR-44)."""
        case = Case(
            case_id="C-TRF-REASON",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PARTY_A", "PARTY_B"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.PARTY_REQUEST,
            event_date=date(2026, 10, 29),
        )
        self.assertFalse(result.success)
        self.assertIn("invalid reason", result.reason)

    def test_transfer_refused_destination_party_conflict(self):
        """Transfer refused if destination bench has a party conflict (BR-45)."""
        # BENCH-CIVIL-01 has conflict with CONFLICT_CORP
        case = Case(
            case_id="C-TRF-CONFLICT",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["CONFLICT_CORP", "DEF_X"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-02",
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-01",
            reason=AdjournmentReason.CONFLICT,
            event_date=date(2026, 10, 29),
        )
        self.assertFalse(result.success)
        self.assertIn("party conflict", result.reason.lower())
        self.assertEqual(case.assigned_bench, "BENCH-CIVIL-02")

    def test_transfer_refused_subject_mismatch(self):
        """Transfer refused if destination bench lacks subject jurisdiction (BR-45)."""
        # BENCH-CRIM-01 does not handle CIVIL
        case = Case(
            case_id="C-TRF-SUBJ",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PA", "PB"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CRIM-01",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        self.assertFalse(result.success)
        self.assertIn("jurisdiction", result.reason.lower())

    def test_transfer_refused_commercial_threshold(self):
        """Commercial claim > 3L requires commercial bench on transfer (BR-45)."""
        case = Case(
            case_id="C-TRF-COMM",
            case_type="COMMERCIAL_SUIT",
            subject=SubjectType.COMMERCIAL,
            party_ids=["CORP_A", "CORP_B"],
            claim_value=Decimal("500000.00"),  # > 3L
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-COMM-01",
        )
        # Attempt transfer to BENCH-COMM-REG (handles commercial, but not designated commercial bench)
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-COMM-REG",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        self.assertFalse(result.success)
        self.assertIn("commercial bench", result.reason.lower())

    def test_transfer_preserves_case_history_and_stage(self):
        """Case stage and adjournment history are preserved on transfer (BR-46)."""
        hist = [
            HearingEvent("E1", "C-TRF-HIST", date(2026, 5, 1), HearingOutcome.HEARD),
            HearingEvent("E2", "C-TRF-HIST", date(2026, 6, 1), HearingOutcome.ADJOURNED, AdjournmentReason.COURT_OCCASIONED),
        ]
        case = Case(
            case_id="C-TRF-HIST",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PA", "PB"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
            stage=CaseStage.EVIDENCE,
            adjournment_history=hist,
        )
        self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        # Stage preserved
        self.assertEqual(case.stage, CaseStage.EVIDENCE)
        # Prior history preserved, plus the transfer event added (BR-47)
        self.assertEqual(len(case.adjournment_history), 3)
        self.assertEqual(case.adjournment_history[0].event_id, "E1")
        self.assertEqual(case.adjournment_history[1].event_id, "E2")
        self.assertEqual(case.adjournment_history[2].outcome, HearingOutcome.TRANSFERRED)

    def test_transfer_counts_as_adjournment(self):
        """A transfer event counts as an adjournment (BR-47)."""
        case = Case(
            case_id="C-TRF-ADJ",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PA", "PB"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
        )
        self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=date(2026, 10, 29),
        )
        # 1 event in history, with outcome TRANSFERRED
        self.assertEqual(len(case.adjournment_history), 1)
        self.assertEqual(case.adjournment_history[0].outcome, HearingOutcome.TRANSFERRED)

    def test_transfer_recomputes_next_hearing_date(self):
        """Recomputes next hearing date using destination bench calendar (BR-48)."""
        # Destination bench BENCH-CIVIL-02 sits Mon-Fri
        event_dt = date(2026, 10, 29)  # Thursday
        # Min interval is 14 days -> earliest date is 2026-11-12 (Thursday)
        case = Case(
            case_id="C-TRF-RECOMP",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PA", "PB"],
            filing_date=date(2026, 1, 10),
            assigned_bench="BENCH-CIVIL-01",
        )
        result = self.manager.transfer_case(
            case=case,
            destination_bench_id="BENCH-CIVIL-02",
            reason=AdjournmentReason.ROSTER_CHANGE,
            event_date=event_dt,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.next_hearing_date, date(2026, 11, 12))
        self.assertEqual(case.next_hearing_date, date(2026, 11, 12))


if __name__ == "__main__":
    unittest.main()
