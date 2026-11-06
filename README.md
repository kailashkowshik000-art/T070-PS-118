# Court Case Listing and Adjournment Scheduling Engine

**Project Title:** Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods  
**Problem Statement:** PS-118  
**Team ID:** T070  
**Domain:** Public Services — Judiciary  
**Programming Language:** Python 3.10+ (tested on Python 3.14)  
**Interface:** Command-line and input-file driven (no GUI required)  
**Checkpoint:** Week 3 Complete Business Rules Implementation (6 November 2026)  

---

## 1. Team Members

* **Kowshik Kailash** — 1AT24CG036
* **Krishitha J** — 1AT24CG037

---

## 2. Purpose and Scope

The application simulates administrative workflows in a district court registry:
1. **Case Admission (BR-07 to BR-18):** Validates statutory limitation periods, handles wrong-forum exclusions, adjusts deadlines for court holidays/weekends, evaluates delay condonation applications, computes progressive marginal court fees, flags defective filings, and tracks 7-day cure periods.
2. **Bench Allocation (BR-01 to BR-06):** Matches case subject matter to judicial bench rosters (Civil, Commercial, Family, Criminal), routes commercial claims exceeding ₹3,00,000 to specialized commercial benches, screens for party conflicts, verifies sitting days and leave calendars, and applies deterministic round-robin allocation per roster.
3. **Daily Cause-List Generation (BR-19 to BR-28):** Generates deterministic daily cause lists across 6 statutory priority bands (Urgent/bail, Part-heard, 3+ adjournments, >2 years old, Final hearing, Regular), enforces a 40-case daily board capacity and an 8-case final hearing cap, manages carry-over priority, applies 3-sitting unreached escalation, lists urgent mentions before 10:30 AM, and restricts family/minor matters to designated in-camera days.
4. **Hearing Management & Multi-Sitting Simulation (BR-29 to BR-43):** Processes chronological hearing outcomes (`HEARD`, `PART_HEARD`, `ADJOURNED`, `DECIDED`, `TRANSFERRED`), enforces stage progression without skipping (`PLEADINGS` &rarr; `ISSUES` &rarr; `EVIDENCE` &rarr; `ARGUMENTS` &rarr; `JUDGMENT`), enforces party adjournment limits (max 3 per stage, 4th refused unless `MEDICAL` or `COURT_OCCASIONED`), assesses adjournment costs (₹2,000 civil, ₹4,000 commercial), tracks cost payment status (`COST_PAYMENT_PENDING`), and calculates next dates (min 14 days, 7 days urgent/commercial overdue, capacity checks, Day-60 `OVERBOARD` fallback).
5. **Case Transfer Engine (BR-44 to BR-48):** Enforces a strict one-transfer lifetime limit per case, permits transfers solely for `ROSTER_CHANGE` or `CONFLICT`, verifies destination bench jurisdiction, commercial threshold, and party conflicts, preserves case history and stage, counts transfer as an adjournment, and recomputes next hearing dates on destination bench calendars.
6. **Advanced Judicial Reporting (BR-33, BR-49 to BR-51):** Produces formatted daily cause lists, individual and consolidated case diaries, dedicated evidence-delay reports (>180 days in evidence), comprehensive Principal District Judge oversight reports, and pendency analytics in both text and JSON formats.

---

## 3. Project Structure

```text
T070-PS-118/
├── main.py                  # CLI entry point, multi-sitting simulator, and pipeline coordinator
├── models.py                # Domain models (Case, Bench, HearingEvent, CauseListEntry, enums)
├── config.py                # System constants, fee schedules, capacity limits, and status flags
├── input_output.py          # Input loaders, strict schema validators, and output report savers
├── admission.py             # Core Flow 1: Limitation checker and court fee scrutiny
├── allocation.py            # Core Flow 2: Deterministic round-robin bench allocator
├── scheduling.py            # Core Flow 3: Priority bands, carry-over, and cause-list generator
├── hearings.py              # Hearing manager, stage progression, transfer engine, and simulator
├── reporting.py             # Advanced judicial reports, diaries, cause lists, and summaries
├── requirements.txt         # Project dependencies (pytest)
├── README.md                # Project documentation and usage guide
├── .gitignore               # Git ignore rules for Python, virtual environments, and IDEs
│
├── data/                    # Representative input fixtures
│   ├── benches.json         # Bench definitions, rosters, sitting days, and conflicts
│   ├── holidays.json        # Court gazetted holidays
│   ├── filings.json         # Case filings across civil, commercial, family, and criminal
│   └── events.json          # Pre-existing hearing events, outcomes, and case history
│
├── output/                  # Deterministic output directory (13 artifacts)
│   ├── admission_results.json
│   ├── allocation_results.json
│   ├── cause_lists.json
│   ├── cause_lists.txt
│   ├── case_diaries.json
│   ├── case_diaries.txt
│   ├── evidence_delay_report.json
│   ├── evidence_delay_report.txt
│   ├── principal_judge_report.json
│   ├── principal_judge_report.txt
│   ├── pendency_report.json
│   ├── pendency_report.txt
│   └── execution_summary.txt
│
├── tests/                   # Comprehensive test suite (80 unit and integration tests)
│   ├── test_admission.py    # 17 unit tests for limitation, condonation, fees, and defects
│   ├── test_allocation.py   # 8 unit tests for rosters, commercial cap, conflicts, and round-robin
│   ├── test_scheduling.py   # 15 unit tests for priority bands, caps, carry-over, and mentions
│   ├── test_hearings.py     # 13 unit tests for stage progression, adjournments, costs, and simulation
│   ├── test_transfers.py    # 10 unit tests for transfer limit, reasons, conflicts, and calendar
│   ├── test_reporting.py    # 8 unit tests for cause lists, diaries, delay, and Principal Judge reports
│   └── test_integration.py  # 9 integration and negative validation tests
│
└── docs/                    # Architectural and legal documentation
    ├── glossary.md          # Domain glossary
    ├── business-rules.md    # Complete traceability matrix for BR-01 through BR-51
    ├── decision-log.md      # Architectural decisions (DEC-01 to DEC-13)
    └── week1-design.pdf     # Week 1 Design Document artifact
```

---

## 4. Setup and Installation

### Prerequisites
- Python 3.10 or higher (Python 3.14 supported).
- Git installed.

### Virtual Environment Setup (Recommended)
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies (pytest)
pip install -r requirements.txt
```

---

## 5. Execution Instructions

### Running the Application

1. **Standard Daily Cause List & Reporting:**
   ```bash
   python main.py --data-dir data --output-dir output --date 2026-10-29
   ```

2. **Verbose Execution (Prints Cause Lists & Principal Judge Oversight Report to Console):**
   ```bash
   python main.py --data-dir data --output-dir output --date 2026-10-29 --verbose
   ```

3. **Multi-Sitting Simulation Run (Simulating Consecutive Court Sittings):**
   ```bash
   python main.py --data-dir data --output-dir output --date 2026-10-29 --simulate-until 2026-11-06 --verbose
   ```

4. **Official Sample Data Stream Execution (6-Month Command Stream & Evaluation CSVs):**
   ```bash
   python main.py --commands data/official_sample/T070-PS-118-sample-data/commands.txt --data-dir data/official_sample/T070-PS-118-sample-data --output-dir output/official_run
   ```
   Or using the dedicated official runner directly:
   ```bash
   python official_runner.py --data-dir data/official_sample/T070-PS-118-sample-data --commands data/official_sample/T070-PS-118-sample-data/commands.txt --output-dir output/official_run
   ```

### CLI Arguments
| Argument | Default | Description |
| :--- | :--- | :--- |
| `--commands` | `None` | Path to official `commands.txt` file for command-driven simulation run. |
| `--data-dir` | `data` | Directory containing inputs (JSON fixtures or official CSV files). |
| `--output-dir` | `output` | Directory where output files will be written. |
| `--date` | `2026-10-29` | Target date (`YYYY-MM-DD`) for cause-list generation or simulation start date. |
| `--simulate-until` | `None` | Optional end date (`YYYY-MM-DD`) for multi-sitting simulation run across dates. |
| `--verbose` | `False` | Displays detailed human-readable cause-list tables and oversight summaries. |

---

## 6. Running Tests

The test suite can be run using either Python's built-in `unittest` runner or `pytest`:

```bash
# Using Python's standard unittest runner:
python -m unittest discover tests

# Using pytest:
python -m pytest
```

**Test Suite Results:**
- **105 passing tests** across 8 test modules with **0 failures and 0 errors** in **0.35 seconds**.
- Includes dedicated `tests/test_official_scenarios.py` verifying all planted edge cases (EC-01 to EC-08) and extra traps.

---

## 7. Input File Formats

All input files are standard, validated JSON files located in `data/`:

### `data/holidays.json`
Array of gazetted court holidays:
```json
[
  { "date": "2026-01-26", "name": "Republic Day" },
  { "date": "2026-10-02", "name": "Gandhi Jayanti" }
]
```

### `data/benches.json`
Array of bench definitions:
```json
[
  {
    "bench_id": "BENCH-COMM-01",
    "subject_jurisdictions": ["COMMERCIAL", "CIVIL"],
    "commercial_jurisdiction": true,
    "sitting_days": [0, 1, 2, 3, 4],
    "daily_board_capacity": 40,
    "leave_dates": [],
    "conflict_party_ids": [],
    "designated_family_hearing_days": [3]
  }
]
```

### `data/filings.json`
Array of case filings:
```json
[
  {
    "case_id": "COM-2026-002",
    "case_type": "COMMERCIAL_SUIT",
    "subject": "COMMERCIAL",
    "party_ids": ["INFOTECH_SOLUTIONS", "GLOBAL_LOGISTICS"],
    "filing_date": "2026-10-20",
    "cause_of_action_date": "2025-01-10",
    "order_date": null,
    "claim_value": "500000.00",
    "court_fee_paid": "21000.00",
    "urgency": false,
    "wrong_forum_days": 0,
    "has_condonation_application": false,
    "involves_minor": false,
    "is_part_heard": false,
    "stage": "PLEADINGS"
  }
]
```

### `data/events.json`
Array of historical and scheduled hearing events:
```json
[
  {
    "event_id": "EVT-2026-001",
    "case_id": "CS-2024-008",
    "hearing_date": "2024-06-15",
    "outcome": "HEARD",
    "adjournment_reason": null,
    "requesting_party": null,
    "consent_indicator": false,
    "new_stage": "ISSUES",
    "notes": "Pleadings completed, stage advanced to Issues."
  }
]
```

---

## 8. Output Descriptions

The engine generates 13 deterministic output files in `output/`:

1. `admission_results.json`: Records admission decisions (`ADMITTED`, `DEFECTIVE`, `REJECTED`, `RETURNED`), statutory limitation deadlines, applicable and paid fees, defect reasons, required flags, and cure deadlines.
2. `allocation_results.json`: Records assigned bench ID or failure reason for each case.
3. `cause_lists.json`: Complete daily cause lists grouped by bench ID, specifying priority bands (1-6), positions (1-40), carry-over indicators, final hearing indicators, and flags.
4. `cause_lists.txt`: Formatted human-readable daily cause list tables for court notice boards.
5. `case_diaries.json`: Complete serialized history for all registered cases including lifecycle events, costs assessed, costs paid, transfer counts, and active flags.
6. `case_diaries.txt`: Detailed formatted case diaries for all registered cases.
7. `evidence_delay_report.json`: Structured list of matters exceeding 180 days in the Evidence stage (BR-33).
8. `evidence_delay_report.txt`: Formatted administrative report of evidence delay matters for the Principal Judge.
9. `principal_judge_report.json`: Executive oversight metrics covering bench utilization, capacities, delay condonations, defective filings, evidence delays, and overdue commercial cases.
10. `principal_judge_report.txt`: Formatted administrative oversight report for the Principal District Judge.
11. `pendency_report.json`: Active pendency breakdown by stage, subject, age, and delay indicators.
12. `pendency_report.txt`: Formatted text version of the district court pendency report.
13. `execution_summary.txt`: Concise run summary detailing filings processed, admission outcomes, allocations, and cause-list listings.

---

## 9. Business Rule Coverage (BR-01 to BR-51)

Every single business rule from BR-01 to BR-51 is **100% implemented and tested**:
- **BR-01 to BR-06 (Bench Registration & Allocation):** Complete in `models.py` and `allocation.py`.
- **BR-07 to BR-18 (Admission & Court Fees):** Complete in `admission.py`.
- **BR-19 to BR-28 (Cause-List Generation & Priorities):** Complete in `scheduling.py`.
- **BR-29 to BR-43 (Hearings, Adjournments, Costs & Capacity):** Complete in `hearings.py`.
- **BR-44 to BR-48 (Case Transfer Engine):** Complete in `hearings.py`.
- **BR-49 to BR-51 (Advanced Judicial Reporting):** Complete in `reporting.py`.

Refer to `docs/business-rules.md` for the line-by-line function and test traceability matrix.

---

## 10. Known Limitations

1. **Non-Standard Holiday Schemes:** Court holidays must be explicitly provided in `data/holidays.json` using ISO `YYYY-MM-DD` strings.
2. **Fixed Adjournment Fine Tiers:** Party adjournment fines are fixed at statutory ₹2,000 (Civil/Family/Criminal) and ₹4,000 (Commercial) as specified in the brief.

---

## 11. Final Submission Readiness

- [x] All 51 business rules (BR-01 through BR-51) fully implemented with zero placeholders.
- [x] 80 unit and integration tests passing cleanly.
- [x] Complete multi-sitting simulation enabled.
- [x] Case transfer engine strictly enforcing 1-transfer limit and permitted reasons.
- [x] Advanced judicial reporting including Principal District Judge reports and evidence delay exports.
- [x] Strict input schema validation and error reporting.
- [x] Clean Git repository status.
