# Court Case Listing and Adjournment Scheduling Engine

**Project Title:** Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods  
**Problem Statement:** PS-118  
**Team ID:** T070  
**Domain:** Public Services — Judiciary  
**Programming Language:** Python 3.10+ (tested on Python 3.14)  
**Interface:** Command-line and input-file driven (no GUI required)  

---

## 1. Team Members

* **Kowshik Kailash** — 1AT24CG036
* **Krishitha J** — 1AT24CG037

---

## 2. Purpose and Scope

The application simulates the core administrative and registry workflows of a district court registry:
1. **Case Admission:** Validates statutory limitation periods, handles wrong-forum exclusions, adjusts deadlines for court holidays/weekends, checks delay condonation applications, computes progressive marginal court fees, identifies defective filings, and manages 7-day cure periods.
2. **Bench Allocation:** Matches case subject matter to judicial bench rosters (Civil, Commercial, Family, Criminal), routes commercial claims exceeding ₹3,00,000 to specialized commercial benches, screens for party conflicts, verifies bench sitting calendars/leaves, and applies deterministic round-robin allocation.
3. **Daily Cause-List Generation:** Generates deterministic daily cause lists using 6 statutory priority bands (Urgent/bail, Part-heard, 3+ adjournments, >2 years old, Final hearing, Regular), enforces a 40-case daily board capacity and an 8-case final hearing cap, manages unreached carry-over priority, handles 3-sitting escalation, and supports urgent mentions before 10:30 AM.
4. **Deterministic Auditable Output:** Produces structured JSON output files and comprehensive human-readable reports and summaries.

---

## 3. Project Structure

```text
T070-PS-118/
├── main.py                  # CLI entry point and end-to-end pipeline coordinator
├── models.py                # Domain models (Case, Bench, HearingEvent, CauseListEntry, enums)
├── config.py                # System constants, fee schedules, and board capacity limits
├── input_output.py          # Input file loaders, JSON schema validators, and output writers
├── admission.py             # Core Flow 1: Limitation checker and court fee scrutiny
├── allocation.py            # Core Flow 2: Deterministic round-robin bench allocator
├── scheduling.py            # Core Flow 3: Priority bands, carry-over, and cause-list generator
├── hearings.py              # Hearing management, stage progression, and adjournment rules
├── reporting.py             # Formatted cause lists, case diaries, and pendency reports
├── requirements.txt         # Project dependencies (pytest)
├── README.md                # Project documentation and usage guide
├── .gitignore               # Git ignore rules for Python, virtual environments, and IDEs
│
├── data/                    # Representative input fixtures
│   ├── benches.json         # Bench definitions, rosters, sitting days, and conflicts
│   ├── holidays.json        # Court gazetted holidays
│   ├── filings.json         # Case filings across civil, commercial, family, and criminal
│   └── events.json          # Pre-existing hearing events and case history
│
├── output/                  # Deterministic output directory
│   ├── admission_results.json
│   ├── allocation_results.json
│   ├── cause_lists.json
│   └── execution_summary.txt
│
├── tests/                   # Comprehensive test suite (54 unit and integration tests)
│   ├── test_admission.py    # 17 unit tests for limitation, condonation, fees, and defects
│   ├── test_allocation.py   # 8 unit tests for rosters, commercial cap, conflicts, and round-robin
│   ├── test_scheduling.py   # 15 unit tests for priority bands, caps, carry-over, and mentions
│   ├── test_hearings.py     # 7 unit tests for stage progression, adjournment limits, and costs
│   ├── test_reporting.py    # 4 unit tests for formatted cause lists, diaries, and summaries
│   └── test_integration.py  # 3 end-to-end integration and negative validation tests
│
└── docs/                    # Architectural and legal documentation
    ├── glossary.md          # Domain glossary
    ├── business-rules.md    # Traceability matrix for BR-01 through BR-51
    ├── decision-log.md      # Architectural assumptions and decisions (DEC-01 to DEC-11)
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
Execute the command-line interface with default paths or custom arguments:

```bash
# Standard execution
python main.py --data-dir data --output-dir output --date 2026-10-29

# Verbose execution (prints formatted cause lists to console)
python main.py --data-dir data --output-dir output --date 2026-10-29 --verbose
```

### CLI Arguments
| Argument | Default | Description |
| :--- | :--- | :--- |
| `--data-dir` | `data` | Directory containing `holidays.json`, `benches.json`, `filings.json`, `events.json`. |
| `--output-dir` | `output` | Directory where output JSON and text reports will be written. |
| `--date` | `2026-10-29` | Target date (`YYYY-MM-DD`) for cause-list generation. |
| `--verbose` | `False` | Displays detailed human-readable cause-list tables on standard output. |

---

## 6. Running Tests

The test suite can be run using either Python's built-in `unittest` runner or `pytest`:

```bash
# Using Python's standard unittest runner:
python -m unittest discover tests

# Using pytest:
python -m pytest
```

**Test Suite Coverage:**
- 54 passing tests across 6 test modules with 0 failures and 0 errors.

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

---

## 8. Output Descriptions

The engine generates four deterministic output files in `output/`:

1. `admission_results.json`: Records the admission status (`ADMITTED`, `DEFECTIVE`, `REJECTED`), statutory limitation deadline, applicable court fee, paid fee, defect/rejection reasons, required flags, and cure deadlines.
2. `allocation_results.json`: Records the assigned bench ID or failure reason for each case.
3. `cause_lists.json`: Complete daily cause lists grouped by bench ID, specifying priority bands (1-6), board positions (1-40), carry-over indicators, final hearing indicators, and diagnostic flags.
4. `execution_summary.txt`: Concise executive summary detailing total filings processed, admission outcomes, allocations, and cause-list listing counts.

---

## 9. Implemented Features (Week 2 Core)

- [x] **Case Admission Flow (BR-07 to BR-18):**
  - Limitation calculation for Civil suits (3 yrs), Money recovery (3 yrs), Appeals (30 days), and Revisions (90 days).
  - Wrong-forum qualifying time deduction.
  - Court holiday and weekend extension to the next working day.
  - Delay condonation application checking (`DELAY_CONDONATION_PENDING`).
  - Progressive marginal court fee calculations (5% on 0-1L, 4% on 1-10L, 2% on >10L, capped at ₹3,00,000, 50% for appeals).
  - Deficient fee handling (marked `DEFECTIVE` with a mandatory 7-day cure window; `RETURNED` if uncured).
- [x] **Bench Allocation Flow (BR-01 to BR-06):**
  - Roster subject matching (Civil, Commercial, Family, Criminal).
  - Commercial threshold enforcement (claims > ₹3,00,000 require commercial bench).
  - Exclusion of benches with party conflicts.
  - Sitting day and leave date checks.
  - Deterministic round-robin allocation per roster.
  - Diagnostic reason reporting when no eligible bench is available.
- [x] **Cause-List Generation Flow (BR-19 to BR-28):**
  - 6 hierarchical priority bands: Urgent/bail, Part-heard, 3+ adjournments, >2 years old, Final hearing, Regular.
  - Oldest-first ordering within bands.
  - Board capacity limit of 40 matters per bench per day.
  - Maximum 8 final-hearing matters per bench per day.
  - Carry-over matter priority within band.
  - Priority escalation after 3 consecutive unreached sittings.
  - Urgent/bail mention before 10:30 AM (same day if capacity exists, otherwise next sitting day at position 1).
  - Family matters involving minors restricted to designated in-camera days.
- [x] **Scaffolding and Foundations for Hearings and Reports (BR-29 to BR-51):**
  - Stage progression (`PLEADINGS` &rarr; `ISSUES` &rarr; `EVIDENCE` &rarr; `ARGUMENTS` &rarr; `JUDGMENT`) with consent-based skipping prevention.
  - Adjournment counting (party limits, cost penalty calculation of ₹2,000 / ₹4,000, medical exceptions).
  - Next hearing date computation (minimum 14-day / 7-day interval, calendar exclusions, 60-day `OVERBOARD` fallback).
  - Case diaries, formatted cause lists, and pendency reports.

---

## 10. Known Limitations

1. **Hearing Stage Progression:** Fully modeled and tested in unit tests, but not yet automated in batch command replay (planned for Week 3).
2. **Case Transfers (BR-44 to BR-48):** Transfer limits and conflict checking are scaffolded in `hearings.py` and `allocation.py`; batch transfer commands are scheduled for Week 3.
3. **Overdue Commercial Listing Frequency (BR-25):** The 7-day recurring loop for overdue commercial cases is identified in pendency reports; multi-week scheduling simulation will be enhanced in Week 3.

---

## 11. Remaining Week 3 Tasks

1. **Complete Hearing Event Processing:** Automate the multi-sitting simulation replay over sequential dates from `events.json`.
2. **Transfer Management Engine:** Implement bench transfer execution with one-time limit enforcement and calendar recalculation.
3. **Advanced Judicial Reporting:** Implement export of the principal-judge evidence delay report (>180 days in evidence) and automated case diary dumps.
