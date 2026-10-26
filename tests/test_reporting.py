"""Unit tests for Reporting module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from config import FLAG_DELAY
from models import (
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
from reporting import (
    generate_case_diary,
    generate_cause_list_report,
    generate_execution_summary,
    generate_pendency_report,
)


class TestReporting(unittest.TestCase):
    def setUp(self):
        self.listing_date = date(2026, 10, 29)
        self.case = Case(
            case_id="C-REP-01",
            case_type="COMMERCIAL_SUIT",
            subject=SubjectType.COMMERCIAL,
            party_ids=["ACME_CORP", "BETA_LLC"],
            filing_date=date(2025, 1, 15),
            claim_value=Decimal("500000"),
            court_fee_paid=Decimal("21000"),
            status=CaseStatus.LISTED,
            stage=CaseStage.EVIDENCE,
            assigned_bench="BENCH-COMM-1",
            next_hearing_date=self.listing_date,
            adjournment_history=[
                HearingEvent("E1", "C-REP-01", date(2025, 6, 1), HearingOutcome.HEARD),
            ],
            flags={FLAG_DELAY},
        )

    def test_cause_list_report_format(self):
        """Generates formatted cause list report for a bench (BR-49)."""
        entry = CauseListEntry(
            case_id="C-REP-01",
            bench_id="BENCH-COMM-1",
            listing_date=self.listing_date,
            priority_band=PriorityBand.BAND_1_URGENT,
            position=1,
            carry_over_indicator=False,
            final_hearing_indicator=False,
            flags=["COMMERCIAL_TARGET"],
        )
        report = generate_cause_list_report("BENCH-COMM-1", self.listing_date, [entry])
        self.assertIn("BENCH-COMM-1", report)
        self.assertIn("2026-10-29", report)
        self.assertIn("C-REP-01", report)
        self.assertIn("Pos: 1", report)

    def test_case_diary_contains_lifecycle_fields(self):
        """Generates comprehensive case diary (BR-50)."""
        diary = generate_case_diary(self.case)
        self.assertIn("C-REP-01", diary)
        self.assertIn("ACME_CORP", diary)
        self.assertIn("COMMERCIAL", diary)
        self.assertIn("BENCH-COMM-1", diary)
        self.assertIn("EVIDENCE", diary)
        self.assertIn("21,000", diary)

    def test_pendency_report_identifies_overdue_and_delay(self):
        """Generates pendency report identifying overdue commercial cases and delay flags (BR-51)."""
        report_data = generate_pendency_report([self.case], as_of_date=self.listing_date)
        self.assertEqual(report_data["total_pending"], 1)
        self.assertEqual(len(report_data["overdue_commercial"]), 1)
        self.assertIn("C-REP-01", report_data["overdue_commercial"])

    def test_execution_summary_text(self):
        """Generates clear summary of registry execution run."""
        summary = generate_execution_summary(
            run_date=self.listing_date,
            filings_count=10,
            admitted_count=8,
            defective_count=1,
            rejected_count=1,
            allocated_count=8,
            listed_count=8,
        )
        self.assertIn("10", summary)
        self.assertIn("8", summary)
        self.assertIn("2026-10-29", summary)


if __name__ == "__main__":
    unittest.main()
