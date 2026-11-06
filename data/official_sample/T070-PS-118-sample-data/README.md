# PS-118 – Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods — Sample Data Pack

Prepared by 10 SECONDS for Team T070.

## Files

| File | What it holds | Row count |
|---|---|---|
| `benches.csv` | 5 benches with subject roster, sitting days, in-camera days and board caps | 5 data rows |
| `bench_leave.csv` | Bench leave periods | 4 data rows |
| `bench_conflicts.csv` | Declared conflicts (party ids a bench must not hear) | 12 data rows |
| `holidays.csv` | Court holidays | 8 data rows |
| `parties.csv` | Parties referenced by cases and filings | 330 data rows |
| `pending_cases.csv` | Docket already pending on 2026-04-01 with stage, adjournment counters and next date | 57 data rows |
| `filings.csv` | 80 new filings for limitation, fee and roster checks | 80 data rows |
| `commands.txt` | ~400 hearing outcomes, mentions, transfers, cost payments, fee cures, filings and print requests over 6 months | 679 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and is only allowed where the notes say so.

### `benches.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| bench_id | string | BEN-nn | — | — |
| presiding_officer | string | — | — | — |
| subject | enum | — | CIVIL, CRIMINAL, FAMILY, COMMERCIAL | roster |
| sitting_days | string | semicolon list | MON..FRI | — |
| in_camera_days | string | semicolon list | — | designated days for matters with a minor; empty = n/a |
| board_capacity | int | matters | 40 | — |
| max_final_hearing | int | matters | 8 | — |

### `bench_leave.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| bench_id | string | — | benches.csv | — |
| leave_from | date | — | — | inclusive |
| leave_to | date | — | — | inclusive |

### `bench_conflicts.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| bench_id | string | — | benches.csv | — |
| party_id | string | — | parties.csv | — |
| reason | string | — | — | — |

### `holidays.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| holiday_date | date | — | — | Saturdays and Sundays are also non-working |
| holiday_name | string | — | — | — |

### `parties.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| party_id | string | PTY-nnnn | — | — |
| party_name | string | — | — | — |
| party_type | enum | — | INDIVIDUAL, COMPANY, STATE | — |

### `pending_cases.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| case_id | string | LGC-nnnn | — | — |
| case_type | enum | — | CIVIL_SUIT, MONEY_RECOVERY, COMMERCIAL_SUIT, CRIMINAL_CASE, FAMILY_PETITION | — |
| subject | enum | — | CIVIL, CRIMINAL, FAMILY, COMMERCIAL | — |
| is_commercial | bool | — | — | 12-month disposal target |
| filing_date | date | — | — | age bands |
| claim_value | decimal | Rs | — | 0 for non-money matters |
| petitioner_id | string | — | parties.csv | — |
| respondent_id | string | — | parties.csv | — |
| bench_id | string | — | benches.csv | — |
| stage | enum | — | PLEADINGS, ISSUES, EVIDENCE, ARGUMENTS, JUDGMENT | — |
| stage_since | date | — | — | for the 180-day EVIDENCE flag |
| adjournments_petitioner_stage | int | — | — | party adjournments in the current stage |
| adjournments_respondent_stage | int | — | — | — |
| adjournments_total | int | — | — | for band 3 (3+ adjournments) |
| part_heard | bool | — | — | — |
| urgent | bool | — | — | — |
| minor_involved | bool | — | — | — |
| next_date | date | — | — | already fixed listing date |

### `filings.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| filing_id | string | FIL-nnnn | — | also the case_id once registered |
| filing_ts | timestamp | — | — | — |
| case_type | enum | — | CIVIL_SUIT, MONEY_RECOVERY, COMMERCIAL_SUIT, APPEAL, REVISION, CRIMINAL_CASE, BAIL_APPLICATION, FAMILY_PETITION | — |
| subject | enum | — | CIVIL, CRIMINAL, FAMILY, COMMERCIAL | — |
| is_commercial | bool | — | — | — |
| petitioner_id | string | — | parties.csv | — |
| respondent_id | string | — | parties.csv | — |
| cause_of_action_date | date | — | — | suits only |
| amount_due_date | date | — | — | money recovery only |
| impugned_order_date | date | — | — | appeals/revisions only |
| wrong_forum_days | int | days | — | excluded from limitation |
| claim_value | decimal | Rs | — | appeals: value of the original claim |
| court_fee_paid | decimal | Rs | — | — |
| urgent | bool | — | — | bail/urgent |
| minor_involved | bool | — | — | — |
| condonation_application | bool | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An argument written as `-` means "not applicable". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `FILE` | `filing_id` | Process the filing (limitation -> fee -> roster -> conflicts); registered cases get their first date by the next-date rule |
| `FEE_CURE` | `filing_id|cure_date|amount` | Deficit court fee paid for a DEFECTIVE filing |
| `MENTION` | `case_id|mention_ts` | Urgent/bail mention |
| `OUTCOME` | `case_id|hearing_date|result|arg1|arg2` | result HEARD (arg1 next stage or -, arg2 consent true/false), PART_HEARD, ADJOURNMENT_REQUEST (arg1 PETITIONER/RESPONDENT/COURT, arg2 reason), NOT_REACHED, DECIDED (arg1 disposal type) |
| `COST_PAID` | `case_id|party_role|pay_date|amount` | Adjournment cost paid |
| `TRANSFER` | `case_id|transfer_date|to_bench_id|reason` | reason ROSTER_CHANGE or CONFLICT |
| `PRINT_CAUSE_LIST` | `bench_id|date` | Printed at 09:00 for that day |
| `PRINT_CASE_DIARY` | `case_id` | — |
| `PRINT_PENDENCY` | `as_of_date` | — |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Limitation expiring on a court holiday**
  - FIL-0021: civil suit, cause of action 2023-05-01 -> 3 years ends 2026-05-01 = May Day (court holiday), then a weekend — limitation extends to Mon 2026-05-04; filed 2026-05-04 10:40 — IN TIME — `commands.txt line 116; filings.csv row 21`
- **EC-02 Claim value exactly Rs 1 lakh and exactly Rs 10 lakh**
  - FIL-0004: claim exactly Rs 100000.00 -> fee 5% = Rs 5000.00; FIL-0005: claim exactly Rs 1000000.00 -> 5000 + 4% of 900000 = Rs 41000.00 (fees paid exactly) — `filings.csv row 4, filings.csv row 5`
- **EC-03 Fourth adjournment request with MEDICAL reason**
  - LGC-0031 (BEN-01, EVIDENCE): petitioner already has 3 adjournments in this stage; the 4th request on 2026-04-20 is MEDICAL — granted (exception), and as it follows 2 earlier ones it costs Rs 2000.00 payable before the next date — `commands.txt lines 72, 83; pending_cases.csv row 31`
- **EC-04 Board with 40 matters when an urgent mention arrives at 10:29**
  - BEN-03 board on 2026-04-15 already holds 40 matters (pending_cases next_date); bail application FIL-0007 is filed 09:45 and MENTIONED at 10:29 (before the 10:30 cut-off) — board full, so it is listed on the next sitting day 2026-04-16 at position 1 — `commands.txt lines 15, 16; 40 pending_cases rows with next_date 2026-04-15 and bench BEN-03`
- **EC-05 Next date falling on a bench leave day exactly 14 days ahead**
  - LGC-0044 (BEN-05, sits Tue/Thu): adjourned on 2026-06-09; 14 days later is Tue 2026-06-23 — the bench is on leave that day, so the next date is Thu 2026-06-25 — `commands.txt line 275`
- **EC-06 Case not reached on exactly 3 sittings**
  - LGC-0008 (BEN-01): NOT_REACHED on three consecutive sittings from 2026-06-01 (carried to the next sitting day each time, first in its band); on the 4th listing it is bumped one band up — `commands.txt lines 225, 235, 244, 250`
- **EC-07 Commercial case crossing 12 months during an adjournment**
  - LGC-0017 (commercial, filed 2025-07-02): adjourned on 2026-06-25 to 2026-07-09 (>= 14 days); the 12-month disposal target passes on 2026-07-02 DURING the adjournment — from the 2026-07-09 listing it is listed every 7 days with top priority until decided. This pack keeps the already-fixed date 2026-07-09 — `commands.txt lines 329, 371`
- **EC-08 Transfer to a bench with a conflict with one party**
  - LGC-0056 (BEN-01): TRANSFER to BEN-02 on 2026-05-06 — BEN-02 has a declared conflict with the respondent PTY-0309: transfer REFUSED, the case stays on BEN-01 with its existing date — `commands.txt line 140; bench_conflicts.csv row 3`
- **Extra traps (not in the brief, but realistic):**
  - FIL-0038: cause 2023-03-10 (limitation 2026-03-10) but 75 days in a wrong forum are excluded -> last day 2026-05-24 (Sun) -> 2026-05-25; filed 2026-05-20 — in time — `filings.csv row 38`
  - FIL-0062: appeal filed 31 days after the order (last day 2026-07-01) with a condonation application — admitted, flagged DELAY_CONDONATION_PENDING; FIL-0053: money recovery 3 years after the due date 2023-06-01 without condonation — REJECTED — `filings.csv row 62, filings.csv row 53`
  - FIL-0030: revision filed on the 90th day after the order (2026-02-10 -> 2026-05-11) — in time — `filings.csv row 30`
  - FIL-0011: claim Rs 20000000.00 -> slab fee Rs 421000.00, capped at Rs 300000.00 — `filings.csv row 11`
  - FIL-0014: commercial claim exactly Rs 300000.00 is NOT over Rs 3 lakh -> civil roster (round-robin); FIL-0015 at Rs 300001.00 -> commercial bench BEN-05 — `filings.csv row 14, filings.csv row 15`
  - FIL-0048: court fee short (paid Rs 20000.00 of Rs 23400.00) — DEFECTIVE, cured on day 7 by FEE_CURE -> registered; FIL-0049: deficient fee never cured — RETURNED after 7 days — `commands.txt lines 243, 276; filings.csv row 49`
  - FIL-0025: appeal on a Rs 1000000.00 claim pays 50% of the original fee = Rs 20500.00 — `filings.csv row 25`
  - FIL-0017: civil round-robin would give BEN-01, but the respondent is on that bench's conflict list — skipped, allocated to the other civil bench — `filings.csv row 17; bench_conflicts.csv row 12`
  - LGC-0005: respondent's 4th adjournment request in ISSUES with reason COUNSEL_UNAVAILABLE — REFUSED, the matter proceeds — `commands.txt line 76`
  - LGC-0027: petitioner's 3rd adjournment (after 2 earlier) — granted with Rs 2000.00 cost paid before the next date — `commands.txt lines 79, 87`
  - LGC-0007: TRANSFER BEN-02 -> BEN-01 (roster change) on 2026-05-06 — stage and adjournment counts carry over, next date recomputed on BEN-01; a second TRANSFER on 2026-06-10 must be REFUSED (once only) — `commands.txt lines 139, 277`
  - LGC-0014: in EVIDENCE since 2025-11-20 — crosses 180 days on 2026-05-19 -> DELAY flag to the principal judge; filed 2023-03-01 so it is also in band 4 (older than 2 years) — `pending_cases.csv row 14`
  - LGC-0051: family matter with a minor — heard in camera and listed only on BEN-04's designated day (WED) — `commands.txt lines 81, 145`
  - LGC-0026: HEARD with next stage ARGUMENTS from ISSUES without consent — skip REFUSED (stays ISSUES); at the next listing the same jump WITH consent is allowed — `commands.txt lines 93, 159`
  - LGC-0046: part-heard ARGUMENTS matter — band 2 and counts towards the 8 final-hearing cap — `pending_cases.csv row 46`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `admissions.csv`

One row per FILE command.

Columns, in order: `filing_id`, `limitation_last_day`, `limitation_status`, `court_fee_due`, `court_fee_paid`, `fee_status`, `bench_id`, `first_date`, `admission_status`

### `cause_lists.csv`

One row per listed matter per PRINT_CAUSE_LIST, in list order.

Columns, in order: `bench_id`, `list_date`, `serial_no`, `case_id`, `band`, `stage`, `flags`

### `case_diary.csv`

One row per hearing/event per printed case, in date order.

Columns, in order: `case_id`, `event_date`, `bench_id`, `stage`, `result`, `adjournments_petitioner`, `adjournments_respondent`, `cost`, `next_date`, `flags`

### `pendency.csv`

One row per bench per PRINT_PENDENCY.

Columns, in order: `as_of_date`, `bench_id`, `pending`, `decided_in_month`, `evidence_over_180_days`, `commercial_over_12_months`, `overboard`

Binding choices: limitation periods of years are counted to the same calendar date (3 years from 2023-05-01 ends 2026-05-01), plus wrong_forum_days, then moved to the next working day if the last day is a holiday or weekend. A newly registered case gets its first date by the same next-date rule (>= 14 days, 7 if urgent). A refused adjournment request is recorded as REFUSED and the matter proceeds as heard with no stage change. A transfer recomputes the next date on the new bench from the transfer date. `band` 0 (disposal-target override) to 6; `flags` semicolon list of URGENT, CARRY_OVER, BUMPED, OVERBOARD, DELAY, IN_CAMERA, DELAY_CONDONATION_PENDING.
