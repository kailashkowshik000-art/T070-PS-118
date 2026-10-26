"""Unit tests for Bench Allocation module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from models import (
    Bench,
    Case,
    CaseStatus,
    SubjectType,
)
from allocation import BenchAllocator


class TestBenchAllocation(unittest.TestCase):
    def setUp(self):
        # Setup benches
        self.bench_civil_1 = Bench(
            bench_id="BENCH-CIVIL-1",
            subject_jurisdictions=[SubjectType.CIVIL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            conflict_party_ids={"CONFLICT_CORP"},
        )
        self.bench_civil_2 = Bench(
            bench_id="BENCH-CIVIL-2",
            subject_jurisdictions=[SubjectType.CIVIL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
        )
        self.bench_commercial = Bench(
            bench_id="BENCH-COMMERCIAL-1",
            subject_jurisdictions=[SubjectType.COMMERCIAL, SubjectType.CIVIL],
            commercial_jurisdiction=True,
            sitting_days=[0, 1, 2, 3, 4],
        )
        self.bench_family = Bench(
            bench_id="BENCH-FAMILY-1",
            subject_jurisdictions=[SubjectType.FAMILY],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
            leave_dates={date(2026, 11, 2)},
        )
        self.bench_criminal = Bench(
            bench_id="BENCH-CRIMINAL-1",
            subject_jurisdictions=[SubjectType.CRIMINAL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
        )

        self.all_benches = [
            self.bench_civil_1,
            self.bench_civil_2,
            self.bench_commercial,
            self.bench_family,
            self.bench_criminal,
        ]

    def test_valid_allocation(self):
        """Civil case allocates to eligible civil bench."""
        allocator = BenchAllocator(self.all_benches)
        case = Case(
            case_id="CASE-CIVIL-01",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["PARTY_A", "PARTY_B"],
            filing_date=date(2026, 3, 1),
            claim_value=Decimal("50000"),
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertTrue(result.success)
        self.assertIn(result.allocated_bench_id, ["BENCH-CIVIL-1", "BENCH-CIVIL-2", "BENCH-COMMERCIAL-1"])
        self.assertEqual(case.assigned_bench, result.allocated_bench_id)
        self.assertEqual(case.status, CaseStatus.ALLOCATED)

    def test_subject_mismatch(self):
        """Criminal case only matches criminal benches, never civil or family."""
        # Only civil benches provided
        allocator = BenchAllocator([self.bench_civil_1, self.bench_civil_2])
        case = Case(
            case_id="CASE-CRIM-01",
            case_type="CRIMINAL_CASE",
            subject=SubjectType.CRIMINAL,
            party_ids=["STATE", "ACCUSED_1"],
            filing_date=date(2026, 3, 1),
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertFalse(result.success)
        self.assertIsNone(result.allocated_bench_id)
        self.assertIn("No eligible bench", result.reason)

    def test_commercial_claim_threshold_exceeded(self):
        """Commercial claim exceeding 3,00,000 must go to commercial bench (BR-03)."""
        allocator = BenchAllocator([self.bench_civil_1, self.bench_civil_2, self.bench_commercial])
        case = Case(
            case_id="CASE-COMM-HIGH",
            case_type="COMMERCIAL_SUIT",
            subject=SubjectType.COMMERCIAL,
            party_ids=["CORP_X", "CORP_Y"],
            filing_date=date(2026, 3, 1),
            claim_value=Decimal("500000"),  # > 3,00,000
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertTrue(result.success)
        self.assertEqual(result.allocated_bench_id, "BENCH-COMMERCIAL-1")

    def test_commercial_claim_at_or_below_threshold(self):
        """Commercial claim <= 3,00,000 can go to any bench with commercial subject jurisdiction."""
        # Bench with COMMERCIAL subject but commercial_jurisdiction=False
        regular_bench = Bench(
            bench_id="BENCH-REGULAR",
            subject_jurisdictions=[SubjectType.COMMERCIAL],
            commercial_jurisdiction=False,
            sitting_days=[0, 1, 2, 3, 4],
        )
        allocator = BenchAllocator([regular_bench])
        case = Case(
            case_id="CASE-COMM-LOW",
            case_type="COMMERCIAL_SUIT",
            subject=SubjectType.COMMERCIAL,
            party_ids=["STORE_A", "STORE_B"],
            filing_date=date(2026, 3, 1),
            claim_value=Decimal("300000"),  # Exactly 3,00,000 (not exceeding)
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertTrue(result.success)
        self.assertEqual(result.allocated_bench_id, "BENCH-REGULAR")

    def test_party_conflicts_exclude_bench(self):
        """Party conflict excludes the conflicted bench (BR-04)."""
        # BENCH-CIVIL-1 has conflict with CONFLICT_CORP
        allocator = BenchAllocator([self.bench_civil_1, self.bench_civil_2])
        case = Case(
            case_id="CASE-CONFLICT-01",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["CONFLICT_CORP", "DEFENDANT_Z"],
            filing_date=date(2026, 3, 1),
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertTrue(result.success)
        # Must NOT be BENCH-CIVIL-1
        self.assertEqual(result.allocated_bench_id, "BENCH-CIVIL-2")

    def test_round_robin_fairness(self):
        """Round-robin distributes cases sequentially across eligible benches (BR-05)."""
        b1 = Bench("BENCH-A", [SubjectType.CIVIL])
        b2 = Bench("BENCH-B", [SubjectType.CIVIL])
        b3 = Bench("BENCH-C", [SubjectType.CIVIL])
        allocator = BenchAllocator([b1, b2, b3])

        assigned_benches = []
        for i in range(6):
            c = Case(
                case_id=f"CASE-{i}",
                case_type="CIVIL_SUIT",
                subject=SubjectType.CIVIL,
                party_ids=[f"P_{i}", f"D_{i}"],
                filing_date=date(2026, 3, 1),
                status=CaseStatus.ADMITTED,
            )
            res = allocator.allocate(c)
            assigned_benches.append(res.allocated_bench_id)

        self.assertEqual(assigned_benches, [
            "BENCH-A", "BENCH-B", "BENCH-C",
            "BENCH-A", "BENCH-B", "BENCH-C",
        ])

    def test_no_eligible_bench_due_to_conflicts(self):
        """Returns clear reason when all benches have conflicts."""
        b1 = Bench("BENCH-1", [SubjectType.CIVIL], conflict_party_ids={"CORP_A"})
        b2 = Bench("BENCH-2", [SubjectType.CIVIL], conflict_party_ids={"CORP_A"})
        allocator = BenchAllocator([b1, b2])

        case = Case(
            case_id="CASE-NO-BENCH",
            case_type="CIVIL_SUIT",
            subject=SubjectType.CIVIL,
            party_ids=["CORP_A", "DEF_B"],
            filing_date=date(2026, 3, 1),
            status=CaseStatus.ADMITTED,
        )
        result = allocator.allocate(case)
        self.assertFalse(result.success)
        self.assertIsNone(result.allocated_bench_id)
        self.assertIn("conflict", result.reason.lower())

    def test_bench_leave_and_sitting_day_filtering(self):
        """Can filter out benches that are on leave or not sitting on specific date."""
        allocator = BenchAllocator([self.bench_family])
        # Bench family is on leave on 2026-11-02
        eligible = allocator.get_eligible_benches(
            subject=SubjectType.FAMILY,
            party_ids=["F_P1", "F_P2"],
            on_date=date(2026, 11, 2),
        )
        self.assertEqual(len(eligible), 0)

        # But on 2026-11-03 (Tuesday), it is eligible
        eligible_next = allocator.get_eligible_benches(
            subject=SubjectType.FAMILY,
            party_ids=["F_P1", "F_P2"],
            on_date=date(2026, 11, 3),
        )
        self.assertEqual(len(eligible_next), 1)


if __name__ == "__main__":
    unittest.main()
