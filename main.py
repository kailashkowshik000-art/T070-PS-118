"""Command-line entry point for Court Case Listing and Adjournment Scheduling Engine.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys

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
    AdmissionResult,
    AllocationResult,
    CaseStatus,
)
from reporting import (
    generate_cause_list_report,
    generate_execution_summary,
)
from scheduling import generate_cause_list


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PS-118: Court Case Listing and Adjournment Scheduling Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Path to directory containing input JSON files (benches, holidays, filings, events)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Path to directory where output JSON and reports will be saved",
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2026-10-29",
        help="Target date for cause-list generation in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed cause lists and diaries to standard output",
    )
    return parser.parse_args()


def run_pipeline(
    data_dir: Path | str,
    output_dir: Path | str,
    listing_date: date,
    verbose: bool = False,
) -> int:
    """Execute the end-to-end court registry pipeline."""
    data_path = Path(data_dir)
    output_path = Path(output_dir)

    # 1. Validate data directory
    if not data_path.exists() or not data_path.is_dir():
        sys.stderr.write(f"Error: Data directory '{data_path}' does not exist or is not a directory.\n")
        return 1

    try:
        # 2. Load inputs
        holidays_file = data_path / "holidays.json"
        benches_file = data_path / "benches.json"
        filings_file = data_path / "filings.json"
        events_file = data_path / "events.json"

        holidays = load_holidays(holidays_file)
        benches = load_benches(benches_file)
        cases = load_filings(filings_file)
        cases_by_id = {c.case_id: c for c in cases}
        events = load_events(events_file, known_cases=cases_by_id)

        # Attach events to case histories
        for event in events:
            cases_by_id[event.case_id].adjournment_history.append(event)

        # 3. Process Admission
        admission_results: list[AdmissionResult] = []
        for case in cases:
            res = process_admission(case, holidays=holidays)
            admission_results.append(res)

        admitted_cases = [c for c in cases if c.status == CaseStatus.ADMITTED]
        defective_count = sum(1 for r in admission_results if r.decision == AdmissionDecision.DEFECTIVE)
        rejected_count = sum(1 for r in admission_results if r.decision == AdmissionDecision.REJECTED)

        # 4. Bench Allocation
        allocator = BenchAllocator(benches)
        allocation_results: list[AllocationResult] = []

        for case in admitted_cases:
            alloc_res = allocator.allocate(case, on_date=listing_date)
            allocation_results.append(alloc_res)

        # Also record non-admitted cases in allocation report for complete visibility
        for r in admission_results:
            if r.decision != AdmissionDecision.ADMITTED:
                allocation_results.append(
                    AllocationResult(
                        case_id=r.case_id,
                        allocated_bench_id=None,
                        success=False,
                        reason=f"Not admitted ({r.decision.value}): {r.defect_or_rejection_reason}",
                    )
                )

        # Sort allocation results deterministically
        allocation_results.sort(key=lambda a: a.case_id)

        # 5. Cause-List Generation
        cause_lists: dict[str, list] = {}
        total_listed = 0

        for bench in benches:
            cl_entries, _ = generate_cause_list(
                bench=bench,
                cases=admitted_cases,
                listing_date=listing_date,
            )
            cause_lists[bench.bench_id] = cl_entries
            total_listed += len(cl_entries)

        # 6. Save Outputs
        output_path.mkdir(parents=True, exist_ok=True)
        save_admission_results(admission_results, output_path / "admission_results.json")
        save_allocation_results(allocation_results, output_path / "allocation_results.json")
        save_cause_lists(cause_lists, output_path / "cause_lists.json")

        summary_text = generate_execution_summary(
            run_date=listing_date,
            filings_count=len(cases),
            admitted_count=len(admitted_cases),
            defective_count=defective_count,
            rejected_count=rejected_count,
            allocated_count=sum(1 for a in allocation_results if a.success),
            listed_count=total_listed,
        )
        save_execution_summary(summary_text, output_path / "execution_summary.txt")

        # 7. Print Summary
        print(summary_text)

        if verbose:
            print("\nDetailed Cause Lists:")
            for bench_id, entries in cause_lists.items():
                if entries:
                    print(generate_cause_list_report(bench_id, listing_date, entries))

        return 0

    except (ValidationError, FileNotFoundError) as err:
        sys.stderr.write(f"Validation Error: {err}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected Execution Error: {exc}\n")
        return 2


def main() -> None:
    args = parse_arguments()
    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        sys.stderr.write(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.\n")
        sys.exit(1)

    exit_code = run_pipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        listing_date=target_date,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
