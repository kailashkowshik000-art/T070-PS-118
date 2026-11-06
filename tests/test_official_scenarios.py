"""Regression test suite for all official sample data planted edge cases and extra traps.

Team ID: T070
Problem Statement: PS-118
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from official_runner import OfficialRunner


class TestOfficialSampleScenarios(unittest.TestCase):
    """Test verification against official sample scenarios (EC-01 through EC-08 + extra traps)."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = Path("data/official_sample/T070-PS-118-sample-data")
        cls.output_dir = Path("output/official_test_run")
        cls.runner = OfficialRunner(data_dir=cls.data_dir, output_dir=cls.output_dir)
        cls.runner.run_commands_file(cls.data_dir / "commands.txt")
        cls.runner.write_output_csvs()

        # Load generated outputs
        with open(cls.output_dir / "admissions.csv", encoding="utf-8") as f:
            cls.admissions = {r["filing_id"]: r for r in csv.DictReader(f)}

        with open(cls.output_dir / "cause_lists.csv", encoding="utf-8") as f:
            cls.cause_lists = list(csv.DictReader(f))

        with open(cls.output_dir / "case_diary.csv", encoding="utf-8") as f:
            cls.case_diary = list(csv.DictReader(f))

        with open(cls.output_dir / "pendency.csv", encoding="utf-8") as f:
            cls.pendency = list(csv.DictReader(f))

    def test_ec01_limitation_holiday_extension(self):
        """EC-01: FIL-0021 limitation expires on May Day (2026-05-01) -> extends to Mon 2026-05-04."""
        row = self.admissions.get("FIL-0021")
        self.assertIsNotNone(row)
        self.assertEqual(row["limitation_last_day"], "2026-05-04")
        self.assertEqual(row["limitation_status"], "IN_TIME")
        self.assertEqual(row["admission_status"], "ADMITTED")

    def test_ec02_claim_value_slabs(self):
        """EC-02: FIL-0004 exactly 1 Lakh (fee 5000); FIL-0005 exactly 10 Lakh (fee 41000)."""
        row4 = self.admissions.get("FIL-0004")
        self.assertIsNotNone(row4)
        self.assertEqual(row4["court_fee_due"], "5000.00")
        self.assertEqual(row4["court_fee_paid"], "5000.00")
        self.assertEqual(row4["fee_status"], "PAID")

        row5 = self.admissions.get("FIL-0005")
        self.assertIsNotNone(row5)
        self.assertEqual(row5["court_fee_due"], "41000.00")
        self.assertEqual(row5["court_fee_paid"], "41000.00")
        self.assertEqual(row5["fee_status"], "PAID")

    def test_ec03_fourth_adjournment_medical_reason(self):
        """EC-03: LGC-0031 4th adjournment on 2026-04-20 with MEDICAL reason granted with Rs 2000 cost."""
        events = [r for r in self.case_diary if r["case_id"] == "LGC-0031" and r["event_date"] == "2026-04-20"]
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["result"], "ADJOURNMENT_REQUEST")
        self.assertEqual(ev["adjournments_petitioner"], "4")
        self.assertEqual(ev["cost"], "2000.00")
        self.assertEqual(ev["next_date"], "2026-05-04")

    def test_ec04_urgent_mention_on_full_board(self):
        """EC-04: FIL-0007 mentioned at 10:29 on full board on 2026-04-15; listed next sitting day 2026-04-16 pos 1."""
        list_entries = [
            r for r in self.cause_lists
            if r["bench_id"] == "BEN-03" and r["list_date"] == "2026-04-16" and r["case_id"] == "FIL-0007"
        ]
        self.assertEqual(len(list_entries), 1)
        self.assertEqual(list_entries[0]["serial_no"], "1")
        self.assertEqual(list_entries[0]["band"], "1")
        self.assertIn("URGENT", list_entries[0]["flags"])

    def test_ec05_bench_leave_rescheduling(self):
        """EC-05: LGC-0044 adjourned on 2026-06-09 skips leave day 2026-06-23 to next date 2026-06-25."""
        events = [r for r in self.case_diary if r["case_id"] == "LGC-0044" and r["event_date"] == "2026-06-09"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["next_date"], "2026-06-25")

    def test_ec06_unreached_bump_after_three_sittings(self):
        """EC-06: LGC-0008 NOT_REACHED on 3 consecutive sittings; 4th listing bumped with BUMPED flag."""
        listings = [r for r in self.cause_lists if r["case_id"] == "LGC-0008"]
        self.assertGreaterEqual(len(listings), 4)
        # Listing 4 on 2026-06-04 should carry BUMPED flag
        fourth_listing = [r for r in listings if r["list_date"] == "2026-06-04"][0]
        self.assertIn("BUMPED", fourth_listing["flags"])
        self.assertIn("CARRY_OVER", fourth_listing["flags"])

    def test_ec07_commercial_12_month_disposal_target(self):
        """EC-07: LGC-0017 crosses 12 months during adjournment; listed under Band 0 with 7-day interval."""
        listings = [r for r in self.cause_lists if r["case_id"] == "LGC-0017" and r["list_date"] == "2026-07-09"]
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["band"], "0")

        # Diary entry on 2026-07-09 should fix next date 7 days later (2026-07-16)
        events = [r for r in self.case_diary if r["case_id"] == "LGC-0017" and r["event_date"] == "2026-07-09"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["next_date"], "2026-07-16")

    def test_ec08_transfer_refused_due_to_party_conflict(self):
        """EC-08: LGC-0056 transfer to BEN-02 refused due to respondent conflict PTY-0309."""
        # Case stays on BEN-01 throughout diary events
        diary_entries = [r for r in self.case_diary if r["case_id"] == "LGC-0056"]
        self.assertTrue(all(r["bench_id"] == "BEN-01" for r in diary_entries))

    def test_extra_wrong_forum_exclusion(self):
        """FIL-0038: 75 wrong forum days excluded; limitation ends Sun 2026-05-24 -> Mon 2026-05-25."""
        row = self.admissions.get("FIL-0038")
        self.assertIsNotNone(row)
        self.assertEqual(row["limitation_last_day"], "2026-05-25")
        self.assertEqual(row["limitation_status"], "IN_TIME")
        self.assertEqual(row["admission_status"], "ADMITTED")

    def test_extra_condonation_and_time_barred(self):
        """FIL-0062 with condonation admitted; FIL-0053 without condonation rejected."""
        row62 = self.admissions.get("FIL-0062")
        self.assertIsNotNone(row62)
        self.assertEqual(row62["limitation_status"], "TIME_BARRED")
        self.assertEqual(row62["admission_status"], "ADMITTED")

        row53 = self.admissions.get("FIL-0053")
        self.assertIsNotNone(row53)
        self.assertEqual(row53["limitation_status"], "TIME_BARRED")
        self.assertEqual(row53["admission_status"], "REJECTED")

    def test_extra_court_fee_cap(self):
        """FIL-0011: claim 2 crore capped at Rs 3,00,000."""
        row = self.admissions.get("FIL-0011")
        self.assertIsNotNone(row)
        self.assertEqual(row["court_fee_due"], "300000.00")

    def test_extra_commercial_claim_threshold(self):
        """FIL-0014 (3 Lakh) allocated to civil roster; FIL-0015 (3,00,001) allocated to commercial bench."""
        row14 = self.admissions.get("FIL-0014")
        self.assertIn(row14["bench_id"], ("BEN-01", "BEN-02"))

        row15 = self.admissions.get("FIL-0015")
        self.assertEqual(row15["bench_id"], "BEN-05")

    def test_extra_fee_deficiency_and_cure(self):
        """FIL-0048 fee short, cured on day 7; FIL-0049 deficient fee never cured."""
        row48 = self.admissions.get("FIL-0048")
        self.assertEqual(row48["admission_status"], "DEFECTIVE")
        self.assertEqual(row48["fee_status"], "DEFICIENT")

        row49 = self.admissions.get("FIL-0049")
        self.assertEqual(row49["admission_status"], "DEFECTIVE")
        self.assertEqual(row49["fee_status"], "DEFICIENT")

    def test_extra_appeal_court_fee_half(self):
        """FIL-0025: appeal pays 50% of original fee = Rs 20,500."""
        row = self.admissions.get("FIL-0025")
        self.assertEqual(row["court_fee_due"], "20500.00")

    def test_extra_party_conflict_round_robin_skip(self):
        """FIL-0017: respondent conflict with BEN-01 skips to BEN-02."""
        row = self.admissions.get("FIL-0017")
        self.assertEqual(row["bench_id"], "BEN-02")

    def test_extra_adjournment_refusal_non_medical(self):
        """LGC-0005: respondent 4th request in ISSUES with COUNSEL_UNAVAILABLE is REFUSED."""
        events = [r for r in self.case_diary if r["case_id"] == "LGC-0005" and r["event_date"] == "2026-04-21"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["result"], "REFUSED")
        self.assertEqual(events[0]["next_date"], "2026-05-05")

    def test_extra_transfer_lifetime_limit(self):
        """LGC-0007: 1st transfer accepted, 2nd transfer refused; remains on BEN-01."""
        diary_entries = [r for r in self.case_diary if r["case_id"] == "LGC-0007"]
        # Later events after 2026-05-06 are all on BEN-01
        post_transfer = [r for r in diary_entries if r["event_date"] > "2026-05-06"]
        self.assertTrue(all(r["bench_id"] == "BEN-01" for r in post_transfer))

    def test_extra_family_minor_in_camera(self):
        """LGC-0051: family matter with minor listed on Wednesday for BEN-04 with IN_CAMERA flag."""
        listings = [r for r in self.cause_lists if r["case_id"] == "LGC-0051"]
        self.assertGreaterEqual(len(listings), 1)
        for entry in listings:
            list_dt = date.fromisoformat(entry["list_date"])
            self.assertEqual(list_dt.weekday(), 2)  # Wednesday
            self.assertIn("IN_CAMERA", entry["flags"])

    def test_extra_stage_progression_consent(self):
        """LGC-0026: jump from ISSUES to ARGUMENTS without consent refused on 2026-04-29; allowed on 2026-05-13."""
        diary = [r for r in self.case_diary if r["case_id"] == "LGC-0026"]
        # On 2026-04-29 stage remains ISSUES
        ev1 = [r for r in diary if r["event_date"] == "2026-04-29"][0]
        self.assertEqual(ev1["stage"], "ISSUES")
        # On 2026-05-13 stage advances to ARGUMENTS
        ev2 = [r for r in diary if r["event_date"] == "2026-05-13"][0]
        self.assertEqual(ev2["stage"], "ARGUMENTS")

    def test_pendency_rows_count_and_benches(self):
        """Check pendency.csv has 30 rows (6 reporting dates x 5 benches in exact order)."""
        self.assertEqual(len(self.pendency), 30)
        expected_benches = ["BEN-01", "BEN-02", "BEN-03", "BEN-04", "BEN-05"]
        for i in range(0, 30, 5):
            batch = [self.pendency[i + j]["bench_id"] for j in range(5)]
            self.assertEqual(batch, expected_benches)


if __name__ == "__main__":
    unittest.main()
