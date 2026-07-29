"""
Integration-level tests: header normalization, column mapping, checksum
protection of the original file, and Nepali Unicode round-tripping through
Excel. Uses only synthetic, fictional data written to a temporary workbook.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extract import (
    MissingColumnsError,
    extract_members,
)
from src.validate import compute_file_checksum
from src.report import write_simple_workbook


@pytest.fixture()
def synthetic_workbook(tmp_path) -> Path:
    """Create a small synthetic workbook with irregular header spacing."""
    df = pd.DataFrame(
        {
            "  Member No#": [1, 2, 3],
            "Members   Name": ["Alpha Fictional", "Bravo Fictional", "Charlie Fictional"],
            " NEPALI NAME ": ["अल्फा काल्पनिक", "ब्राभो काल्पनिक", "चार्ली काल्पनिक"],
            "Gender": ["Male", "Female", "M"],
        }
    )
    path = tmp_path / "synthetic_test_workbook.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    return path


@pytest.fixture()
def workbook_missing_columns(tmp_path) -> Path:
    df = pd.DataFrame({"Some Other Column": [1, 2, 3], "Unrelated": ["a", "b", "c"]})
    path = tmp_path / "bad_workbook.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    return path


# ---------------------------------------------------------------------------
# Header normalization / column mapping
# ---------------------------------------------------------------------------
def test_header_normalization_and_mapping(synthetic_workbook):
    df, meta = extract_members(synthetic_workbook)
    assert set(["original_member_no", "member_name", "nepali_name", "gender", "source_row_number"]) == set(
        df.columns
    )
    assert len(df) == 3
    assert meta.input_row_count == 3


def test_required_column_mapping_present(synthetic_workbook):
    df, meta = extract_members(synthetic_workbook)
    assert set(meta.column_mapping.keys()) == {
        "original_member_no",
        "member_name",
        "nepali_name",
        "gender",
    }


def test_missing_required_columns_raises_error(workbook_missing_columns):
    with pytest.raises(MissingColumnsError):
        extract_members(workbook_missing_columns)


# ---------------------------------------------------------------------------
# Nepali Unicode preservation
# ---------------------------------------------------------------------------
def test_nepali_unicode_preserved_through_extraction(synthetic_workbook):
    df, meta = extract_members(synthetic_workbook)
    assert "अल्फा काल्पनिक" in df["nepali_name"].tolist()


def test_nepali_unicode_round_trips_through_excel_write(tmp_path):
    df = pd.DataFrame(
        {
            "member_no": [1, 2],
            "member_name": ["Alpha Fictional", "Bravo Fictional"],
            "nepali_name": ["अल्फा काल्पनिक", "ब्राभो काल्पनिक"],
            "gender": ["Male", "Female"],
        }
    )
    out_path = tmp_path / "roundtrip.xlsx"
    write_simple_workbook(df, out_path)
    read_back = pd.read_excel(out_path)
    assert read_back["nepali_name"].tolist() == ["अल्फा काल्पनिक", "ब्राभो काल्पनिक"]


# ---------------------------------------------------------------------------
# Original-file checksum protection
# ---------------------------------------------------------------------------
def test_checksum_unchanged_after_read_only_extraction(synthetic_workbook):
    before = compute_file_checksum(synthetic_workbook)
    extract_members(synthetic_workbook)
    after = compute_file_checksum(synthetic_workbook)
    assert before == after


def test_checksum_detects_modification(tmp_path):
    path = tmp_path / "file.xlsx"
    df = pd.DataFrame({"a": [1, 2, 3]})
    df.to_excel(path, index=False)
    before = compute_file_checksum(path)
    # Modify the file
    df2 = pd.DataFrame({"a": [1, 2, 3, 4]})
    df2.to_excel(path, index=False)
    after = compute_file_checksum(path)
    assert before != after
