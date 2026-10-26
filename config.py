"""Configuration settings and constants for Court Case Listing and Adjournment Scheduling Engine.

Team ID: T070
Problem Statement: PS-118
"""

from decimal import Decimal

# Limitation Periods (BR-07)
CIVIL_LIMITATION_YEARS: int = 3
MONEY_RECOVERY_LIMITATION_YEARS: int = 3
APPEAL_LIMITATION_DAYS: int = 30
REVISION_LIMITATION_DAYS: int = 90

# Court Fee Schedule (BR-13, BR-14, BR-15, BR-16, BR-18)
FEE_BAND_1_THRESHOLD: Decimal = Decimal("100000")    # Up to 1 Lakh: 5%
FEE_BAND_1_RATE: Decimal = Decimal("0.05")
FEE_BAND_2_THRESHOLD: Decimal = Decimal("1000000")   # Above 1 Lakh up to 10 Lakh: 4%
FEE_BAND_2_RATE: Decimal = Decimal("0.04")
FEE_BAND_3_RATE: Decimal = Decimal("0.02")           # Above 10 Lakh: 2%
FEE_CAP: Decimal = Decimal("300000")                 # Cap at 3 Lakh
APPEAL_FEE_FACTOR: Decimal = Decimal("0.50")         # Appeals pay 50%
FEE_CURE_PERIOD_DAYS: int = 7                        # 7 days to cure deficient fee

# Bench Allocation (BR-02, BR-03, BR-04, BR-05)
COMMERCIAL_CLAIM_THRESHOLD: Decimal = Decimal("300000")  # Commercial claims > 3 Lakh must go to commercial bench

# Cause-List Scheduling (BR-19, BR-21, BR-22, BR-24, BR-25, BR-26, BR-27)
DAILY_BOARD_CAPACITY: int = 40
DAILY_FINAL_HEARING_CAP: int = 8
UNREACHED_ESCALATION_THRESHOLD: int = 3
COMMERCIAL_DISPOSAL_TARGET_DAYS: int = 365  # 12 months
COMMERCIAL_DISPOSAL_INTERVAL_DAYS: int = 7
URGENT_MENTION_CUTOFF_TIME: str = "10:30"
# Default designated family hearing day (3 = Thursday; Monday is 0)
DEFAULT_DESIGNATED_FAMILY_DAYS: list[int] = [3]

# Hearing & Adjournment Rules (BR-34, BR-35, BR-36, BR-37, BR-38, BR-39, BR-42)
MAX_ADJOURNMENTS_PER_STAGE: int = 3
PARTY_ADJOURNMENT_COST: Decimal = Decimal("2000")
COMMERCIAL_ADJOURNMENT_COST: Decimal = Decimal("4000")
MIN_NEXT_DATE_INTERVAL_DAYS: int = 14
MIN_NEXT_DATE_URGENT_INTERVAL_DAYS: int = 7
MAX_SCHEDULING_LOOKAHEAD_DAYS: int = 60
EVIDENCE_DELAY_THRESHOLD_DAYS: int = 180

# Flag Constants
FLAG_DELAY_CONDONATION_PENDING = "DELAY_CONDONATION_PENDING"
FLAG_DEFECTIVE = "DEFECTIVE"
FLAG_FEE_DEFICIENT = "FEE_DEFICIENT"
FLAG_OVERBOARD = "OVERBOARD"
FLAG_DELAY = "DELAY"
FLAG_IN_CAMERA = "IN_CAMERA"
FLAG_ESCALATED = "PRIORITY_ESCALATED"
FLAG_CARRIED_OVER = "CARRIED_OVER"
