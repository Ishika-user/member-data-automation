"""
Tests for the full cleaning/validation pipeline in src/transform.py and
src/validate.py, using small synthetic DataFrames with fictional names only.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform import process_dataframe
from src.validate import overall_status, run_validations


def _raw_row(member_no, name, nepali, gender, source_row_number):
    return {
        "original_member_no": member_no,
        "member_name": name,
        "nepali_name": nepali,
        "gender": gender,
        "source_row_number": source_row_number,
    }


def _base_raw_df():
    rows = [
        _raw_row(1, "Alpha Fictional", "अल्फा काल्पनिक", "Male", 2),
        _raw_row(2, "Bravo Fictional", "ब्राभो काल्पनिक", "Female", 3),
        _raw_row(3, "Charlie Fictional", None, None, 4),
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Missing member number handling
# ---------------------------------------------------------------------------
def test_missing_member_number_goes_to_manual_review():
    df = pd.DataFrame([_raw_row(None, "Delta Fictional", None, "Male", 5)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 0
    assert result["manual_review"].iloc[0]["review_reason"] == "Missing original member number"


def test_invalid_member_number_goes_to_manual_review():
    df = pd.DataFrame([_raw_row("XYZ", "Echo Fictional", None, "Male", 6)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 0
    assert "Invalid original member number" in result["manual_review"].iloc[0]["review_reason"]


def test_missing_member_name_goes_to_manual_review():
    df = pd.DataFrame([_raw_row(10, None, "नामविहीन", "Female", 7)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 0
    assert result["manual_review"].iloc[0]["review_reason"] == "Missing member name"


def test_missing_nepali_name_does_not_trigger_review():
    df = pd.DataFrame([_raw_row(11, "Foxtrot Fictional", None, "Male", 8)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 1
    assert len(result["manual_review"]) == 0


def test_missing_gender_does_not_trigger_review():
    df = pd.DataFrame([_raw_row(12, "Golf Fictional", "गल्फ काल्पनिक", None, 9)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 1
    assert pd.isna(result["cleaned"].iloc[0]["gender"])


def test_unsupported_gender_kept_with_null_gender():
    df = pd.DataFrame([_raw_row(13, "Hotel Fictional", "होटल काल्पनिक", "Other", 10)])
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 1
    assert pd.isna(result["cleaned"].iloc[0]["gender"])
    assert result["stats"]["unsupported_gender_count"] == 1


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------
def test_exact_duplicate_removed_keeps_one():
    df = pd.DataFrame(
        [
            _raw_row(20, "India Fictional", "इन्डिया काल्पनिक", "Male", 11),
            _raw_row(20, "India Fictional", "इन्डिया काल्पनिक", "Male", 12),
        ]
    )
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 1
    assert result["stats"]["exact_duplicate_rows_removed"] == 1


def test_same_number_same_name_prefers_most_complete_record():
    df = pd.DataFrame(
        [
            _raw_row(21, "Juliet Fictional", "जुलिएट काल्पनिक", "Female", 13),
            _raw_row(21, "juliet   fictional", None, None, 14),
        ]
    )
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 1
    kept = result["cleaned"].iloc[0]
    assert kept["nepali_name"] == "जुलिएट काल्पनिक"
    assert kept["gender"] == "Female"
    assert result["stats"]["same_name_duplicate_rows_removed"] == 1


def test_same_number_conflicting_names_go_to_manual_review():
    df = pd.DataFrame(
        [
            _raw_row(22, "Kilo Fictional", "किलो काल्पनिक", "Male", 15),
            _raw_row(22, "Lima Fictional", "लिमा काल्पनिक", "Female", 16),
        ]
    )
    result = process_dataframe(df)
    assert len(result["cleaned"]) == 0
    assert len(result["manual_review"]) == 2
    assert (result["manual_review"]["review_reason"] == "Conflicting names for the same member number").all()
    assert result["stats"]["conflicting_member_number_groups"] == 1


# ---------------------------------------------------------------------------
# Output schema and sequential IDs
# ---------------------------------------------------------------------------
def test_output_schema_matches_requirement():
    df = _base_raw_df()
    result = process_dataframe(df)
    assert list(result["cleaned"].columns) == ["member_no", "member_name", "nepali_name", "gender"]


def test_sequential_ids_start_at_one_no_gaps():
    df = _base_raw_df()
    result = process_dataframe(df)
    cleaned = result["cleaned"]
    assert cleaned["member_no"].min() == 1
    assert sorted(cleaned["member_no"].tolist()) == list(range(1, len(cleaned) + 1))


# ---------------------------------------------------------------------------
# Reconciliation formula
# ---------------------------------------------------------------------------
def test_reconciliation_formula_holds():
    df = pd.DataFrame(
        [
            _raw_row(30, "Mike Fictional", "माइक काल्पनिक", "Male", 17),
            _raw_row(31, "November Fictional", "नोभेम्बर काल्पनिक", "Female", 18),
            _raw_row(None, "Oscar Fictional", None, "Male", 19),
            _raw_row(32, "Papa Fictional", "पापा काल्पनिक", "Male", 20),
            _raw_row(32, "Papa Fictional", "पापा काल्पनिक", "Male", 21),
        ]
    )
    result = process_dataframe(df)
    stats = result["stats"]
    raw = stats["raw_record_count"]
    cleaned = stats["cleaned_record_count"]
    review = stats["manual_review_record_count"]
    dup_removed = stats["total_duplicate_rows_removed"]
    assert raw == cleaned + review + dup_removed


# ---------------------------------------------------------------------------
# Validation module - success and failure detection
# ---------------------------------------------------------------------------
def test_validation_success_on_healthy_dataset():
    df = _base_raw_df()
    result = process_dataframe(df)
    validation_results = run_validations(
        cleaned_df=result["cleaned"],
        manual_review_df=result["manual_review"],
        stats=result["stats"],
        column_mapping_complete=True,
        checksum_before="abc123",
        checksum_after="abc123",
        output_files_exist=True,
    )
    status = overall_status(validation_results)
    assert status == "PASSED"


def test_validation_detects_checksum_mismatch_as_failed():
    df = _base_raw_df()
    result = process_dataframe(df)
    validation_results = run_validations(
        cleaned_df=result["cleaned"],
        manual_review_df=result["manual_review"],
        stats=result["stats"],
        column_mapping_complete=True,
        checksum_before="abc123",
        checksum_after="DIFFERENT",
        output_files_exist=True,
    )
    status = overall_status(validation_results)
    assert status == "FAILED"
    checksum_result = [r for r in validation_results if "Original workbook was not modified" in r["rule"]][0]
    assert checksum_result["passed"] == "Failed"


def test_validation_detects_missing_output_files_as_failed():
    df = _base_raw_df()
    result = process_dataframe(df)
    validation_results = run_validations(
        cleaned_df=result["cleaned"],
        manual_review_df=result["manual_review"],
        stats=result["stats"],
        column_mapping_complete=True,
        checksum_before="abc123",
        checksum_after="abc123",
        output_files_exist=False,
    )
    status = overall_status(validation_results)
    assert status == "FAILED"
