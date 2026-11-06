"""Official sample data pack runner and command stream interpreter.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any

from admission import (
    calculate_court_fee,
    calculate_limitation_deadline,
)
from allocation import BenchAllocator
from config import (
    COMMERCIAL_ADJOURNMENT_COST,
    COMMERCIAL_CLAIM_THRESHOLD,
    COMMERCIAL_DISPOSAL_TARGET_DAYS,
    DAILY_BOARD_CAPACITY,
    DAILY_FINAL_HEARING_CAP,
    EVIDENCE_DELAY_THRESHOLD_DAYS,
    FEE_CURE_PERIOD_DAYS,
    FLAG_BUMPED,
    FLAG_CARRY_OVER,
    FLAG_DELAY,
    FLAG_DELAY_CONDONATION_PENDING,
    FLAG_IN_CAMERA,
    FLAG_OVERBOARD,
    FLAG_URGENT,
    MAX_ADJOURNMENTS_PER_STAGE,
    MIN_NEXT_DATE_INTERVAL_DAYS,
    MIN_NEXT_DATE_URGENT_INTERVAL_DAYS,
    PARTY_ADJOURNMENT_COST,
    UNREACHED_ESCALATION_THRESHOLD,
    URGENT_MENTION_CUTOFF_TIME,
)
from hearings import STAGE_ORDER
from models import (
    AdjournmentReason,
    AdmissionDecision,
    Bench,
    Case,
    CaseStage,
    CaseStatus,
    HearingEvent,
    HearingOutcome,
    PriorityBand,
    SubjectType,
)
from scheduling import determine_priority_band

OFFICIAL_FLAGS_ORDER = [
    FLAG_URGENT,
    FLAG_CARRY_OVER,
    FLAG_BUMPED,
    FLAG_OVERBOARD,
    FLAG_DELAY,
    FLAG_IN_CAMERA,
    FLAG_DELAY_CONDONATION_PENDING,
]


def format_flags(flags_set: set[str] | list[str]) -> str:
    """Format flags as a deterministic semicolon-separated string matching official schema."""
    present = set(flags_set)
    ordered = [f for f in OFFICIAL_FLAGS_ORDER if f in present]
    return ";".join(ordered)


def parse_day_list(day_str: str) -> list[int]:
    """Parse semicolon-separated day string like MON;TUE;WED;THU;FRI to day numbers (0..6)."""
    if not day_str or not day_str.strip():
        return []
    day_map = {
        "MON": 0,
        "TUE": 1,
        "WED": 2,
        "THU": 3,
        "FRI": 4,
        "SAT": 5,
        "SUN": 6,
    }
    result = []
    for part in day_str.split(";"):
        p = part.strip().upper()
        if p in day_map:
            result.append(day_map[p])
    return result


class OfficialRunner:
    """Loads official CSV datasets, executes the command stream, and produces evaluation CSVs."""

    def __init__(self, data_dir: Path | str, output_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.holidays: set[date] = set()
        self.benches: dict[str, Bench] = {}
        self.bench_list: list[Bench] = []
        self.parties: dict[str, dict[str, str]] = {}
        self.pending_cases: dict[str, Case] = {}
        self.filings_data: dict[str, dict[str, str]] = {}

        # Tracking state
        self.active_cases: dict[str, Case] = {}  # All cases known to court (pending + admitted filings)
        self.admissions_rows: list[list[str]] = []
        self.cause_lists_rows: list[list[str]] = []
        self.case_diary_rows: list[list[str]] = []
        self.pendency_rows: list[list[str]] = []

        # Monthly decided tracking: bench_id -> dict of (year, month) -> count
        self.decided_by_month: dict[str, dict[tuple[int, int], int]] = {}

        # Round robin allocator
        self.allocator: BenchAllocator | None = None

        self._load_data()

    def _load_data(self) -> None:
        # 1. Holidays
        holidays_file = self.data_dir / "holidays.csv"
        with open(holidays_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dt = datetime.strptime(row["holiday_date"], "%Y-%m-%d").date()
                self.holidays.add(dt)

        # 2. Benches
        benches_file = self.data_dir / "benches.csv"
        with open(benches_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bench_id = row["bench_id"]
                presiding = row["presiding_officer"]
                subject_enum = SubjectType(row["subject"])
                sitting_days = parse_day_list(row["sitting_days"])
                in_camera_days = parse_day_list(row.get("in_camera_days", ""))
                capacity = int(row["board_capacity"])
                max_fh = int(row["max_final_hearing"])

                bench = Bench(
                    bench_id=bench_id,
                    subject_jurisdictions=[subject_enum],
                    commercial_jurisdiction=(subject_enum == SubjectType.COMMERCIAL),
                    sitting_days=sitting_days,
                    daily_board_capacity=capacity,
                    presiding_officer=presiding,
                    in_camera_days=in_camera_days,
                    max_final_hearing=max_fh,
                )
                self.benches[bench_id] = bench
                self.bench_list.append(bench)
                self.decided_by_month[bench_id] = {}

        self.bench_list.sort(key=lambda b: b.bench_id)
        self.allocator = BenchAllocator(self.bench_list)

        # 3. Bench Leave
        leave_file = self.data_dir / "bench_leave.csv"
        with open(leave_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                b_id = row["bench_id"]
                l_from = datetime.strptime(row["leave_from"], "%Y-%m-%d").date()
                l_to = datetime.strptime(row["leave_to"], "%Y-%m-%d").date()
                curr = l_from
                while curr <= l_to:
                    if b_id in self.benches:
                        self.benches[b_id].leave_dates.add(curr)
                    curr += timedelta(days=1)

        # 4. Bench Conflicts
        conflict_file = self.data_dir / "bench_conflicts.csv"
        with open(conflict_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                b_id = row["bench_id"]
                p_id = row["party_id"]
                if b_id in self.benches:
                    self.benches[b_id].conflict_party_ids.add(p_id)

        # 5. Parties
        parties_file = self.data_dir / "parties.csv"
        with open(parties_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.parties[row["party_id"]] = row

        # 6. Pending cases (Docket on 2026-04-01)
        pending_file = self.data_dir / "pending_cases.csv"
        with open(pending_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row["case_id"]
                f_date = datetime.strptime(row["filing_date"], "%Y-%m-%d").date()
                c_val = Decimal(row["claim_value"])
                stage_enum = CaseStage(row["stage"])
                stage_since = datetime.strptime(row["stage_since"], "%Y-%m-%d").date()
                adj_p = int(row["adjournments_petitioner_stage"])
                adj_r = int(row["adjournments_respondent_stage"])
                adj_tot = int(row["adjournments_total"])
                p_heard = row["part_heard"].lower() == "true"
                urg = row["urgent"].lower() == "true"
                minor = row["minor_involved"].lower() == "true"
                nxt_date = datetime.strptime(row["next_date"], "%Y-%m-%d").date()
                is_comm = row["is_commercial"].lower() == "true"
                sub_enum = SubjectType(row["subject"])

                flags: set[str] = set()
                if urg:
                    flags.add(FLAG_URGENT)
                if minor:
                    flags.add(FLAG_IN_CAMERA)

                case = Case(
                    case_id=cid,
                    case_type=row["case_type"],
                    subject=sub_enum,
                    party_ids=[row["petitioner_id"], row["respondent_id"]],
                    petitioner_id=row["petitioner_id"],
                    respondent_id=row["respondent_id"],
                    filing_date=f_date,
                    claim_value=c_val,
                    urgency=urg,
                    status=CaseStatus.LISTED,
                    stage=stage_enum,
                    stage_start_date=stage_since,
                    stage_since=stage_since,
                    adjournments_petitioner_stage=adj_p,
                    adjournments_respondent_stage=adj_r,
                    adjournments_total=adj_tot,
                    is_part_heard=p_heard,
                    involves_minor=minor,
                    assigned_bench=row["bench_id"],
                    next_hearing_date=nxt_date,
                    flags=flags,
                    is_commercial=is_comm,
                )
                self.pending_cases[cid] = case
                self.active_cases[cid] = case

        # 7. Filings
        filings_file = self.data_dir / "filings.csv"
        with open(filings_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.filings_data[row["filing_id"]] = row

    def get_bench_board_count(self, bench_id: str, on_date: date) -> int:
        """Count how many cases are already scheduled on bench on on_date."""
        count = 0
        for c in self.active_cases.values():
            if c.assigned_bench == bench_id and c.next_hearing_date == on_date and c.status != CaseStatus.DECIDED:
                count += 1
        return count

    def find_next_date_for_case(
        self,
        bench: Bench,
        from_date: date,
        is_urgent: bool,
        is_commercial_overdue: bool,
        involves_minor: bool,
    ) -> tuple[date, bool]:
        """Find the earliest eligible sitting date with capacity for bench."""
        min_interval = MIN_NEXT_DATE_URGENT_INTERVAL_DAYS if (is_urgent or is_commercial_overdue) else MIN_NEXT_DATE_INTERVAL_DAYS
        earliest_date = from_date + timedelta(days=min_interval)
        max_date = from_date + timedelta(days=60)

        in_cam_days = bench.in_camera_days if (bench.in_camera_days and involves_minor) else []

        current = earliest_date
        while current <= max_date:
            if (
                current.weekday() in bench.sitting_days
                and current not in bench.leave_dates
                and current not in self.holidays
            ):
                if in_cam_days and current.weekday() not in in_cam_days:
                    current += timedelta(days=1)
                    continue

                if self.get_bench_board_count(bench.bench_id, current) < bench.daily_board_capacity:
                    return current, False
            current += timedelta(days=1)

        # Day 60 fallback (BR-42)
        fallback = max_date
        while (
            fallback.weekday() not in bench.sitting_days
            or fallback in bench.leave_dates
            or fallback in self.holidays
            or (in_cam_days and fallback.weekday() not in in_cam_days)
        ):
            fallback += timedelta(days=1)
        return fallback, True

    def process_file_command(self, filing_id: str) -> None:
        """Process FILE command: evaluate limitation -> court fee -> roster allocation -> first date."""
        row = self.filings_data.get(filing_id)
        if not row:
            raise ValueError(f"Filing {filing_id} not found in filings.csv")

        filing_ts = datetime.strptime(row["filing_ts"], "%Y-%m-%d %H:%M:%S")
        filing_date = filing_ts.date()
        case_type = row["case_type"]
        subject_enum = SubjectType(row["subject"])
        is_comm = row["is_commercial"].lower() == "true"
        petitioner_id = row["petitioner_id"]
        respondent_id = row["respondent_id"]
        party_ids = [petitioner_id, respondent_id]
        claim_val = Decimal(row["claim_value"])
        paid_val = Decimal(row["court_fee_paid"])
        urgent = row["urgent"].lower() == "true"
        minor = row["minor_involved"].lower() == "true"
        condonation = row["condonation_application"].lower() == "true"
        wrong_forum_days = int(row.get("wrong_forum_days", 0))

        # Base date for limitation
        has_limitation = True
        if row.get("impugned_order_date"):
            base_date = datetime.strptime(row["impugned_order_date"], "%Y-%m-%d").date()
        elif row.get("amount_due_date"):
            base_date = datetime.strptime(row["amount_due_date"], "%Y-%m-%d").date()
        elif row.get("cause_of_action_date"):
            base_date = datetime.strptime(row["cause_of_action_date"], "%Y-%m-%d").date()
        else:
            base_date = filing_date
            if "BAIL" in case_type or "FAMILY" in case_type or "CRIMINAL" in case_type:
                has_limitation = False

        if has_limitation:
            limitation_last_day = calculate_limitation_deadline(
                case_type=case_type,
                base_date=base_date,
                wrong_forum_days=wrong_forum_days,
                holidays=self.holidays,
            )
            is_time_barred = filing_date > limitation_last_day
            limitation_status = "TIME_BARRED" if is_time_barred else "IN_TIME"
            lim_last_day_str = limitation_last_day.strftime("%Y-%m-%d")
        else:
            limitation_last_day = filing_date
            is_time_barred = False
            limitation_status = "IN_TIME"
            lim_last_day_str = ""

        # Court fee check
        is_appeal = "APPEAL" in case_type.upper()
        fee_due = calculate_court_fee(claim_val, is_appeal=is_appeal)
        fee_due_str = f"{fee_due:.2f}"
        fee_paid_str = f"{paid_val:.2f}"

        is_fee_deficient = paid_val < fee_due
        fee_status = "DEFICIENT" if is_fee_deficient else "PAID"

        # Determine admission status
        flags: set[str] = set()
        if urgent:
            flags.add(FLAG_URGENT)
        if minor:
            flags.add(FLAG_IN_CAMERA)

        bench_id_str = ""
        first_date_str = ""
        admission_status = ""

        if is_time_barred and not condonation:
            admission_status = "REJECTED"
        elif is_fee_deficient:
            admission_status = "DEFECTIVE"
            # Defective filing is not allocated until cured
        else:
            admission_status = "ADMITTED"
            if is_time_barred and condonation:
                flags.add(FLAG_DELAY_CONDONATION_PENDING)

            # Roster allocation
            alloc_case = Case(
                case_id=filing_id,
                case_type=case_type,
                subject=subject_enum,
                party_ids=party_ids,
                petitioner_id=petitioner_id,
                respondent_id=respondent_id,
                filing_date=filing_date,
                claim_value=claim_val,
                court_fee_paid=paid_val,
                urgency=urgent,
                involves_minor=minor,
                is_commercial=is_comm,
                flags=flags,
            )
            alloc_res = self.allocator.allocate(alloc_case)
            if alloc_res.success and alloc_case.assigned_bench:
                bench_id_str = alloc_case.assigned_bench
                bench = self.benches[bench_id_str]
                first_date, is_overboard = self.find_next_date_for_case(
                    bench=bench,
                    from_date=filing_date,
                    is_urgent=urgent,
                    is_commercial_overdue=False,
                    involves_minor=minor,
                )
                first_date_str = first_date.strftime("%Y-%m-%d")
                alloc_case.next_hearing_date = first_date
                alloc_case.status = CaseStatus.LISTED
                alloc_case.stage = CaseStage.PLEADINGS
                alloc_case.stage_start_date = filing_date
                alloc_case.stage_since = filing_date
                if is_overboard:
                    alloc_case.flags.add(FLAG_OVERBOARD)
                self.active_cases[filing_id] = alloc_case

        # Row in admissions.csv
        # Columns: filing_id,limitation_last_day,limitation_status,court_fee_due,court_fee_paid,fee_status,bench_id,first_date,admission_status
        self.admissions_rows.append([
            filing_id,
            lim_last_day_str,
            limitation_status,
            fee_due_str,
            fee_paid_str,
            fee_status,
            bench_id_str,
            first_date_str,
            admission_status,
        ])

    def process_fee_cure_command(self, filing_id: str, cure_date_str: str, amount_str: str) -> None:
        """Process FEE_CURE: deficit fee paid; if within 7 days, registers case and allocates bench."""
        cure_date = datetime.strptime(cure_date_str, "%Y-%m-%d").date()
        cure_amount = Decimal(amount_str)

        row = self.filings_data.get(filing_id)
        if not row:
            return

        filing_ts = datetime.strptime(row["filing_ts"], "%Y-%m-%d %H:%M:%S")
        filing_date = filing_ts.date()

        # Check cure period (BR-17: 7 days)
        if (cure_date - filing_date).days <= FEE_CURE_PERIOD_DAYS:
            # Successfully cured -> register and allocate
            case_type = row["case_type"]
            subject_enum = SubjectType(row["subject"])
            is_comm = row["is_commercial"].lower() == "true"
            petitioner_id = row["petitioner_id"]
            respondent_id = row["respondent_id"]
            party_ids = [petitioner_id, respondent_id]
            claim_val = Decimal(row["claim_value"])
            total_paid = Decimal(row["court_fee_paid"]) + cure_amount
            urgent = row["urgent"].lower() == "true"
            minor = row["minor_involved"].lower() == "true"

            flags: set[str] = set()
            if urgent:
                flags.add(FLAG_URGENT)
            if minor:
                flags.add(FLAG_IN_CAMERA)

            case = Case(
                case_id=filing_id,
                case_type=case_type,
                subject=subject_enum,
                party_ids=party_ids,
                petitioner_id=petitioner_id,
                respondent_id=respondent_id,
                filing_date=filing_date,
                claim_value=claim_val,
                court_fee_paid=total_paid,
                urgency=urgent,
                involves_minor=minor,
                is_commercial=is_comm,
                flags=flags,
            )
            alloc_res = self.allocator.allocate(case)
            if alloc_res.success and case.assigned_bench:
                bench = self.benches[case.assigned_bench]
                first_date, is_overboard = self.find_next_date_for_case(
                    bench=bench,
                    from_date=cure_date,
                    is_urgent=urgent,
                    is_commercial_overdue=False,
                    involves_minor=minor,
                )
                case.next_hearing_date = first_date
                case.status = CaseStatus.LISTED
                case.stage = CaseStage.PLEADINGS
                case.stage_start_date = cure_date
                case.stage_since = cure_date
                if is_overboard:
                    case.flags.add(FLAG_OVERBOARD)
                self.active_cases[filing_id] = case

    def process_mention_command(self, case_id: str, mention_ts_str: str) -> None:
        """Process MENTION command: urgent mention before 10:30; if board full (40), lists next sitting day pos 1."""
        case = self.active_cases.get(case_id)
        if not case or not case.assigned_bench:
            return

        bench = self.benches[case.assigned_bench]
        mention_dt = datetime.strptime(mention_ts_str, "%Y-%m-%d %H:%M:%S")
        mention_date = mention_dt.date()
        mention_time = mention_dt.strftime("%H:%M")

        is_before_cutoff = mention_time < URGENT_MENTION_CUTOFF_TIME
        current_board = self.get_bench_board_count(bench.bench_id, mention_date)

        if is_before_cutoff and current_board < bench.daily_board_capacity:
            case.next_hearing_date = mention_date
        else:
            # Listed on the next sitting day
            nxt = mention_date + timedelta(days=1)
            while nxt.weekday() not in bench.sitting_days or nxt in bench.leave_dates or nxt in self.holidays:
                nxt += timedelta(days=1)
            case.next_hearing_date = nxt
            # Urgent flag guaranteed
            case.urgency = True
            case.flags.add(FLAG_URGENT)

    def process_outcome_command(
        self,
        case_id: str,
        hearing_date_str: str,
        result: str,
        arg1: str,
        arg2: str,
    ) -> None:
        """Process OUTCOME command: records hearing outcome, updates stages/adjournments/next dates."""
        case = self.active_cases.get(case_id)
        if not case:
            return

        hearing_date = datetime.strptime(hearing_date_str, "%Y-%m-%d").date()
        bench_id = case.assigned_bench or ""
        bench = self.benches.get(bench_id)

        # Check evidence delay flag (BR-33: > 180 days in EVIDENCE)
        stage_since_date = case.stage_since or case.stage_start_date or case.filing_date
        if case.stage == CaseStage.EVIDENCE and (hearing_date - stage_since_date).days > EVIDENCE_DELAY_THRESHOLD_DAYS:
            case.flags.add(FLAG_DELAY)

        cost_assessed = Decimal("0.00")
        diary_result = result
        nxt_date_val: date | None = None

        is_comm_overdue = (
            (case.subject == SubjectType.COMMERCIAL or case.is_commercial)
            and (hearing_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
        )

        if result == "HEARD":
            next_stage_str = arg1
            consent = arg2.lower() == "true"
            case.is_part_heard = False

            if next_stage_str and next_stage_str != "-":
                target_stage = CaseStage(next_stage_str)
                curr_idx = STAGE_ORDER.index(case.stage)
                target_idx = STAGE_ORDER.index(target_stage)

                if target_idx > curr_idx + 1 and not consent:
                    # Stage jump without consent is refused! Stays at current stage
                    pass
                elif target_idx > curr_idx:
                    case.stage = target_stage
                    case.stage_start_date = hearing_date
                    case.stage_since = hearing_date
                    case.adjournments_petitioner_stage = 0
                    case.adjournments_respondent_stage = 0
                    if target_stage == CaseStage.ARGUMENTS:
                        case.final_hearing = True

            # Calculate next date if not decided
            if bench:
                nxt_date_val, is_overboard = self.find_next_date_for_case(
                    bench=bench,
                    from_date=hearing_date,
                    is_urgent=case.urgency,
                    is_commercial_overdue=is_comm_overdue,
                    involves_minor=case.involves_minor,
                )
                case.next_hearing_date = nxt_date_val
                if is_overboard:
                    case.flags.add(FLAG_OVERBOARD)

        elif result == "PART_HEARD":
            case.is_part_heard = True
            if bench:
                # Part heard listed on earliest next sitting day
                nxt = hearing_date + timedelta(days=1)
                while nxt.weekday() not in bench.sitting_days or nxt in bench.leave_dates or nxt in self.holidays:
                    nxt += timedelta(days=1)
                nxt_date_val = nxt
                case.next_hearing_date = nxt

        elif result == "ADJOURNMENT_REQUEST":
            party_role = arg1.upper()  # PETITIONER, RESPONDENT, COURT
            reason_str = arg2.upper()

            prior_party_count = (
                case.adjournments_petitioner_stage if party_role == "PETITIONER"
                else (case.adjournments_respondent_stage if party_role == "RESPONDENT" else 0)
            )

            is_medical = (reason_str == "MEDICAL")
            is_court = (party_role == "COURT" or reason_str == "COURT_OCCASIONED")

            # Max 3 adjournments per stage: 4th refused unless medical or court-occasioned
            if not is_court and prior_party_count >= MAX_ADJOURNMENTS_PER_STAGE and not is_medical:
                # REFUSED!
                diary_result = "REFUSED"
                # Proceeds as heard with no stage change
                if bench:
                    nxt_date_val, is_overboard = self.find_next_date_for_case(
                        bench=bench,
                        from_date=hearing_date,
                        is_urgent=case.urgency,
                        is_commercial_overdue=is_comm_overdue,
                        involves_minor=case.involves_minor,
                    )
                    case.next_hearing_date = nxt_date_val
                    if is_overboard:
                        case.flags.add(FLAG_OVERBOARD)
            else:
                # Adjournment ALLOWED
                if party_role == "PETITIONER":
                    case.adjournments_petitioner_stage += 1
                elif party_role == "RESPONDENT":
                    case.adjournments_respondent_stage += 1
                case.adjournments_total += 1

                # Cost assessment: party request following 2 earlier (i.e. 3rd or more)
                if not is_court and prior_party_count >= 2:
                    if case.subject == SubjectType.COMMERCIAL or case.is_commercial:
                        cost_assessed = COMMERCIAL_ADJOURNMENT_COST
                    else:
                        cost_assessed = PARTY_ADJOURNMENT_COST
                    case.costs_assessed += cost_assessed

                # Compute next date
                if bench:
                    nxt_date_val, is_overboard = self.find_next_date_for_case(
                        bench=bench,
                        from_date=hearing_date,
                        is_urgent=case.urgency,
                        is_commercial_overdue=is_comm_overdue,
                        involves_minor=case.involves_minor,
                    )
                    case.next_hearing_date = nxt_date_val
                    if is_overboard:
                        case.flags.add(FLAG_OVERBOARD)

        elif result == "NOT_REACHED":
            case.carry_over_count += 1
            case.consecutive_unreached_count += 1
            case.flags.add(FLAG_CARRY_OVER)
            if case.consecutive_unreached_count >= UNREACHED_ESCALATION_THRESHOLD:
                case.flags.add(FLAG_BUMPED)

            if bench:
                # Carried to next sitting day
                nxt = hearing_date + timedelta(days=1)
                while nxt.weekday() not in bench.sitting_days or nxt in bench.leave_dates or nxt in self.holidays:
                    nxt += timedelta(days=1)
                nxt_date_val = nxt
                case.next_hearing_date = nxt

        elif result == "DECIDED":
            case.status = CaseStatus.DECIDED
            case.stage = CaseStage.JUDGMENT
            case.next_hearing_date = None
            nxt_date_val = None

            # Record decided in month for pendency tracking
            m_key = (hearing_date.year, hearing_date.month)
            self.decided_by_month[bench_id][m_key] = self.decided_by_month[bench_id].get(m_key, 0) + 1

        # Map outcome enum safely
        if diary_result in ("HEARD", "REFUSED"):
            outcome_enum = HearingOutcome.HEARD
        elif diary_result == "PART_HEARD":
            outcome_enum = HearingOutcome.PART_HEARD
        elif diary_result == "DECIDED":
            outcome_enum = HearingOutcome.DECIDED
        else:
            outcome_enum = HearingOutcome.ADJOURNED

        # Record hearing event
        event = HearingEvent(
            event_id=f"EVT-{case_id}-{len(case.adjournment_history) + 1}",
            case_id=case_id,
            hearing_date=hearing_date,
            outcome=outcome_enum,
            stage=case.stage,
            cost_assessed=cost_assessed,
            notes=f"result={diary_result}, arg1={arg1}, arg2={arg2}",
        )
        # Store metadata on event for diary printing
        setattr(event, "diary_result", diary_result)
        setattr(event, "bench_id", bench_id)
        setattr(event, "adj_p_snapshot", case.adjournments_petitioner_stage)
        setattr(event, "adj_r_snapshot", case.adjournments_respondent_stage)
        setattr(event, "next_date_snapshot", nxt_date_val)
        setattr(event, "flags_snapshot", format_flags(case.flags))
        case.adjournment_history.append(event)

    def process_cost_paid_command(self, case_id: str, party_role: str, pay_date_str: str, amount_str: str) -> None:
        """Process COST_PAID command."""
        case = self.active_cases.get(case_id)
        if case:
            case.costs_paid += Decimal(amount_str)

    def process_transfer_command(self, case_id: str, transfer_date_str: str, to_bench_id: str, reason: str) -> None:
        """Process TRANSFER command: checks once-only limit, bench eligibility, and party conflicts."""
        case = self.active_cases.get(case_id)
        if not case:
            return

        transfer_date = datetime.strptime(transfer_date_str, "%Y-%m-%d").date()

        # BR-44: Lifetime transfer limit is 1
        if case.transferred_count >= 1:
            return

        target_bench = self.benches.get(to_bench_id)
        if not target_bench:
            return

        # BR-45: Target jurisdiction & conflict check
        if case.subject not in target_bench.subject_jurisdictions:
            return
        if (case.subject == SubjectType.COMMERCIAL or case.is_commercial) and case.claim_value > COMMERCIAL_CLAIM_THRESHOLD and not target_bench.commercial_jurisdiction:
            return
        if any(p in target_bench.conflict_party_ids for p in case.party_ids):
            # Conflict detected: transfer refused! Stays on current bench
            return

        # Transfer accepted!
        case.transferred_count += 1
        case.assigned_bench = to_bench_id
        case.status = CaseStatus.TRANSFERRED

        # Recompute next date on destination bench from transfer date
        is_comm_overdue = (
            (case.subject == SubjectType.COMMERCIAL or case.is_commercial)
            and (transfer_date - case.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS
        )
        nxt_date, is_overboard = self.find_next_date_for_case(
            bench=target_bench,
            from_date=transfer_date,
            is_urgent=case.urgency,
            is_commercial_overdue=is_comm_overdue,
            involves_minor=case.involves_minor,
        )
        case.next_hearing_date = nxt_date
        if is_overboard:
            case.flags.add(FLAG_OVERBOARD)

    def process_print_cause_list_command(self, bench_id: str, list_date_str: str) -> None:
        """Generate cause list for bench on list_date and append rows to cause_lists.csv."""
        bench = self.benches.get(bench_id)
        if not bench:
            return

        list_date = datetime.strptime(list_date_str, "%Y-%m-%d").date()

        # Eligible cases: assigned to bench, next_hearing_date == list_date, not decided
        eligible_cases = [
            c for c in self.active_cases.values()
            if c.assigned_bench == bench_id and c.next_hearing_date == list_date and c.status != CaseStatus.DECIDED
        ]

        # Determine priority band and sort entries:
        # Band order (0..6), carry-over first (0 if carry else 1), filing_date, case_id
        sorted_entries = []
        for c in eligible_cases:
            band = determine_priority_band(c, list_date)
            is_carry = (c.carry_over_count > 0 or FLAG_CARRY_OVER in c.flags)
            sorted_entries.append((band, 0 if is_carry else 1, c.filing_date, c.case_id, c))

        sorted_entries.sort(key=lambda t: (t[0].value, t[1], t[2], t[3]))

        # Apply capacity (40) and max final hearing cap (8)
        serial_no = 1
        final_hearing_count = 0

        for band, _, _, _, c in sorted_entries:
            # Check in-camera constraint
            if c.involves_minor and bench.in_camera_days and list_date.weekday() not in bench.in_camera_days:
                continue

            is_final = (c.stage == CaseStage.ARGUMENTS or c.final_hearing or band == PriorityBand.BAND_5_FINAL_HEARING)
            if is_final and final_hearing_count >= bench.max_final_hearing:
                continue

            if serial_no > bench.daily_board_capacity:
                break

            if is_final:
                final_hearing_count += 1

            # Format flags
            row_flags: list[str] = []
            if c.urgency:
                row_flags.append(FLAG_URGENT)
            if c.carry_over_count > 0 or FLAG_CARRY_OVER in c.flags:
                row_flags.append(FLAG_CARRY_OVER)
            if c.consecutive_unreached_count >= UNREACHED_ESCALATION_THRESHOLD or FLAG_BUMPED in c.flags:
                row_flags.append(FLAG_BUMPED)
            if FLAG_OVERBOARD in c.flags:
                row_flags.append(FLAG_OVERBOARD)
            if FLAG_DELAY in c.flags:
                row_flags.append(FLAG_DELAY)
            if c.involves_minor or FLAG_IN_CAMERA in c.flags:
                row_flags.append(FLAG_IN_CAMERA)
            if FLAG_DELAY_CONDONATION_PENDING in c.flags:
                row_flags.append(FLAG_DELAY_CONDONATION_PENDING)

            flags_str = format_flags(row_flags)

            # Columns: bench_id,list_date,serial_no,case_id,band,stage,flags
            self.cause_lists_rows.append([
                bench_id,
                list_date_str,
                str(serial_no),
                c.case_id,
                str(band.value),
                c.stage.value,
                flags_str,
            ])
            serial_no += 1

    def process_print_case_diary_command(self, case_id: str) -> None:
        """Print complete hearing history of case_id to case_diary.csv."""
        case = self.active_cases.get(case_id)
        if not case:
            return

        for event in sorted(case.adjournment_history, key=lambda e: e.hearing_date):
            evt_date_str = event.hearing_date.strftime("%Y-%m-%d")
            bench_id_str = getattr(event, "bench_id", case.assigned_bench or "")
            stage_str = event.stage.value if event.stage else case.stage.value
            result_str = getattr(event, "diary_result", event.outcome.value)
            adj_p_str = str(getattr(event, "adj_p_snapshot", case.adjournments_petitioner_stage))
            adj_r_str = str(getattr(event, "adj_r_snapshot", case.adjournments_respondent_stage))
            cost_str = f"{event.cost_assessed:.2f}"
            nxt_date = getattr(event, "next_date_snapshot", case.next_hearing_date)
            nxt_date_str = nxt_date.strftime("%Y-%m-%d") if nxt_date else ""
            flags_str = getattr(event, "flags_snapshot", format_flags(case.flags))

            # Columns: case_id,event_date,bench_id,stage,result,adjournments_petitioner,adjournments_respondent,cost,next_date,flags
            self.case_diary_rows.append([
                case_id,
                evt_date_str,
                bench_id_str,
                stage_str,
                result_str,
                adj_p_str,
                adj_r_str,
                cost_str,
                nxt_date_str,
                flags_str,
            ])

    def process_print_pendency_command(self, as_of_date_str: str) -> None:
        """Print pendency statistics for all 5 benches as of as_of_date."""
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()
        m_key = (as_of_date.year, as_of_date.month)

        for bench in self.bench_list:
            b_id = bench.bench_id

            # Active pending cases on this bench
            pending_cases_bench = [
                c for c in self.active_cases.values()
                if c.assigned_bench == b_id and c.status != CaseStatus.DECIDED
            ]
            pending_count = len(pending_cases_bench)

            # Decided in current month
            decided_in_month = self.decided_by_month[b_id].get(m_key, 0)

            # Evidence over 180 days
            evidence_over_180 = 0
            for c in pending_cases_bench:
                if c.stage == CaseStage.EVIDENCE:
                    since = c.stage_since or c.stage_start_date or c.filing_date
                    if (as_of_date - since).days > EVIDENCE_DELAY_THRESHOLD_DAYS:
                        evidence_over_180 += 1

            # Commercial over 12 months
            comm_over_12 = 0
            for c in pending_cases_bench:
                if (c.subject == SubjectType.COMMERCIAL or c.is_commercial):
                    if (as_of_date - c.filing_date).days > COMMERCIAL_DISPOSAL_TARGET_DAYS:
                        comm_over_12 += 1

            # Overboard count
            overboard_count = sum(1 for c in pending_cases_bench if FLAG_OVERBOARD in c.flags)

            # Columns: as_of_date,bench_id,pending,decided_in_month,evidence_over_180_days,commercial_over_12_months,overboard
            self.pendency_rows.append([
                as_of_date_str,
                b_id,
                str(pending_count),
                str(decided_in_month),
                str(evidence_over_180),
                str(comm_over_12),
                str(overboard_count),
            ])

    def run_commands_file(self, commands_path: Path | str) -> None:
        """Execute all commands from commands.txt strictly in file order."""
        path = Path(commands_path)
        with open(path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("|")
                cmd = parts[0]

                if cmd == "FILE":
                    self.process_file_command(parts[1])
                elif cmd == "FEE_CURE":
                    self.process_fee_cure_command(parts[1], parts[2], parts[3])
                elif cmd == "MENTION":
                    self.process_mention_command(parts[1], parts[2])
                elif cmd == "OUTCOME":
                    self.process_outcome_command(parts[1], parts[2], parts[3], parts[4], parts[5])
                elif cmd == "COST_PAID":
                    self.process_cost_paid_command(parts[1], parts[2], parts[3], parts[4])
                elif cmd == "TRANSFER":
                    self.process_transfer_command(parts[1], parts[2], parts[3], parts[4])
                elif cmd == "PRINT_CAUSE_LIST":
                    self.process_print_cause_list_command(parts[1], parts[2])
                elif cmd == "PRINT_CASE_DIARY":
                    self.process_print_case_diary_command(parts[1])
                elif cmd == "PRINT_PENDENCY":
                    self.process_print_pendency_command(parts[1])
                else:
                    raise ValueError(f"Unknown command '{cmd}' on line {line_no}: {line}")

    def write_output_csvs(self) -> None:
        """Write evaluation CSV files."""
        # 1. admissions.csv
        admissions_file = self.output_dir / "admissions.csv"
        with open(admissions_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "filing_id",
                "limitation_last_day",
                "limitation_status",
                "court_fee_due",
                "court_fee_paid",
                "fee_status",
                "bench_id",
                "first_date",
                "admission_status",
            ])
            writer.writerows(self.admissions_rows)

        # 2. cause_lists.csv
        cause_lists_file = self.output_dir / "cause_lists.csv"
        with open(cause_lists_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "bench_id",
                "list_date",
                "serial_no",
                "case_id",
                "band",
                "stage",
                "flags",
            ])
            writer.writerows(self.cause_lists_rows)

        # 3. case_diary.csv
        diary_file = self.output_dir / "case_diary.csv"
        with open(diary_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "case_id",
                "event_date",
                "bench_id",
                "stage",
                "result",
                "adjournments_petitioner",
                "adjournments_respondent",
                "cost",
                "next_date",
                "flags",
            ])
            writer.writerows(self.case_diary_rows)

        # 4. pendency.csv
        pendency_file = self.output_dir / "pendency.csv"
        with open(pendency_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "as_of_date",
                "bench_id",
                "pending",
                "decided_in_month",
                "evidence_over_180_days",
                "commercial_over_12_months",
                "overboard",
            ])
            writer.writerows(self.pendency_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PS-118 official benchmark sample commands.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/official_sample/T070-PS-118-sample-data",
        help="Path to directory containing official CSV files",
    )
    parser.add_argument(
        "--commands",
        type=str,
        default="data/official_sample/T070-PS-118-sample-data/commands.txt",
        help="Path to commands.txt",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/official_run",
        help="Path to output directory for CSV files",
    )
    args = parser.parse_args()

    runner = OfficialRunner(data_dir=args.data_dir, output_dir=args.output_dir)
    runner.run_commands_file(args.commands)
    runner.write_output_csvs()
    print(f"Official sample run complete. CSV outputs written to {args.output_dir}:")
    print(f"  - admissions.csv: {len(runner.admissions_rows)} rows")
    print(f"  - cause_lists.csv: {len(runner.cause_lists_rows)} rows")
    print(f"  - case_diary.csv: {len(runner.case_diary_rows)} rows")
    print(f"  - pendency.csv: {len(runner.pendency_rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
