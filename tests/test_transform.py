"""
Unit tests for src/transform.py using small, entirely fictional data.
No real member records are used anywhere in this test suite.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform import (
    clean_member_name,
    clean_member_number,
    clean_nepali_name,
    clean_text,
    normalize_for_comparison,
    standardize_gender,
    generate_sequential_ids,
)


# ---------------------------------------------------------------------------
# clean_text / name cleaning
# ---------------------------------------------------------------------------
def test_clean_text_trims_and_collapses_whitespace():
    assert clean_text("  Fictional   Name  ") == "Fictional Name"


def test_clean_text_none_returns_none():
    assert clean_text(None) is None


def test_clean_text_nan_returns_none_not_string():
    assert clean_text(float("nan")) is None


def test_clean_text_empty_string_returns_none():
    assert clean_text("   ") is None


def test_clean_member_name_preserves_punctuation_and_case():
    assert clean_member_name("Dr. Fictional  O'Test") == "Dr. Fictional O'Test"


def test_clean_nepali_name_preserves_unicode():
    nepali = "  फिक्शनल   नाम "
    result = clean_nepali_name(nepali)
    assert result == "फिक्शनल नाम"
    assert "फिक्शनल" in result


def test_clean_nepali_name_missing_is_nullable():
    assert clean_nepali_name(None) is None


# ---------------------------------------------------------------------------
# Member number cleaning
# ---------------------------------------------------------------------------
def test_valid_integer_member_number():
    value, valid, audit = clean_member_number(501)
    assert value == 501
    assert valid is True
    assert audit is None


def test_valid_integer_like_float_member_number():
    value, valid, audit = clean_member_number(501.0)
    assert value == 501
    assert valid is True


def test_missing_member_number_is_invalid():
    value, valid, audit = clean_member_number(None)
    assert valid is False
    assert value is None


def test_nan_member_number_is_invalid():
    value, valid, audit = clean_member_number(float("nan"))
    assert valid is False


def test_nonnumeric_member_number_is_invalid():
    value, valid, audit = clean_member_number("ABC123")
    assert valid is False
    assert value is None


def test_fractional_member_number_is_invalid():
    value, valid, audit = clean_member_number(245.5)
    assert valid is False


def test_fractional_text_member_number_is_invalid():
    value, valid, audit = clean_member_number("245.5")
    assert valid is False


def test_leading_zero_member_number_preserves_audit():
    value, valid, audit = clean_member_number("0099")
    assert valid is True
    assert value == 99
    assert audit == "0099"


def test_plain_text_number_no_leading_zero_audit():
    value, valid, audit = clean_member_number("501")
    assert valid is True
    assert audit is None


# ---------------------------------------------------------------------------
# Gender standardization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Male", "Male"),
        ("male", "Male"),
        ("MALE", "Male"),
        ("M", "Male"),
        ("m", "Male"),
        ("Female", "Female"),
        ("female", "Female"),
        ("FEMALE", "Female"),
        ("F", "Female"),
        ("f", "Female"),
    ],
)
def test_gender_standardization_supported_values(raw, expected):
    value, supported = standardize_gender(raw)
    assert value == expected
    assert supported is True


def test_gender_standardization_unsupported_value():
    value, supported = standardize_gender("Other")
    assert value is None
    assert supported is False


def test_gender_standardization_blank_value():
    value, supported = standardize_gender(None)
    assert value is None
    assert supported is False


def test_gender_standardization_whitespace_and_case():
    value, supported = standardize_gender("  MaLe  ")
    assert value == "Male"
    assert supported is True


# ---------------------------------------------------------------------------
# Normalized comparison
# ---------------------------------------------------------------------------
def test_normalize_for_comparison_handles_none():
    assert normalize_for_comparison(None) == ""


def test_normalize_for_comparison_case_and_whitespace_insensitive():
    a = normalize_for_comparison("  Fictional   Person ")
    b = normalize_for_comparison("fictional person")
    assert a == b


# ---------------------------------------------------------------------------
# Sequential ID generation
# ---------------------------------------------------------------------------
def test_generate_sequential_ids_starts_at_one_and_has_no_gaps():
    df = pd.DataFrame(
        {
            "member_name": ["Charlie Fictional", "Alpha Fictional", "Bravo Fictional"],
            "source_row_number": [3, 1, 2],
        }
    )
    result = generate_sequential_ids(df)
    assert sorted(result["member_no"].tolist()) == [1, 2, 3]
    assert result["member_no"].min() == 1
    assert result["member_no"].is_unique
