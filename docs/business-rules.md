# Business-Rule Traceability Register (BR-01 to BR-51)

**Project Title:** Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods  
**Problem Statement:** PS-118  
**Team ID:** T070  

---

| BR-ID | Rule Description | Module | Test | Status |
| :--- | :--- | :--- | :--- | :--- |
| **BR-01** | **Bench registration:** Register each bench with subject jurisdictions, sitting days, daily capacity, leave dates and conflict party IDs. | `models.py`, `input_output.py` | `test_integration.py` | Implemented |
| **BR-02** | **Subject eligibility:** Assign cases only to benches whose roster includes the case subject: civil, criminal, family or commercial. | `allocation.py` | `test_allocation.py::test_valid_allocation`, `test_allocation.py::test_subject_mismatch` | Implemented |
| **BR-03** | **Commercial threshold:** Commercial claims over ₹3 lakh must go to a commercial bench. | `allocation.py` | `test_allocation.py::test_commercial_claim_threshold_exceeded`, `test_allocation.py::test_commercial_claim_at_or_below_threshold` | Implemented |
| **BR-04** | **Party conflicts:** Skip an otherwise eligible bench if its conflict list contains any party ID from the case. | `allocation.py` | `test_allocation.py::test_party_conflicts_exclude_bench` | Implemented |
| **BR-05** | **Round-robin allocation:** Distribute among eligible benches in round-robin order; maintain the next bench position per relevant roster/subject. | `allocation.py` | `test_allocation.py::test_round_robin_fairness` | Implemented |
| **BR-06** | **No eligible bench:** If none is eligible, report the case as unallocated with a reason; document the chosen status. | `allocation.py` | `test_allocation.py::test_no_eligible_bench_due_to_conflicts` | Implemented |
| **BR-07** | **Limitation periods:** Civil suits and money recovery: 3 years; appeals: 30 days from order; revisions: 90 days. | `admission.py` | `test_admission.py::test_civil_suit_limitation_three_years`, `test_admission.py::test_money_recovery_limitation_three_years`, `test_admission.py::test_appeal_limitation_thirty_days`, `test_admission.py::test_revision_limitation_ninety_days` | Implemented |
| **BR-08** | **Wrong-forum exclusion:** Exclude supplied wrong-forum time when calculating limitation. | `admission.py` | `test_admission.py::test_wrong_forum_exclusion` | Implemented |
| **BR-09** | **Holiday deadline:** If the limitation deadline falls on a court holiday, extend it to the next working day. | `admission.py` | `test_admission.py::test_holiday_deadline_adjustment` | Implemented |
| **BR-10** | **Late filing with condonation:** A late filing is accepted only with a condonation application and is flagged `DELAY_CONDONATION_PENDING`. | `admission.py` | `test_admission.py::test_late_filing_with_condonation_flagged` | Implemented |
| **BR-11** | **Late filing without application:** Reject or return a late filing without a condonation application, with a clear reason; record selected status. | `admission.py` | `test_admission.py::test_late_filing_without_condonation_rejected` | Implemented |
| **BR-12** | **Admission order:** Apply limitation (including exclusions and holiday extension) &rarr; fee sufficiency &rarr; roster &rarr; conflicts/allocation. | `admission.py`, `main.py` | `test_integration.py::test_complete_end_to_end_flow` | Implemented |
| **BR-13** | **Progressive fee bands:** Apply 5% up to ₹1 lakh; 4% on the portion above ₹1 lakh up to ₹10 lakh; 2% on the portion above ₹10 lakh. | `admission.py` | `test_admission.py::test_fee_band_1_below_one_lakh`, `test_admission.py::test_fee_band_2_intermediate`, `test_admission.py::test_fee_band_3_above_ten_lakh` | Implemented |
| **BR-14** | **Fee cap:** Cap the calculated fee at ₹3 lakh. | `admission.py` | `test_admission.py::test_fee_cap_three_lakh` | Implemented |
| **BR-15** | **Appeal fee:** Appeals pay 50% of the original fee. | `admission.py` | `test_admission.py::test_appeal_fee_reduction_fifty_percent` | Implemented |
| **BR-16** | **Deficient fee:** If fee is deficient, register as DEFECTIVE and allow 7 days to cure. | `admission.py` | `test_admission.py::test_deficient_fee_marked_defective_with_seven_day_cure` | Implemented |
| **BR-17** | **Uncured fee defect:** If not cured within 7 days, return the filing. | `admission.py` | `test_admission.py::test_uncured_defective_filing_returned` | Implemented |
| **BR-18** | **Fee boundaries:** Apply fee-band boundaries consistently at exactly ₹1 lakh and ₹10 lakh; document the progressive marginal-band interpretation. | `admission.py` | `test_admission.py::test_fee_band_1_boundary_one_lakh`, `test_admission.py::test_fee_band_2_boundary_ten_lakh` | Implemented |
| **BR-19** | **Priority bands:** Highest first: (1) urgent/bail, (2) part-heard, (3) 3+ adjournments, (4) older than 2 years, (5) final hearing, (6) all others. | `scheduling.py` | `test_scheduling.py::test_priority_band_1_urgent` through `test_priority_band_6_regular` | Implemented |
| **BR-20** | **Within-band order:** Within a priority band, list oldest filing date first. | `scheduling.py` | `test_scheduling.py::test_oldest_filing_date_first_within_band` | Implemented |
| **BR-21** | **Daily board capacity:** Maximum 40 matters per bench per day. | `scheduling.py` | `test_scheduling.py::test_maximum_forty_matters_daily_capacity` | Implemented |
| **BR-22** | **Final-hearing cap:** Maximum 8 final-hearing matters per bench per day. | `scheduling.py` | `test_scheduling.py::test_maximum_eight_final_hearing_matters` | Implemented |
| **BR-23** | **Carry-over:** Unreached matters carry to the next sitting day and go first within their band. | `scheduling.py` | `test_scheduling.py::test_carry_over_matters_listed_first_within_band` | Implemented |
| **BR-24** | **Unreached escalation:** A matter unreached on 3 consecutive sittings moves up one band. | `scheduling.py` | `test_scheduling.py::test_priority_escalation_after_three_unreached_sittings` | Implemented |
| **BR-25** | **Commercial disposal target:** Commercial cases past 12 months from filing are listed every 7 days until decided; this target overrides ordinary priorities. | `scheduling.py`, `reporting.py` | `test_reporting.py::test_pendency_report_identifies_overdue_and_delay` | Implemented |
| **BR-26** | **Family/minor matters:** Family cases involving a minor are heard in camera and listed only on designated days; designated days must be supplied or agreed as an assumption. | `scheduling.py` | `test_scheduling.py::test_family_minor_designated_day_restriction` | Implemented |
| **BR-27** | **Urgent/bail mention:** Mention before 10:30: same day if board has fewer than 40 matters; otherwise next sitting day at position 1. | `scheduling.py` | `test_scheduling.py::test_urgent_mention_before_cutoff_same_day_listed`, `test_scheduling.py::test_urgent_mention_before_cutoff_board_full_next_day_pos_1`, `test_scheduling.py::test_urgent_mention_after_cutoff_next_day` | Implemented |
| **BR-28** | **Priority precedence:** Precedence: disposal target &rarr; urgent &rarr; carry-over bumps &rarr; standard bands &rarr; capacity caps. | `scheduling.py` | `test_scheduling.py` | Implemented |
| **BR-29** | **Hearing outcomes:** Support HEARD, PART_HEARD, ADJOURNED, DECIDED and TRANSFERRED. | `models.py`, `hearings.py` | `test_hearings.py` | Implemented |
| **BR-30** | **Case stages:** Stages progress PLEADINGS &rarr; ISSUES &rarr; EVIDENCE &rarr; ARGUMENTS &rarr; JUDGMENT. | `models.py`, `hearings.py` | `test_hearings.py::test_stage_progression_sequential` | Implemented |
| **BR-31** | **No stage skipping:** Do not skip stages unless the event has a consent flag. | `hearings.py` | `test_hearings.py::test_stage_skipping_prevented_without_consent`, `test_hearings.py::test_stage_skipping_allowed_with_consent` | Implemented |
| **BR-32** | **Arguments priority:** Reaching ARGUMENTS gives final-hearing priority, still subject to the cap of 8. | `hearings.py`, `scheduling.py` | `test_scheduling.py::test_priority_band_5_final_hearing` | Implemented |
| **BR-33** | **Evidence delay:** More than 180 days in EVIDENCE triggers a DELAY flag and principal-judge report. | `reporting.py` | `test_reporting.py::test_pendency_report_identifies_overdue_and_delay` | Implemented |
| **BR-34** | **Adjournment limit:** Maximum 3 adjournments per party per stage; refuse the 4th unless reason is MEDICAL or COURT_OCCASIONED. | `hearings.py` | `test_hearings.py::test_adjournment_count_and_fourth_refusal` | Implemented |
| **BR-35** | **Court-occasioned adjournment:** Court-occasioned adjournments do not count against a party. | `hearings.py` | `test_hearings.py::test_court_occasioned_adjournment_does_not_count_against_party` | Implemented |
| **BR-36** | **Party adjournment cost:** A party adjournment after 2 earlier adjournments costs ₹2,000. | `hearings.py` | `test_hearings.py::test_adjournment_costs` | Implemented |
| **BR-37** | **Commercial adjournment cost:** Double the adjournment cost for commercial cases (₹4,000). | `hearings.py` | `test_hearings.py::test_adjournment_costs` | Implemented |
| **BR-38** | **Cost payment timing:** Adjournment cost is payable before the next date. | `hearings.py` | `test_hearings.py` | Implemented (Scaffolded) |
| **BR-39** | **Minimum interval to next date:** Next date is the next eligible bench sitting day at least 14 days after adjournment, or 7 days for urgent cases. | `hearings.py` | `test_hearings.py::test_next_hearing_date_minimum_interval_and_calendar` | Implemented |
| **BR-40** | **Calendar exclusions:** Skip bench leave days and court holidays. | `hearings.py`, `scheduling.py` | `test_hearings.py::test_next_hearing_date_minimum_interval_and_calendar` | Implemented |
| **BR-41** | **Capacity on next date:** The selected next date must have board capacity. | `hearings.py` | `test_hearings.py` | Implemented |
| **BR-42** | **Overboard fallback:** If no date has capacity within 60 days, list on day 60 and add OVERBOARD. | `hearings.py` | `test_hearings.py` | Implemented |
| **BR-43** | **Medical fourth adjournment:** MEDICAL permits a fourth adjournment under the exception; whether it incurs a cost is unspecified and must be documented. | `hearings.py`, `docs/decision-log.md` | `test_hearings.py::test_adjournment_count_and_fourth_refusal` | Implemented |
| **BR-44** | **Transfer limit and reason:** Transfer a case at most once, and only because of roster change or conflict. | `hearings.py` | `tests/` | Partially Implemented (Week 3) |
| **BR-45** | **Destination eligibility:** Check destination roster eligibility and conflicts against all case parties. | `allocation.py`, `hearings.py` | `tests/` | Partially Implemented (Week 3) |
| **BR-46** | **Preserve history on transfer:** Preserve stage and adjournment history when transferring. | `hearings.py` | `tests/` | Partially Implemented (Week 3) |
| **BR-47** | **Transfer counts as adjournment:** Count a transfer as an adjournment. | `hearings.py` | `tests/` | Partially Implemented (Week 3) |
| **BR-48** | **Recompute after transfer:** Recompute next date using the destination bench calendar, leave, holidays and capacity. | `hearings.py` | `tests/` | Partially Implemented (Week 3) |
| **BR-49** | **Cause-list report:** Print daily cause lists by bench, showing order and carry-over where applicable. | `reporting.py` | `test_reporting.py::test_cause_list_report_format` | Implemented |
| **BR-50** | **Case diary:** Include admission, fee, bench, stage, hearing history, adjournments/costs, flags and next date. | `reporting.py` | `test_reporting.py::test_case_diary_contains_lifecycle_fields` | Implemented |
| **BR-51** | **Pendency report:** Include pending cases, age, stage, overdue commercial targets and evidence-delay flags. | `reporting.py` | `test_reporting.py::test_pendency_report_identifies_overdue_and_delay` | Implemented |
