# Court Case Listing and Adjournment Scheduling Engine

**Project Title:** Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods  
**Problem Statement:** PS-118  
**Team ID:** T070  
**Domain:** Public Services — Judiciary  
**Programming Language:** Python 3.10+ (tested on Python 3.14)  
**Interface:** Command-line and input-file driven (no GUI required)  
**Checkpoint:** Week 4 Final Submission  

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

```
T070-PS-118/
├── main.py                  # CLI entry point, multi-sitting simulator, and pipeline coordinator
├── official_runner.py       # Command-stream runner for the official data pack (writes the 4 evaluation CSVs)
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
├── .gitignore               # Git ignore rules (generated output/ files are ignored)
│
├── data/                    # Input fixtures
│   ├── benches.json         # Bench definitions, rosters, sitting days, and conflicts
│   ├── holidays.json        # Court gazetted holidays
│   ├── filings.json         # Case filings across civil, commercial, family, and criminal
│   ├── events.json          # Pre-existing hearing events, outcomes, and case history
│   └── official_sample/     # Official sample data pack (CSV files + commands.txt, ~680 commands)
│
├── output/                  # Generated files are written here (git-ignored; recreate with the commands in Section 5)
│
├── tests/                   # Test suite (106 unit and integration tests)
│   ├── test_admission.py          # 18 tests: limitation, condonation, fees, defects, leap day
│   ├── test_allocation.py         #  8 tests: rosters, commercial threshold, conflicts, round-robin
│   ├── test_scheduling.py         # 15 tests: priority bands, caps, carry-over, mentions
│   ├── test_hearings.py           # 17 tests: stage progression, adjournments, costs, simulation
│   ├── test_transfers.py          # 10 tests: transfer limit, reasons, conflicts, calendar
│   ├── test_reporting.py          #  8 tests: cause lists, diaries, delay, Principal Judge report
│   ├── test_integration.py        # 10 tests: end-to-end flows and negative validation
│   └── test_official_scenarios.py # 20 tests: planted edge cases EC-01 to EC-08 and extra traps
│
├── docs/                    # Design and decision documentation
│   ├── design-document.md   # Final design document (architecture, class and state diagrams)
│   ├── business-rules.md    # Traceability matrix for BR-01 through BR-51
│   ├── decision-log.md      # Assumptions and decisions (DEC-01 to DEC-18)
│   ├── glossary.md          # Domain glossary
│   ├── demo-script.md       # Script and commands for the 5-minute demo video
│   └── week1-design.pdf     # Week 1 design document (original)
│
└── 00_Index.docx ... 11_Week1_Completion_Checklist.docx   # Week 1 design documents (original, kept for history)
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

```
# Using Python's standard unittest runner:
python -m unittest discover tests

# Using pytest:
python -m pytest
```

**Test suite:** 106 tests across 8 modules (counts per module are listed in Section 3). All pass with 0 failures and 0 errors.

- `tests/test_official_scenarios.py` runs the official command stream and checks every planted edge case (EC-01 to EC-08) and the extra traps from the data pack.
- Every business rule BR-01 to BR-51 maps to at least one test; see `docs/business-rules.md`.

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

The standard run (`main.py` with `--data-dir data`) generates 13 deterministic files in the chosen output directory (default `output/`, which is git-ignored, so run the command to create them):

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

### Official run outputs (command stream)

A run with `--commands` (or `official_runner.py`) processes the command file strictly in order and writes four CSV files with the column order required for evaluation:

| File | Content |
| ---- | ------- |
| `admissions.csv` | One row per `FILE` command: limitation last day and status, fee due/paid/status, bench, first date, admission status (the status at the time of the `FILE` command; see DEC-16) |
| `cause_lists.csv` | One row per listed matter for each `PRINT_CAUSE_LIST`, in list order, with band (0 to 6) and flags |
| `case_diary.csv` | One row per hearing/event for each printed case, in date order |
| `pendency.csv` | One row per bench for each `PRINT_PENDENCY` |

For the included sample data pack this produces 80 admission rows, 130 cause-list rows, 381 case-diary rows and 30 pendency rows.

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

## 10. Documentation

| Document | Purpose |
| -------- | ------- |
| `docs/design-document.md` | Final design: architecture, class diagram, state diagrams, processing flow, changes since Week 1 |
| `docs/business-rules.md` | BR-01 to BR-51 traceability: rule, module and function, tests |
| `docs/decision-log.md` | Ambiguities and the interpretation chosen (DEC-01 to DEC-18) |
| `docs/glossary.md` | Domain terms |
| `docs/demo-script.md` | Script for the 5-minute demo video |

**Demo video:** https://drive.google.com/file/d/1fSlCJ-r6zi1iPsEWYErkwU5n-0PA5rj_/view?usp=sharing

---

## 11. Known Limitations

1. **Holidays must be supplied.** Court holidays come from `data/holidays.json` (or `holidays.csv`) as ISO `YYYY-MM-DD` dates; no holiday calendar is built in.
2. **Fixed adjournment costs.** Costs are fixed at ₹2,000 (civil, family, criminal) and ₹4,000 (commercial), as specified in the brief.
3. **Two execution paths differ on one point.** For a `MEDICAL` 4th adjournment the official command run charges the adjournment cost (as the data pack requires), while the JSON demo pipeline in `hearings.py` does not (DEC-02).
4. **`admissions.csv` is a snapshot.** A filing cured after a `FILE` command stays `DEFECTIVE` in that row, although the case is registered and listed from the cure date; no `RETURNED` row is emitted by the official runner (DEC-16).
5. **Leap-day limitation.** A period starting on 29 Feb ends on 28 Feb when the target year has no 29 Feb (DEC-14).

---

## 12. Final Submission Readiness

- [x] All 51 business rules (BR-01 to BR-51) implemented and mapped to tests (`docs/business-rules.md`).
- [x] 106 unit and integration tests passing.
- [x] Official sample data pack runs end to end and writes the four evaluation CSVs.
- [x] Multi-sitting simulation, transfer engine and judicial reports implemented.
- [x] Strict input schema validation and error reporting.
- [x] Final design document, decision log (DEC-01 to DEC-18) and demo script in `docs/`.
- [x] Demo video recorded and its link added in Section 10.
