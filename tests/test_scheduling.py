"""Unit tests for Cause-List Generation module.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import unittest

from config import (
    DAILY_BOARD_CAPACITY,
    DAILY_FINAL_HEARING_CAP,
    FLAG_CARRIED_OVER,
    FLAG_ESCALATED,
    FLAG_IN_CAMERA,
)
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
from scheduling import (
    determine_priority_band,
    generate_cause_list,
    ScheduleUrgentResult,
    schedule_urgent_mention,
)


class TestCauseListScheduling(unittest.TestCase):
    def setUp(self):
        self.listing_date = date(2026, 10, 29)  # Thursday (weekday == 3)
        self.bench = Bench(
            bench_id="BENCH-01",
            subject_jurisdictions=[
                SubjectType.CIVIL,
                SubjectType.COMMERCIAL,
                SubjectType.FAMILY,
                SubjectType.CRIMINAL,
            ],
            commercial_jurisdiction=True,
            sitting_days=[0, 1, 2, 3, 4],  # Mon-Fri
            daily_board_capacity=40,
            designated_family_hearing_days=[3],  # Thursday is designated family day
        )

    # ==========================================
    # Priority Band Assignment Tests (BR-19, BR-24, BR-25, BR-32)
    # ==========================================

    def test_priority_band_1_urgent(self):
        """Urgent/bail matters belong to Band 1."""
        case = Case(
            case_id="C-URGENT",
            case_type="CRIMINAL",
            subject=SubjectType.CRIMINAL,
            party_ids=["P", "D"],
            filing_date=date(2026, 10, 1),
            urgency=True,
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_1_URGENT)

    def test_priority_band_2_part_heard(self):
        """Part-heard matters belong to Band 2."""
        case = Case(
            case_id="C-PART-HEARD",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 5, 1),
            is_part_heard=True,
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_2_PART_HEARD)

    def test_priority_band_3_three_plus_adjournments(self):
        """Cases with 3 or more adjournments belong to Band 3 (BR-19)."""
        adjournments = [
            HearingEvent("E1", "C-ADJ", date(2026, 6, 1), HearingOutcome.ADJOURNED),
            HearingEvent("E2", "C-ADJ", date(2026, 7, 1), HearingOutcome.ADJOURNED),
            HearingEvent("E3", "C-ADJ", date(2026, 8, 1), HearingOutcome.ADJOURNED),
        ]
        case = Case(
            case_id="C-ADJ",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            adjournment_history=adjournments,
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_3_THREE_PLUS_ADJOURNMENTS)

    def test_priority_band_4_older_than_two_years(self):
        """Cases older than 2 years from filing date belong to Band 4."""
        case = Case(
            case_id="C-OLD",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2024, 1, 1),  # > 2 years before 2026-10-29
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_4_OLDER_THAN_TWO_YEARS)

    def test_priority_band_5_final_hearing(self):
        """Cases at ARGUMENTS stage or marked final hearing belong to Band 5."""
        case = Case(
            case_id="C-FINAL",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.ARGUMENTS,
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_5_FINAL_HEARING)

    def test_priority_band_6_regular(self):
        """Standard cases with no special condition belong to Band 6."""
        case = Case(
            case_id="C-REG",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2026, 1, 1),
            stage=CaseStage.PLEADINGS,
        )
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_6_REGULAR)

    def test_priority_escalation_after_three_unreached_sittings(self):
        """Unreached on 3 consecutive sittings moves up one priority band (BR-24)."""
        case = Case(
            case_id="C-ESCALATE",
            case_type="CIVIL",
            subject=SubjectType.CIVIL,
            party_ids=["P", "D"],
            filing_date=date(2024, 1, 1),  # Normally Band 4
            consecutive_unreached_count=3,
        )
        # Should escalate to Band 3
        band = determine_priority_band(case, self.listing_date)
        self.assertEqual(band, PriorityBand.BAND_3_THREE_PLUS_ADJOURNMENTS)

    # ==========================================
    # Cause List Ordering and Capacity Tests (BR-20, BR-21, BR-22, BR-23)
    # ==========================================

    def test_oldest_filing_date_first_within_band(self):
        """Within the same band, oldest filing date is listed first (BR-20)."""
        c1 = Case("C1", "CIVIL", SubjectType.CIVIL, ["P"], date(2026, 3, 15), assigned_bench="BENCH-01")
        c2 = Case("C2", "CIVIL", SubjectType.CIVIL, ["P"], date(2026, 1, 10), assigned_bench="BENCH-01")
        c3 = Case("C3", "CIVIL", SubjectType.CIVIL, ["P"], date(2026, 2, 20), assigned_bench="BENCH-01")

        cause_list, unreached = generate_cause_list(
            bench=self.bench,
            cases=[c1, c2, c3],
            listing_date=self.listing_date,
        )

        self.assertEqual(len(cause_list), 3)
        self.assertEqual([e.case_id for e in cause_list], ["C2", "C3", "C1"])
        self.assertEqual([e.position for e in cause_list], [1, 2, 3])

    def test_carry_over_matters_listed_first_within_band(self):
        """Carry-over matters go first within their band, ahead of new matters (BR-23)."""
        c_new = Case("C-NEW", "CIVIL", SubjectType.CIVIL, ["P"], date(2026, 1, 1), assigned_bench="BENCH-01")
        c_carry = Case(
            "C-CARRY",
            "CIVIL",
            SubjectType.CIVIL,
            ["P"],
            date(2026, 2, 1),
            carry_over_count=1,
            assigned_bench="BENCH-01",
        )

        cause_list, _ = generate_cause_list(
            bench=self.bench,
            cases=[c_new, c_carry],
            listing_date=self.listing_date,
        )

        self.assertEqual([e.case_id for e in cause_list], ["C-CARRY", "C-NEW"])
        self.assertTrue(cause_list[0].carry_over_indicator)
        self.assertFalse(cause_list[1].carry_over_indicator)

    def test_maximum_forty_matters_daily_capacity(self):
        """Maximum 40 matters per bench per day (BR-21). Excess matters are unreached."""
        cases = [
            Case(
                f"C-{i:02d}",
                "CIVIL",
                SubjectType.CIVIL,
                ["P"],
                date(2026, 1, 1),
                assigned_bench="BENCH-01",
            )
            for i in range(45)
        ]

        cause_list, unreached = generate_cause_list(
            bench=self.bench,
            cases=cases,
            listing_date=self.listing_date,
        )

        self.assertEqual(len(cause_list), 40)
        self.assertEqual(len(unreached), 5)
        self.assertEqual(cause_list[-1].position, 40)
        self.assertEqual(unreached[0].consecutive_unreached_count, 1)

    def test_maximum_eight_final_hearing_matters(self):
        """Maximum 8 final-hearing matters per bench per day (BR-22)."""
        # Create 10 final-hearing cases (Band 5) and 5 regular cases (Band 6)
        final_cases = [
            Case(
                f"CF-{i:02d}",
                "CIVIL",
                SubjectType.CIVIL,
                ["P"],
                date(2026, 1, i + 1),
                stage=CaseStage.ARGUMENTS,
                assigned_bench="BENCH-01",
            )
            for i in range(10)
        ]
        reg_cases = [
            Case(
                f"CR-{i:02d}",
                "CIVIL",
                SubjectType.CIVIL,
                ["P"],
                date(2026, 2, i + 1),
                stage=CaseStage.PLEADINGS,
                assigned_bench="BENCH-01",
            )
            for i in range(5)
        ]

        cause_list, unreached = generate_cause_list(
            bench=self.bench,
            cases=final_cases + reg_cases,
            listing_date=self.listing_date,
        )

        final_listed = [e for e in cause_list if e.final_hearing_indicator]
        self.assertEqual(len(final_listed), 8)
        # 2 excess final hearing cases must be unreached
        unreached_ids = [c.case_id for c in unreached]
        self.assertIn("CF-08", unreached_ids)
        self.assertIn("CF-09", unreached_ids)
        # Regular cases should still be listed
        reg_listed = [e for e in cause_list if not e.final_hearing_indicator]
        self.assertEqual(len(reg_listed), 5)

    # ==========================================
    # Urgent Mention and Family Restrictions Tests (BR-26, BR-27)
    # ==========================================

    def test_urgent_mention_before_cutoff_same_day_listed(self):
        """Urgent mentioned before 10:30 with capacity fits same day (BR-27)."""
        urgent_case = Case(
            case_id="C-URG-1015",
            case_type="CRIMINAL",
            subject=SubjectType.CRIMINAL,
            party_ids=["P", "D"],
            filing_date=date(2026, 10, 29),
            urgency=True,
            assigned_bench="BENCH-01",
        )
        current_board_count = 35  # < 40 capacity

        result = schedule_urgent_mention(
            case=urgent_case,
            bench=self.bench,
            current_date=self.listing_date,
            mentioned_at="10:15",
            current_board_size=current_board_count,
        )

        self.assertTrue(result.listed_same_day)
        self.assertEqual(result.scheduled_date, self.listing_date)
        self.assertEqual(result.position, 36)

    def test_urgent_mention_before_cutoff_board_full_next_day_pos_1(self):
        """Urgent mentioned before 10:30 with full board goes to next sitting day at position 1 (BR-27)."""
        urgent_case = Case(
            case_id="C-URG-FULL",
            case_type="CRIMINAL",
            subject=SubjectType.CRIMINAL,
            party_ids=["P", "D"],
            filing_date=date(2026, 10, 29),
            urgency=True,
            assigned_bench="BENCH-01",
        )
        current_board_count = 40  # Full capacity

        result = schedule_urgent_mention(
            case=urgent_case,
            bench=self.bench,
            current_date=self.listing_date,
            mentioned_at="10:20",
            current_board_size=current_board_count,
        )

        self.assertFalse(result.listed_same_day)
        # Next sitting day after Thursday 2026-10-29 is Friday 2026-10-30
        self.assertEqual(result.scheduled_date, date(2026, 10, 30))
        self.assertEqual(result.position, 1)

    def test_urgent_mention_after_cutoff_next_day(self):
        """Urgent mentioned at or after 10:30 goes to next sitting day (BR-27)."""
        urgent_case = Case(
            case_id="C-URG-LATE",
            case_type="CRIMINAL",
            subject=SubjectType.CRIMINAL,
            party_ids=["P", "D"],
            filing_date=date(2026, 10, 29),
            urgency=True,
            assigned_bench="BENCH-01",
        )

        result = schedule_urgent_mention(
            case=urgent_case,
            bench=self.bench,
            current_date=self.listing_date,
            mentioned_at="10:35",
            current_board_size=20,
        )

        self.assertFalse(result.listed_same_day)
        self.assertEqual(result.scheduled_date, date(2026, 10, 30))

    def test_family_minor_designated_day_restriction(self):
        """Family case involving minor is listed ONLY on designated days (BR-26)."""
        # Thursday 2026-10-29 is designated day (3)
        case_minor = Case(
            case_id="C-MINOR",
            case_type="FAMILY",
            subject=SubjectType.FAMILY,
            party_ids=["P1", "P2"],
            filing_date=date(2026, 1, 1),
            involves_minor=True,
            assigned_bench="BENCH-01",
        )

        # On Thursday (designated), it lists successfully with IN_CAMERA flag
        cause_list_thu, _ = generate_cause_list(
            bench=self.bench,
            cases=[case_minor],
            listing_date=date(2026, 10, 29),
        )
        self.assertEqual(len(cause_list_thu), 1)
        self.assertIn(FLAG_IN_CAMERA, cause_list_thu[0].flags)

        # On Friday 2026-10-30 (weekday 4 != 3), it cannot be listed and is held back
        cause_list_fri, unreached_fri = generate_cause_list(
            bench=self.bench,
            cases=[case_minor],
            listing_date=date(2026, 10, 30),
        )
        self.assertEqual(len(cause_list_fri), 0)
        self.assertEqual(len(unreached_fri), 1)


if __name__ == "__main__":
    unittest.main()
