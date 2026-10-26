# Glossary of Terms

**Project Title:** Court Case Listing and Adjournment Scheduling Engine with Cause-list Priorities and Limitation Periods  
**Problem Statement:** PS-118  
**Team ID:** T070  

---

| Term | Definition |
| :--- | :--- |
| **Bench** | A judicial court unit defined by subject jurisdictions, roster rules, daily board capacity, sitting calendar, leave dates, and party conflicts. |
| **Case / Filing** | A matter submitted to the court registry containing subject matter, parties, cause-of-action/order date, claim value, and urgency status. |
| **Cause List** | The deterministically ordered list of cases scheduled for hearing before a specific bench on a given sitting date. |
| **Limitation Period** | The statutory window within which a suit, appeal, or revision must be instituted before the court. |
| **Wrong-Forum Exclusion** | Qualifying time spent bona fide pursuing litigation before a forum lacking jurisdiction, excluded from limitation computation. |
| **Condonation** | A formal application requesting the court to excuse delay in filing beyond the prescribed limitation period. |
| **Court Fee** | The statutory ad valorem fee payable at filing, calculated using marginal progressive percentage bands and subject to a statutory cap. |
| **Defective Filing** | A filing marked with insufficient court fee or procedural defect, granted a mandatory 7-day cure window. |
| **Priority Band** | Hierarchical ranking categories (Band 1 through Band 6) used to determine listing priority on a bench's daily board. |
| **Carry-Over** | An unreached matter from an earlier sitting day that is carried over to the next eligible sitting day and given top priority within its band. |
| **Adjournment** | Formal postponement of a scheduled hearing to a future sitting date, subject to stage limits, party cost penalties, and court calendar rules. |
| **Stage** | Sequential phase of the civil/criminal lifecycle: `PLEADINGS` &rarr; `ISSUES` &rarr; `EVIDENCE` &rarr; `ARGUMENTS` &rarr; `JUDGMENT`. |
| **OVERBOARD** | Diagnostic flag assigned when a case cannot be scheduled within board capacity within the 60-day scheduling horizon and is listed on Day 60. |
| **Pendency** | The active backlog of unresolved cases before the court, analyzed by case age, stage duration, and delay indicators. |
| **In Camera** | Proceedings conducted in private chambers; family matters involving minors are restricted to designated hearing days. |
| **Command-File Driven** | System architecture where execution is controlled via structured CLI commands and batch data files (JSON), with no GUI required. |
