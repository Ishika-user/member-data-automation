"""
Transformation module for the Automated Member Data Migration and QA System.

Contains small, independently testable functions for text cleaning,
member-number cleaning, gender standardization, missing-data detection,
duplicate resolution, and final sequential ID generation.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from src.config import ALLOWED_GENDER_VALUES

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------
GENDER_MAP = {
    "male": "Male",
    "m": "Male",
    "female": "Female",
    "f": "Female",
}


def clean_text(value: object) -> Optional[str]:
    """
    Safely convert a value to a cleaned string.
    - None / NaN -> None (never the literal string 'nan')
    - Trims leading/trailing whitespace
    - Collapses repeated internal whitespace to a single space
    - Empty / whitespace-only -> None
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    if text == "":
        return None
    return text


def clean_member_name(value: object) -> Optional[str]:
    """Clean an English member name (whitespace only, preserve punctuation/case)."""
    return clean_text(value)


def clean_nepali_name(value: object) -> Optional[str]:
    """Clean a Nepali name while preserving Unicode exactly (no transliteration)."""
    return clean_text(value)


def clean_member_number(value: object) -> "tuple[Optional[int], bool, Optional[str]]":
    """
    Clean and validate a member number.

    Returns (numeric_value_or_None, is_valid, leading_zero_audit_or_None).

    Rules:
    - Missing -> invalid
    - Non-numeric -> invalid
    - Fractional (non-integer) -> invalid
    - Preserves leading-zero text in an audit note when applicable
    """
    if value is None:
        return None, False, None
    if isinstance(value, float) and pd.isna(value):
        return None, False, None

    if isinstance(value, bool):
        return None, False, None

    leading_zero_audit = None

    if isinstance(value, int):
        return value, True, None

    if isinstance(value, float):
        if value.is_integer():
            return int(value), True, None
        return None, False, None

    text = str(value).strip()
    if text == "":
        return None, False, None

    if not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None, False, None

    if "." in text:
        whole, frac = text.split(".", 1)
        if frac.strip("0") != "":
            return None, False, None
        text_int = whole
    else:
        text_int = text

    if text_int.startswith("0") and len(text_int) > 1:
        leading_zero_audit = text_int

    try:
        numeric = int(text_int)
    except ValueError:
        return None, False, None

    if numeric < 0:
        return None, False, None

    return numeric, True, leading_zero_audit


def standardize_gender(value: object) -> "tuple[Optional[str], bool]":
    """
    Standardize a gender value.

    Returns (standardized_value_or_None, was_supported).
    Unsupported or blank values map to (None, False) and must be preserved
    in the audit trail by the caller using the original value.
    """
    cleaned = clean_text(value)
    if cleaned is None:
        return None, False
    key = cleaned.lower()
    if key in GENDER_MAP:
        return GENDER_MAP[key], True
    return None, False


# ---------------------------------------------------------------------------
# Normalized comparison keys (used internally, not for display)
# ---------------------------------------------------------------------------
def normalize_for_comparison(value: Optional[str]) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def completeness_score(row: pd.Series) -> int:
    """Higher score = more complete record (used to select the best duplicate)."""
    score = 0
    if pd.notna(row.get("nepali_name")) and str(row.get("nepali_name")).strip() != "":
        score += 1
    if row.get("gender") in ALLOWED_GENDER_VALUES:
        score += 1
    if pd.notna(row.get("member_name")) and str(row.get("member_name")).strip() != "":
        score += 1
    return score


def generate_sequential_ids(df: pd.DataFrame, sort_columns=None) -> pd.DataFrame:
    """
    Assign a new sequential member_no starting at 1, incrementing by 1,
    with no gaps, based on deterministic sort order.
    """
    if sort_columns is None:
        sort_columns = ["member_name", "source_row_number"]
    sort_columns = [c for c in sort_columns if c in df.columns]
    sorted_df = df.sort_values(by=sort_columns, kind="mergesort").reset_index(drop=True)
    sorted_df["member_no"] = range(1, len(sorted_df) + 1)
    return sorted_df


# ---------------------------------------------------------------------------
# Full pipeline orchestration
# ---------------------------------------------------------------------------
def process_dataframe(raw_df: pd.DataFrame) -> dict:
    """
    Run the complete cleaning, validation, and duplicate-resolution pipeline
    on an extracted raw DataFrame.

    Returns a dict with keys:
        cleaned            -> final migration-ready DataFrame
        manual_review      -> DataFrame of records needing human review
        duplicate_details  -> list of dicts describing duplicate/conflict actions
        stats              -> dict of aggregate counters for the QA report
    """
    df = raw_df.copy()

    # --- Step 1: field-level cleaning -------------------------------------------------
    df["member_name_clean"] = df["member_name"].apply(clean_member_name)
    df["nepali_name_clean"] = df["nepali_name"].apply(clean_nepali_name)

    member_no_results = df["original_member_no"].apply(clean_member_number)
    df["member_no_numeric"] = member_no_results.apply(lambda t: t[0])
    df["member_no_valid"] = member_no_results.apply(lambda t: t[1])
    df["member_no_leading_zero_audit"] = member_no_results.apply(lambda t: t[2])

    gender_results = df["gender"].apply(standardize_gender)
    df["gender_std"] = gender_results.apply(lambda t: t[0])
    df["gender_supported"] = gender_results.apply(lambda t: t[1])
    df["original_gender_value"] = df["gender"]

    # --- Step 2: missing / invalid detection -------------------------------------------
    missing_member_no_count = int(df["original_member_no"].isna().sum())
    invalid_member_no_count = int(
        ((~df["member_no_valid"]) & (df["original_member_no"].notna())).sum()
    )
    missing_member_name_count = int(df["member_name_clean"].isna().sum())
    missing_nepali_name_count = int(df["nepali_name_clean"].isna().sum())
    missing_gender_count = int(df["gender"].apply(clean_text).isna().sum())
    unsupported_gender_count = int(
        ((~df["gender_supported"]) & (df["gender"].apply(clean_text).notna())).sum()
    )

    def build_review_reasons(row) -> list:
        reasons = []
        if pd.isna(row["original_member_no"]):
            reasons.append("Missing original member number")
        elif not row["member_no_valid"]:
            reasons.append("Invalid original member number")
        if pd.isna(row["member_name_clean"]):
            reasons.append("Missing member name")
        return reasons

    df["base_review_reasons"] = df.apply(build_review_reasons, axis=1)
    df["needs_base_review"] = df["base_review_reasons"].apply(lambda r: len(r) > 0)

    base_invalid_df = df[df["needs_base_review"]].copy()
    candidate_df = df[~df["needs_base_review"]].copy()

    # --- Step 3: group by valid original member number for duplicate/conflict handling --
    duplicate_details: list = []
    conflict_row_indices = set()
    exact_duplicate_removed_indices = set()
    same_number_duplicate_removed_indices = set()
    kept_indices = []

    groups = candidate_df.groupby("member_no_numeric")
    repeated_member_number_groups = 0
    conflicting_member_number_groups = 0

    for member_no, group in groups:
        if len(group) == 1:
            kept_indices.append(group.index[0])
            continue

        repeated_member_number_groups += 1
        normalized_names = group["member_name_clean"].apply(normalize_for_comparison)
        distinct_names = normalized_names.unique()

        if len(distinct_names) > 1:
            # Conflicting names for the same member number -> entire group to review
            conflicting_member_number_groups += 1
            for idx in group.index:
                conflict_row_indices.add(idx)
                duplicate_details.append(
                    {
                        "duplicate_type": "Conflicting member number",
                        "original_member_no": member_no,
                        "source_row_number": df.loc[idx, "source_row_number"],
                        "status": "Excluded - Manual Review",
                        "reason": "Conflicting names for the same member number",
                    }
                )
            continue

        # Same member number, same normalized name.
        # Determine if rows are fully identical (exact duplicate) or merely
        # share number+name but differ in other fields (same-name duplicate).
        normalized_full = group.apply(
            lambda r: (
                normalize_for_comparison(r["member_name_clean"]),
                normalize_for_comparison(r["nepali_name_clean"]),
                normalize_for_comparison(r["gender_std"]),
            ),
            axis=1,
        )
        is_exact = normalized_full.nunique() == 1

        scored = group.copy()
        scored["completeness"] = scored.apply(completeness_score, axis=1)
        scored = scored.sort_values(
            by=["completeness", "source_row_number"], ascending=[False, True]
        )
        selected_idx = scored.index[0]
        removed_idx = list(scored.index[1:])

        kept_indices.append(selected_idx)

        duplicate_type = "Exact duplicate" if is_exact else "Same member number, same name"
        for idx in removed_idx:
            if is_exact:
                exact_duplicate_removed_indices.add(idx)
            else:
                same_number_duplicate_removed_indices.add(idx)
            duplicate_details.append(
                {
                    "duplicate_type": duplicate_type,
                    "original_member_no": member_no,
                    "source_row_number": df.loc[idx, "source_row_number"],
                    "status": "Excluded - Duplicate",
                    "reason": f"Duplicate of source row {df.loc[selected_idx, 'source_row_number']}",
                }
            )
        duplicate_details.append(
            {
                "duplicate_type": duplicate_type,
                "original_member_no": member_no,
                "source_row_number": df.loc[selected_idx, "source_row_number"],
                "status": "Selected",
                "reason": "Most complete record retained",
            }
        )

    exact_duplicate_rows_removed = len(exact_duplicate_removed_indices)
    same_name_duplicate_rows_removed = len(same_number_duplicate_removed_indices)
    total_duplicate_rows_removed = exact_duplicate_rows_removed + same_name_duplicate_rows_removed

    # --- Step 4: assemble manual review dataset -----------------------------------------
    review_frames = []

    if len(base_invalid_df) > 0:
        review_frames.append(
            base_invalid_df.assign(review_reason=base_invalid_df["base_review_reasons"].apply(
                lambda r: "; ".join(r)
            ))
        )

    if conflict_row_indices:
        conflict_df = df.loc[sorted(conflict_row_indices)].copy()
        conflict_df["review_reason"] = "Conflicting names for the same member number"
        review_frames.append(conflict_df)

    if review_frames:
        manual_review_df = pd.concat(review_frames, axis=0)
    else:
        manual_review_df = df.iloc[0:0].copy()
        manual_review_df["review_reason"] = []

    manual_review_output = pd.DataFrame(
        {
            "source_row_number": manual_review_df["source_row_number"].values,
            "original_member_no": manual_review_df["original_member_no"].values,
            "member_name": manual_review_df["member_name_clean"].values,
            "nepali_name": manual_review_df["nepali_name_clean"].values,
            "original_gender": manual_review_df["original_gender_value"].values,
            "standardized_gender": manual_review_df["gender_std"].values,
            "review_reason": manual_review_df["review_reason"].values,
        }
    ).sort_values(by="source_row_number").reset_index(drop=True)

    # --- Step 5: assemble cleaned candidate dataset and assign sequential IDs -----------
    final_candidates = df.loc[kept_indices].copy()
    final_candidates["member_name"] = final_candidates["member_name_clean"]
    final_candidates["nepali_name"] = final_candidates["nepali_name_clean"]
    final_candidates["gender"] = final_candidates["gender_std"]

    final_with_ids = generate_sequential_ids(
        final_candidates, sort_columns=["member_name", "source_row_number"]
    )
    cleaned_output = final_with_ids[["member_no", "member_name", "nepali_name", "gender"]].copy()

    male_count = int((cleaned_output["gender"] == "Male").sum())
    female_count = int((cleaned_output["gender"] == "Female").sum())
    null_gender_count = int(cleaned_output["gender"].isna().sum())

    stats = {
        "raw_record_count": int(len(df)),
        "valid_member_number_count": int(df["member_no_valid"].sum()),
        "invalid_member_number_count": invalid_member_no_count,
        "missing_member_number_count": missing_member_no_count,
        "missing_member_name_count": missing_member_name_count,
        "missing_nepali_name_count": missing_nepali_name_count,
        "missing_gender_count": missing_gender_count,
        "unsupported_gender_count": unsupported_gender_count,
        "exact_duplicate_rows_removed": exact_duplicate_rows_removed,
        "same_name_duplicate_rows_removed": same_name_duplicate_rows_removed,
        "total_duplicate_rows_removed": total_duplicate_rows_removed,
        "repeated_member_number_groups": repeated_member_number_groups,
        "conflicting_member_number_groups": conflicting_member_number_groups,
        "manual_review_record_count": int(len(manual_review_output)),
        "cleaned_record_count": int(len(cleaned_output)),
        "male_count": male_count,
        "female_count": female_count,
        "null_gender_count": null_gender_count,
    }

    return {
        "cleaned": cleaned_output,
        "manual_review": manual_review_output,
        "duplicate_details": duplicate_details,
        "stats": stats,
    }
