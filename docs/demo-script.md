# Demo Video Script (5 minutes)

**Project:** Court Case Listing and Adjournment Scheduling Engine (PS-118, Team T070)
**Target length:** 5:00 (keep under the limit; the plan below totals 4:55)

Every command below was run against the repository and the output described is what it prints. Record the terminal with the font enlarged so the text is readable.

---

## Before recording

1. Open a terminal in the project folder and activate the virtual environment (`.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` on Linux or macOS).
2. Run `pip install -r requirements.txt` once.
3. Delete old generated files: remove the `output/` contents (it is git-ignored).
4. Have these open in tabs, ready to show: `README.md`, `docs/design-document.md`, `docs/decision-log.md`.
5. Rehearse once with a timer. The official run takes about a second, so no waiting is needed.

---

## Timeline

| Time | Screen | What to say |
| --- | --- | --- |
| **0:00 to 0:30** | README title and Section 2 | "This is our court case listing and adjournment scheduling engine for problem statement PS-118. It simulates a district court registry: it checks limitation and court fee when a case is filed, allocates it to a bench, builds the daily cause list by priority, and manages hearings, adjournments, costs and transfers. It is a Python command-line program, and all 51 business rules are implemented." |
| **0:30 to 1:10** | File tree, then `docs/design-document.md` (scroll to the class diagram and state diagram), then `docs/decision-log.md` | "The code is split by responsibility: admission, allocation, scheduling, hearings and reporting, with shared models and constants. The design document has the class and state diagrams. Wherever the brief was ambiguous we recorded our choice in the decision log, with the test that covers it. Every rule from BR-01 to BR-51 is traced to its function and test in `docs/business-rules.md`." |
| **1:10 to 1:40** | Terminal: run the tests | "First the test suite." Run `python -m pytest -q`. Wait for **106 passed**. "106 tests across 8 modules, including a module that replays the official sample data and checks each planted edge case." |
| **1:40 to 2:20** | Terminal: standard run | "Now a normal run on our sample data." Run `python main.py --data-dir data --output-dir output --date 2026-10-29 --verbose`. Point at the summary (10 filings, 8 admitted, 1 defective, 1 rejected) and at one cause list. "Band 5 is a final-hearing matter, so it is listed first on its bench. The flag on this one shows a delay condonation application is pending." |
| **2:20 to 2:45** | Terminal: official run | "Now the official data pack: 80 filings and about 680 commands over six months, processed strictly in order." Run the command in the table below. It prints the four CSV files and their row counts: 80, 130, 381 and 30. |
| **2:45 to 4:15** | Terminal: edge-case checks (see below) | Walk through six checks, about 15 seconds each. |
| **4:15 to 4:45** | `docs/decision-log.md` | "Two examples of decisions we documented. DEC-03: court fee is calculated in marginal slices, 5% up to one lakh, 4% up to ten lakh, 2% above, capped at three lakh. DEC-10: if no date with capacity exists within 60 days, the matter is listed on day 60 and flagged OVERBOARD." |
| **4:45 to 4:55** | README Section 11 | "Known limitations are listed in the README, and the open questions we want to confirm are marked in the decision log. Thank you." |

---

## Commands

**Official run** (works the same in PowerShell and bash):

```
python main.py --commands data/official_sample/T070-PS-118-sample-data/commands.txt --data-dir data/official_sample/T070-PS-118-sample-data --output-dir output/official_run
```

**Edge-case checks.** Use the line that matches your shell.

| # | Edge case | PowerShell | bash | What it shows |
| --- | --- | --- | --- | --- |
| 1 | EC-01 limitation ends on a holiday | `Select-String -Path output\official_run\admissions.csv -Pattern "^FIL-0021,"` | `grep "^FIL-0021," output/official_run/admissions.csv` | Limitation last day `2026-05-04` (the 1 May holiday and the weekend are skipped), status `IN_TIME` |
| 2 | EC-02 fee at exactly ₹1 lakh and ₹10 lakh | `Select-String -Path output\official_run\admissions.csv -Pattern "^FIL-0004,","^FIL-0005,"` | `grep -E "^(FIL-0004\|FIL-0005)," output/official_run/admissions.csv` | Fees `5000.00` and `41000.00`, both `PAID` |
| 3 | EC-03 fourth adjournment, reason MEDICAL | `Select-String -Path output\official_run\case_diary.csv -Pattern "^LGC-0031,2026-04-20"` | `grep "^LGC-0031,2026-04-20" output/official_run/case_diary.csv` | Petitioner count `4`, cost `2000.00`: the medical exception is granted |
| 4 | EC-04 urgent mention on a full board | `Select-String -Path output\official_run\cause_lists.csv -Pattern "FIL-0007"` | `grep "FIL-0007" output/official_run/cause_lists.csv` | Listed on `BEN-03` on `2026-04-16` at serial `1` with `URGENT`, because the 15 April board was already at 40 |
| 5 | EC-05 14 days lands on a leave day | `Select-String -Path output\official_run\case_diary.csv -Pattern "^LGC-0044,2026-06-09"` | `grep "^LGC-0044,2026-06-09" output/official_run/case_diary.csv` | Next date `2026-06-25` instead of the leave day `2026-06-23` |
| 6 | EC-06 not reached on three sittings | `Select-String -Path output\official_run\cause_lists.csv -Pattern "LGC-0008" \| Select-Object -First 4` | `grep "LGC-0008" output/official_run/cause_lists.csv \| head -4` | Listed 1 June, carried over on 2 and 3 June (band `6`), then on the 4th listing (4 June) it moves up to band `2` with `BUMPED` |

If time allows, two more worth showing: `LGC-0017` on `2026-07-09` (EC-07: commercial case listed every 7 days, next date `2026-07-16`) and `LGC-0056` in `case_diary.csv` (EC-08: the transfer to a conflicted bench was refused, so every row stays on `BEN-01`).

---

## Tips

- **Do not read the CSV rows aloud.** Point at the one or two columns that matter (the dates, the fee, the flag) and say what they prove.
- **Keep the order.** Tests, then a normal run, then the official data, so the viewer sees correctness before detail.
- **If something prints differently** from this script, stop and check it before recording; the numbers above come from the current repository state (106 tests; 80, 130, 381 and 30 rows).
- **After uploading,** paste the video link into README Section 10 and tick the last box in Section 12.
