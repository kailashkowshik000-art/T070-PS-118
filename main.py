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
from hearings import HearingManager
from input_output import (
    load_benches,
    load_events,
    load_filings,
    load_holidays,
    save_admission_results,
    save_allocation_results,
    save_case_diaries,
    save_cause_lists,
    save_cause_lists_text,
    save_evidence_delay_report,
    save_execution_summary,
    save_pendency_report,
    save_principal_judge_report,
    ValidationError,
)
from models import (
    AdmissionDecision,
    AdmissionResult,
    AllocationResult,
    CaseStatus,
)
from reporting import (
    generate_all_case_diaries,
    generate_cause_list_report,
    generate_evidence_delay_report,
    generate_execution_summary,
    generate_pendency_report,
    generate_pendency_report_text,
    generate_principal_judge_report,
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
        "--simulate-until",
        type=str,
        default=None,
        help="Optional end date (YYYY-MM-DD) for multi-sitting simulation run",
    )
    parser.add_argument(
        "--commands",
        type=str,
        default=None,
        help="Path to official commands.txt file for command-driven simulation run",
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
    simulate_until: date | None = None,
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

        hearing_manager = HearingManager(benches=benches, holidays=holidays)

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

        # 5. Process Hearing Events & Generate Cause Lists
        cause_lists: dict[str, list] = {}
        total_listed = 0

        if simulate_until and simulate_until >= listing_date:
            # Multi-sitting simulation
            from datetime import timedelta
            sitting_dates = [listing_date + timedelta(days=i) for i in range((simulate_until - listing_date).days + 1)]
            sim_summaries, cause_lists = hearing_manager.simulate_sittings(
                cases=admitted_cases,
                events=events,
                sitting_dates=sitting_dates,
            )
            total_listed = sum(len(entries) for entries in cause_lists.values())
        else:
            # Standard single sitting listing
            # Process prior historical events up to listing date
            for event in sorted(events, key=lambda e: e.hearing_date):
                if event.hearing_date <= listing_date:
                    c = cases_by_id.get(event.case_id)
                    if c:
                        hearing_manager.process_hearing_event(c, event)

            for bench in benches:
                cl_entries, _ = generate_cause_list(
                    bench=bench,
                    cases=admitted_cases,
                    listing_date=listing_date,
                )
                cause_lists[bench.bench_id] = cl_entries
                total_listed += len(cl_entries)

        # 6. Generate All Reports (BR-33, BR-49, BR-50, BR-51)
        output_path.mkdir(parents=True, exist_ok=True)

        # A. Admission & Allocation results
        save_admission_results(admission_results, output_path / "admission_results.json")
        save_allocation_results(allocation_results, output_path / "allocation_results.json")

        # B. Cause Lists (JSON + Formatted Text) (BR-49)
        save_cause_lists(cause_lists, output_path / "cause_lists.json")
        cause_lists_text_blocks = []
        for b_id, entries in cause_lists.items():
            if entries:
                actual_date = entries[0].listing_date
                actual_bench = entries[0].bench_id
                cause_lists_text_blocks.append(generate_cause_list_report(actual_bench, actual_date, entries))
        save_cause_lists_text("\n\n".join(cause_lists_text_blocks), output_path / "cause_lists.txt")

        # C. Case Diaries (BR-50)
        diaries_text = generate_all_case_diaries(cases)
        save_case_diaries(diaries_text, cases, output_path / "case_diaries.txt", output_path / "case_diaries.json")

        # D. Evidence Delay Report (BR-33)
        ev_text, ev_dict = generate_evidence_delay_report(cases, as_of_date=listing_date)
        save_evidence_delay_report(ev_text, ev_dict, output_path / "evidence_delay_report.txt", output_path / "evidence_delay_report.json")

        # E. Principal District Judge Report (BR-33, BR-51)
        pj_text, pj_dict = generate_principal_judge_report(cases, benches, as_of_date=listing_date, cause_lists=cause_lists)
        save_principal_judge_report(pj_text, pj_dict, output_path / "principal_judge_report.txt", output_path / "principal_judge_report.json")

        # F. Pendency Report (BR-51)
        pend_dict = generate_pendency_report(cases, as_of_date=listing_date)
        pend_text = generate_pendency_report_text(pend_dict)
        save_pendency_report(pend_text, pend_dict, output_path / "pendency_report.txt", output_path / "pendency_report.json")

        # G. Execution Summary
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
                    actual_date = entries[0].listing_date
                    actual_bench = entries[0].bench_id
                    print(generate_cause_list_report(actual_bench, actual_date, entries))
            print("\n" + pj_text)

        return 0

    except (ValidationError, FileNotFoundError) as err:
        sys.stderr.write(f"Validation Error: {err}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected Execution Error: {exc}\n")
        return 2


def main() -> None:
    args = parse_arguments()

    if args.commands:
        from official_runner import OfficialRunner
        runner = OfficialRunner(data_dir=args.data_dir, output_dir=args.output_dir)
        runner.run_commands_file(args.commands)
        runner.write_output_csvs()
        print(f"Official command run complete. CSV outputs written to {args.output_dir}:")
        print(f"  - admissions.csv: {len(runner.admissions_rows)} rows")
        print(f"  - cause_lists.csv: {len(runner.cause_lists_rows)} rows")
        print(f"  - case_diary.csv: {len(runner.case_diary_rows)} rows")
        print(f"  - pendency.csv: {len(runner.pendency_rows)} rows")
        sys.exit(0)

    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        sys.stderr.write(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.\n")
        sys.exit(1)

    sim_until = None
    if args.simulate_until:
        try:
            sim_until = datetime.strptime(args.simulate_until, "%Y-%m-%d").date()
        except ValueError:
            sys.stderr.write(f"Error: Invalid simulate-until date format '{args.simulate_until}'. Expected YYYY-MM-DD.\n")
            sys.exit(1)

    exit_code = run_pipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        listing_date=target_date,
        simulate_until=sim_until,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
