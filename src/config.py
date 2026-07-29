"""
Configuration module for the Automated Member Data Migration and QA System.

Holds path configuration, standardized schema definitions, logging
configuration, and execution mode toggles. No user-specific absolute
paths or credentials are hard-coded here.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PRIVATE_INPUT_DIR = PROJECT_ROOT / "data" / "private"
SAMPLE_INPUT_DIR = PROJECT_ROOT / "data" / "sample"

PRIVATE_OUTPUT_DIR = PROJECT_ROOT / "output" / "private"
SAMPLE_OUTPUT_DIR = PROJECT_ROOT / "output" / "sample"

DEFAULT_PRIVATE_INPUT = PRIVATE_INPUT_DIR / "source_member_data.xlsx"
DEFAULT_SAMPLE_INPUT = SAMPLE_INPUT_DIR / "synthetic_member_data.xlsx"

# ---------------------------------------------------------------------------
# Standardized schema
# ---------------------------------------------------------------------------
# Internal, working column names used throughout extraction/transformation.
STANDARD_SOURCE_COLUMNS = [
    "original_member_no",
    "member_name",
    "nepali_name",
    "gender",
]

# Final migration-ready output schema (no original_member_no exposed).
FINAL_OUTPUT_COLUMNS = [
    "member_no",
    "member_name",
    "nepali_name",
    "gender",
]

MANUAL_REVIEW_COLUMNS = [
    "source_row_number",
    "original_member_no",
    "member_name",
    "nepali_name",
    "original_gender",
    "standardized_gender",
    "review_reason",
]

ALLOWED_GENDER_VALUES = {"Male", "Female"}

# Mapping of normalized (lowercase, single-spaced, stripped) source header
# fragments to the standardized internal field name. Matching is done via
# "contains" checks in extract.py to tolerate irregular spacing/punctuation.
HEADER_MATCH_RULES = {
    "original_member_no": ["member no", "member number", "memberno"],
    "member_name": ["members name", "member name", "member's name"],
    "nepali_name": ["nepali name"],
    "gender": ["gender"],
}

# ---------------------------------------------------------------------------
# Output filenames
# ---------------------------------------------------------------------------
CLEANED_MEMBERS_FILENAME = "cleaned_members.xlsx"
MANUAL_REVIEW_FILENAME = "manual_review.xlsx"
QA_REPORT_FILENAME = "qa_report.xlsx"
LOG_FILENAME = "automation.log"

CLEANED_MEMBERS_SAMPLE_FILENAME = "cleaned_members_sample.xlsx"
MANUAL_REVIEW_SAMPLE_FILENAME = "manual_review_sample.xlsx"
QA_REPORT_SAMPLE_FILENAME = "qa_report_sample.xlsx"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
LOG_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------
MODE_PRIVATE = "private"
MODE_SAMPLE = "sample"
VALID_MODES = {MODE_PRIVATE, MODE_SAMPLE}

# ---------------------------------------------------------------------------
# SQL loading safety switches (both must be true to load data)
# ---------------------------------------------------------------------------
ALLOW_SQL_LOAD_ENV = os.getenv("ALLOW_SQL_LOAD", "false").strip().lower() == "true"
SQL_CONNECTION_STRING_ENV = os.getenv("SQL_CONNECTION_STRING", "")
SQL_TARGET_TABLE_ENV = os.getenv("SQL_TARGET_TABLE", "Member")

# ---------------------------------------------------------------------------
# Private comparison baseline (NOT for public reporting)
# ---------------------------------------------------------------------------
PRIVATE_BASELINE_CLEANED_COUNT = 755


def ensure_directories() -> None:
    """Create all required directories if they do not already exist."""
    for directory in (
        PRIVATE_INPUT_DIR,
        SAMPLE_INPUT_DIR,
        PRIVATE_OUTPUT_DIR,
        SAMPLE_OUTPUT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
