"""End-to-End Integration tests for Court Case Listing and Adjournment Scheduling Engine.

Team ID: T070
Problem Statement: PS-118
"""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from admission import process_admission
from allocation import BenchAllocator
from input_output import (
    load_benches,
    load_events,
    load_filings,
    load_holidays,
    save_admission_results,
    save_allocation_results,
    save_cause_lists,
    save_execution_summary,
    ValidationError,
)
from models import (
    AdmissionDecision,
    CaseStatus,
    PriorityBand,
)
from reporting import generate_execution_summary
from scheduling import generate_cause_list


class TestEndToEndIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = Path("data")
        self.output_dir = self.test_dir / "output"
        self.listing_date = date(2026, 10, 29)  # Thursday

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_complete_end_to_end_flow(self):
        """Execute full flow: INPUT -> ADMISSION -> ALLOCATION -> CAUSE LIST -> OUTPUT."""
        # 1. Load inputs
        holidays = load_holidays(self.data_dir / "holidays.json")
        benches = load_benches(self.data_dir / "benches.json")
        cases = load_filings(self.data_dir / "filings.json")
        cases_by_id = {c.case_id: c for c in cases}
        events = load_events(self.data_dir / "events.json", known_cases=cases_by_id)

        # Attach events
        for e in events:
            cases_by_id[e.case_id].adjournment_history.append(e)

        self.assertGreater(len(benches), 0)
        self.assertGreater(len(cases), 0)

        # 2. Case Admission
        admission_results = []
        for c in cases:
            res = process_admission(c, holidays=holidays)
            admission_results.append(res)

        admitted_cases = [c for c in cases if c.status == CaseStatus.ADMITTED]
        self.assertGreater(len(admitted_cases), 0)

        # Verify CS-2026-004 was rejected for limitation
        rej = next(r for r in admission_results if r.case_id == "CS-2026-004")
        self.assertEqual(rej.decision, AdmissionDecision.REJECTED)

        # Verify CS-2026-003 was marked defective for fees
        defective = next(r for r in admission_results if r.case_id == "CS-2026-003")
        self.assertEqual(defective.decision, AdmissionDecision.DEFECTIVE)

        # 3. Bench Allocation
        allocator = BenchAllocator(benches)
        allocation_results = []
        for c in admitted_cases:
            alloc_res = allocator.allocate(c)
            allocation_results.append(alloc_res)
            self.assertTrue(alloc_res.success)

        # Verify commercial case COM-2026-002 went to commercial bench
        com_alloc = next(r for r in allocation_results if r.case_id == "COM-2026-002")
        self.assertEqual(com_alloc.allocated_bench_id, "BENCH-COMM-01")

        # Verify conflicted case CS-2026-010 avoided BENCH-CIVIL-01
        conf_alloc = next(r for r in allocation_results if r.case_id == "CS-2026-010")
        self.assertNotEqual(conf_alloc.allocated_bench_id, "BENCH-CIVIL-01")

        # 4. Cause-List Generation
        cause_lists = {}
        total_listed = 0
        for b in benches:
            cl, _ = generate_cause_list(b, admitted_cases, self.listing_date)
            cause_lists[b.bench_id] = cl
            total_listed += len(cl)

        self.assertGreater(total_listed, 0)

        # 5. Save Outputs and Validate
        save_admission_results(admission_results, self.output_dir / "admission_results.json")
        save_allocation_results(allocation_results, self.output_dir / "allocation_results.json")
        save_cause_lists(cause_lists, self.output_dir / "cause_lists.json")

        summary_text = generate_execution_summary(
            run_date=self.listing_date,
            filings_count=len(cases),
            admitted_count=len(admitted_cases),
            defective_count=sum(1 for r in admission_results if r.decision == AdmissionDecision.DEFECTIVE),
            rejected_count=sum(1 for r in admission_results if r.decision == AdmissionDecision.REJECTED),
            allocated_count=len(allocation_results),
            listed_count=total_listed,
        )
        save_execution_summary(summary_text, self.output_dir / "execution_summary.txt")

        # Check files exist on disk and are non-empty
        self.assertTrue((self.output_dir / "admission_results.json").exists())
        self.assertTrue((self.output_dir / "allocation_results.json").exists())
        self.assertTrue((self.output_dir / "cause_lists.json").exists())
        self.assertTrue((self.output_dir / "execution_summary.txt").exists())

        # Validate JSON content integrity
        with open(self.output_dir / "admission_results.json", "r", encoding="utf-8") as f:
            adm_json = json.load(f)
            self.assertEqual(len(adm_json), len(cases))

        with open(self.output_dir / "cause_lists.json", "r", encoding="utf-8") as f:
            cl_json = json.load(f)
            self.assertIn("BENCH-COMM-01", cl_json)

    def test_invalid_input_duplicate_case_id(self):
        """Validates that duplicate case IDs raise ValidationError."""
        dup_file = self.test_dir / "dup_filings.json"
        dup_data = [
            {
                "case_id": "DUP-01",
                "case_type": "CIVIL",
                "subject": "CIVIL",
                "party_ids": ["P1"],
                "filing_date": "2026-01-01",
            },
            {
                "case_id": "DUP-01",
                "case_type": "CIVIL",
                "subject": "CIVIL",
                "party_ids": ["P2"],
                "filing_date": "2026-01-02",
            },
        ]
        with open(dup_file, "w", encoding="utf-8") as f:
            json.dump(dup_data, f)

        with self.assertRaises(ValidationError) as ctx:
            load_filings(dup_file)
        self.assertIn("Duplicate case_id", str(ctx.exception))

    def test_unknown_case_reference_in_events(self):
        """Validates that events referencing non-existent case IDs raise ValidationError."""
        evt_file = self.test_dir / "bad_events.json"
        evt_data = [
            {
                "event_id": "EVT-ERR",
                "case_id": "NON_EXISTENT_CASE",
                "hearing_date": "2026-10-29",
                "outcome": "HEARD",
            }
        ]
        with open(evt_file, "w", encoding="utf-8") as f:
            json.dump(evt_data, f)

        known_cases = {}
        with self.assertRaises(ValidationError) as ctx:
            load_events(evt_file, known_cases=known_cases)
        self.assertIn("references unknown case_id", str(ctx.exception))

    def test_end_to_end_full_pipeline_with_all_reports(self):
        """Execute run_pipeline via main module and verify all 13 output files are generated."""
        from main import run_pipeline

        out_dir = self.test_dir / "pipeline_out"
        code = run_pipeline(
            data_dir=self.data_dir,
            output_dir=out_dir,
            listing_date=self.listing_date,
            verbose=False,
        )
        self.assertEqual(code, 0)

        # Check all 13 output files
        expected_files = [
            "admission_results.json",
            "allocation_results.json",
            "cause_lists.json",
            "cause_lists.txt",
            "case_diaries.json",
            "case_diaries.txt",
            "evidence_delay_report.json",
            "evidence_delay_report.txt",
            "principal_judge_report.json",
            "principal_judge_report.txt",
            "pendency_report.json",
            "pendency_report.txt",
            "execution_summary.txt",
        ]
        for fname in expected_files:
            target_f = out_dir / fname
            self.assertTrue(target_f.exists(), f"Missing expected output file: {fname}")
            self.assertGreater(target_f.stat().st_size, 0, f"Output file is empty: {fname}")

    def test_end_to_end_multi_sitting_simulation_pipeline(self):
        """Execute run_pipeline with simulate_until covering consecutive sitting days."""
        from main import run_pipeline

        out_dir = self.test_dir / "sim_out"
        code = run_pipeline(
            data_dir=self.data_dir,
            output_dir=out_dir,
            listing_date=date(2026, 10, 29),
            simulate_until=date(2026, 10, 31),
            verbose=False,
        )
        self.assertEqual(code, 0)
        self.assertTrue((out_dir / "cause_lists.json").exists())

    def test_invalid_input_malformed_json(self):
        """Validates that malformed JSON files raise appropriate exceptions."""
        bad_json_file = self.test_dir / "malformed.json"
        with open(bad_json_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json content: true ")

        with self.assertRaises(json.JSONDecodeError):
            load_filings(bad_json_file)

    def test_invalid_input_duplicate_bench_id(self):
        """Validates that duplicate bench IDs raise ValidationError."""
        dup_bench_file = self.test_dir / "dup_benches.json"
        dup_data = [
            {"bench_id": "B-DUP", "subject_jurisdictions": ["CIVIL"]},
            {"bench_id": "B-DUP", "subject_jurisdictions": ["COMMERCIAL"]},
        ]
        with open(dup_bench_file, "w", encoding="utf-8") as f:
            json.dump(dup_data, f)

        with self.assertRaises(ValidationError) as ctx:
            load_benches(dup_bench_file)
        self.assertIn("Duplicate bench_id", str(ctx.exception))

    def test_invalid_input_negative_claim_value(self):
        """Validates that negative monetary values raise ValidationError."""
        bad_file = self.test_dir / "neg_filings.json"
        bad_data = [
            {
                "case_id": "C-NEG",
                "case_type": "CIVIL",
                "subject": "CIVIL",
                "party_ids": ["P1"],
                "filing_date": "2026-01-01",
                "claim_value": "-1000.00",
            }
        ]
        with open(bad_file, "w", encoding="utf-8") as f:
            json.dump(bad_data, f)

        with self.assertRaises(ValidationError) as ctx:
            load_filings(bad_file)
        self.assertIn("cannot be negative", str(ctx.exception))

    def test_invalid_input_invalid_date_format(self):
        """Validates that malformed date strings raise ValidationError."""
        bad_file = self.test_dir / "bad_date.json"
        bad_data = [
            {
                "case_id": "C-DATE",
                "case_type": "CIVIL",
                "subject": "CIVIL",
                "party_ids": ["P1"],
                "filing_date": "not-a-date",
            }
        ]
        with open(bad_file, "w", encoding="utf-8") as f:
            json.dump(bad_data, f)

        with self.assertRaises(ValidationError) as ctx:
            load_filings(bad_file)
        self.assertIn("Invalid date format", str(ctx.exception))

    def test_multi_sitting_json_and_text_reports_agree(self):
        """Verifies that cause_lists.json and cause_lists.txt agree exactly on bench IDs and sitting dates."""
        from main import run_pipeline

        out_dir = self.test_dir / "sim_match_out"
        code = run_pipeline(
            data_dir=self.data_dir,
            output_dir=out_dir,
            listing_date=date(2026, 11, 5),
            simulate_until=date(2026, 11, 6),
            verbose=False,
        )
        self.assertEqual(code, 0)

        # 1. Read JSON
        json_path = out_dir / "cause_lists.json"
        with open(json_path, "r", encoding="utf-8") as f:
            cl_json = json.load(f)

        # 2. Read Text
        txt_path = out_dir / "cause_lists.txt"
        with open(txt_path, "r", encoding="utf-8") as f:
            txt_content = f.read()

        # Check that 2026-11-05 and 2026-11-06 blocks exist in text
        self.assertIn("Sitting Date: 2026-11-05", txt_content)
        self.assertIn("Sitting Date: 2026-11-06", txt_content)

        # Verify that for every bench and sitting date in JSON, the text contains the exact matching bench and date header
        for key, entries in cl_json.items():
            if entries:
                sit_dt = entries[0]["listing_date"]
                bench = entries[0]["bench_id"]

                expected_bench_header = f"DISTRICT COURT CAUSE LIST - BENCH: {bench}"
                expected_date_header = f"Sitting Date: {sit_dt}"

                self.assertIn(expected_bench_header, txt_content)
                self.assertIn(expected_date_header, txt_content)

                # Ensure every case listed in JSON is present in text
                for entry in entries:
                    self.assertIn(entry["case_id"], txt_content)


if __name__ == "__main__":
    unittest.main()
