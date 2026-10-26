"""Domain models for Court Case Listing and Adjournment Scheduling Engine.

Team ID: T070
Problem Statement: PS-118
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum, IntEnum


class SubjectType(str, Enum):
    CIVIL = "CIVIL"
    COMMERCIAL = "COMMERCIAL"
    FAMILY = "FAMILY"
    CRIMINAL = "CRIMINAL"


class CaseStatus(str, Enum):
    FILED = "FILED"
    UNDER_SCRUTINY = "UNDER_SCRUTINY"
    ADMITTED = "ADMITTED"
    DEFECTIVE = "DEFECTIVE"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"
    ALLOCATED = "ALLOCATED"
    LISTED = "LISTED"
    HEARD = "HEARD"
    ADJOURNED = "ADJOURNED"
    DECIDED = "DECIDED"
    TRANSFERRED = "TRANSFERRED"


class CaseStage(str, Enum):
    PLEADINGS = "PLEADINGS"
    ISSUES = "ISSUES"
    EVIDENCE = "EVIDENCE"
    ARGUMENTS = "ARGUMENTS"
    JUDGMENT = "JUDGMENT"


class HearingOutcome(str, Enum):
    HEARD = "HEARD"
    PART_HEARD = "PART_HEARD"
    ADJOURNED = "ADJOURNED"
    DECIDED = "DECIDED"
    TRANSFERRED = "TRANSFERRED"


class AdjournmentReason(str, Enum):
    PARTY_REQUEST = "PARTY_REQUEST"
    MEDICAL = "MEDICAL"
    COURT_OCCASIONED = "COURT_OCCASIONED"
    ROSTER_CHANGE = "ROSTER_CHANGE"
    CONFLICT = "CONFLICT"
    LAWYER_ABSENT = "LAWYER_ABSENT"
    OTHER = "OTHER"


class PriorityBand(IntEnum):
    BAND_1_URGENT = 1
    BAND_2_PART_HEARD = 2
    BAND_3_THREE_PLUS_ADJOURNMENTS = 3
    BAND_4_OLDER_THAN_TWO_YEARS = 4
    BAND_5_FINAL_HEARING = 5
    BAND_6_REGULAR = 6


class AdmissionDecision(str, Enum):
    ADMITTED = "ADMITTED"
    DEFECTIVE = "DEFECTIVE"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


@dataclass
class HearingEvent:
    event_id: str
    case_id: str
    hearing_date: date
    outcome: HearingOutcome
    adjournment_reason: AdjournmentReason | None = None
    requesting_party: str | None = None
    consent_indicator: bool = False
    mentioned_at: str | None = None
    notes: str = ""


@dataclass
class Case:
    case_id: str
    case_type: str
    subject: SubjectType
    party_ids: list[str]
    filing_date: date
    cause_of_action_date: date | None = None
    order_date: date | None = None
    claim_value: Decimal = Decimal("0")
    court_fee_paid: Decimal = Decimal("0")
    urgency: bool = False
    status: CaseStatus = CaseStatus.FILED
    stage: CaseStage = CaseStage.PLEADINGS
    adjournment_history: list[HearingEvent] = field(default_factory=list)
    assigned_bench: str | None = None
    next_hearing_date: date | None = None
    carry_over_count: int = 0
    consecutive_unreached_count: int = 0
    final_hearing: bool = False
    flags: set[str] = field(default_factory=set)
    wrong_forum_days: int = 0
    has_condonation_application: bool = False
    cure_deadline: date | None = None
    involves_minor: bool = False
    is_part_heard: bool = False
    stage_start_date: date | None = None
    transferred_count: int = 0

    @property
    def is_appeal(self) -> bool:
        return "APPEAL" in self.case_type.upper()

    @property
    def is_revision(self) -> bool:
        return "REVISION" in self.case_type.upper()


@dataclass
class Bench:
    bench_id: str
    subject_jurisdictions: list[SubjectType]
    commercial_jurisdiction: bool = False
    sitting_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # 0=Mon, ..., 4=Fri
    daily_board_capacity: int = 40
    leave_dates: set[date] = field(default_factory=set)
    conflict_party_ids: set[str] = field(default_factory=set)
    designated_family_hearing_days: list[int] = field(default_factory=lambda: [3])  # Thursday default


@dataclass
class CauseListEntry:
    case_id: str
    bench_id: str
    listing_date: date
    priority_band: PriorityBand
    position: int
    carry_over_indicator: bool = False
    final_hearing_indicator: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class AdmissionResult:
    case_id: str
    decision: AdmissionDecision
    limitation_deadline: date
    applicable_fee: Decimal
    paid_fee: Decimal
    defect_or_rejection_reason: str | None = None
    required_flags: list[str] = field(default_factory=list)
    cure_deadline: date | None = None


@dataclass
class AllocationResult:
    case_id: str
    allocated_bench_id: str | None
    success: bool
    reason: str | None = None
