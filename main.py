"""
Automated Member Data Migration and QA System
Entry point: main.py

Usage:
    python main.py --input "data/private/source_member_data.xlsx" --mode private
    python main.py --generate-sample
    python main.py --input "data/sample/synthetic_member_data.xlsx" --mode sample
    python main.py --input "path/to/cleaned_file.xlsx" --mode private --load-sql
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config
from src.extract import ExtractionError, extract_members
from src.transform import process_dataframe
from src.validate import compute_file_checksum, overall_status, run_validations
from src.report import write_qa_report, write_simple_workbook
from src.sample_generator import generate_sample_workbook
from src.database import SqlLoadError, load_to_sql_server


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated Member Data Migration and QA System")
    parser.add_argument("--input", type=str, default=None, help="Path to the input Excel workbook.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=sorted(config.VALID_MODES),
        default=config.MODE_PRIVATE,
        help="Execution mode: private or sample.",
    )
    parser.add_argument(
        "--generate-sample", action="store_true", help="Generate the synthetic public demonstration dataset."
    )
    parser.add_argument(
        "--load-sql", action="store_true", help="Attempt SQL Server load (also requires ALLOW_SQL_LOAD=true)."
    )
    return parser


def configure_logging(mode: str) -> logging.Logger:
    config.ensure_directories()
    log_dir = config.PRIVATE_OUTPUT_DIR if mode == config.MODE_PRIVATE else config.SAMPLE_OUTPUT_DIR
    log_path = log_dir / config.LOG_FILENAME if mode == config.MODE_PRIVATE else log_dir / "automation_sample.log"

    logger = logging.getLogger("member_data_automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding=config.LOG_ENCODING)
    file_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    logger.addHandler(stream_handler)

    return logger


def build_summary_rows(stats: dict, reconciliation_ok: bool, overall_qa_status: str, mode: str) -> list:
    baseline = config.PRIVATE_BASELINE_CLEANED_COUNT if mode == config.MODE_PRIVATE else None
    difference = (stats["cleaned_record_count"] - baseline) if baseline is not None else "N/A"
    rows = [
        {"Metric": "Raw record count", "Value": stats["raw_record_count"]},
        {"Metric": "Valid member-number count", "Value": stats["valid_member_number_count"]},
        {"Metric": "Invalid member-number count", "Value": stats["invalid_member_number_count"]},
        {"Metric": "Missing member-number count", "Value": stats["missing_member_number_count"]},
        {"Metric": "Missing member-name count", "Value": stats["missing_member_name_count"]},
        {"Metric": "Missing Nepali-name count", "Value": stats["missing_nepali_name_count"]},
        {"Metric": "Missing gender count", "Value": stats["missing_gender_count"]},
        {"Metric": "Unsupported gender count", "Value": stats["unsupported_gender_count"]},
        {"Metric": "Exact duplicate rows removed", "Value": stats["exact_duplicate_rows_removed"]},
        {"Metric": "Same-name duplicate rows removed", "Value": stats["same_name_duplicate_rows_removed"]},
        {"Metric": "Repeated member-number groups", "Value": stats["repeated_member_number_groups"]},
        {"Metric": "Conflicting member-number groups", "Value": stats["conflicting_member_number_groups"]},
        {"Metric": "Manual-review record count", "Value": stats["manual_review_record_count"]},
        {"Metric": "Cleaned record count", "Value": stats["cleaned_record_count"]},
        {"Metric": "Male count", "Value": stats["male_count"]},
        {"Metric": "Female count", "Value": stats["female_count"]},
        {"Metric": "Null/not-applicable gender count", "Value": stats["null_gender_count"]},
    ]
    if mode == config.MODE_PRIVATE:
        rows.append({"Metric": "Previous private baseline count", "Value": "[PRIVATE - see internal notes]"})
        rows.append({"Metric": "Difference from private baseline", "Value": "[PRIVATE - see internal notes]"})
    rows.append({"Metric": "Reconciliation status", "Value": "OK" if reconciliation_ok else "MISMATCH"})
    rows.append({"Metric": "Overall QA status", "Value": overall_qa_status})
    return rows


def run_pipeline(input_path: Path, mode: str, logger: logging.Logger) -> dict:
    run_id = str(uuid.uuid4())
    start_time = datetime.now()
    logger.info("Run started. run_id=%s mode=%s", run_id, mode)

    checksum_before = compute_file_checksum(input_path)

    try:
        raw_df, extraction_meta = extract_members(input_path, logger=logger)
    except ExtractionError as exc:
        logger.error("Extraction failed: %s", exc)
        raise

    logger.info(
        "Extraction complete. selected_sheet=%s input_row_count=%d",
        extraction_meta.selected_sheet_label,
        extraction_meta.input_row_count,
    )
    logger.info("Column mapping resolved for all four required fields.")

    result = process_dataframe(raw_df)
    stats = result["stats"]
    cleaned_df = result["cleaned"]
    manual_review_df = result["manual_review"]
    duplicate_details = result["duplicate_details"]

    logger.info(
        "Cleaning complete. cleaned=%d manual_review=%d duplicates_removed=%d",
        stats["cleaned_record_count"],
        stats["manual_review_record_count"],
        stats["total_duplicate_rows_removed"],
    )

    # Determine output directory and filenames based on mode
    if mode == config.MODE_PRIVATE:
        out_dir = config.PRIVATE_OUTPUT_DIR
        cleaned_filename = config.CLEANED_MEMBERS_FILENAME
        review_filename = config.MANUAL_REVIEW_FILENAME
        qa_filename = config.QA_REPORT_FILENAME
    else:
        out_dir = config.SAMPLE_OUTPUT_DIR
        cleaned_filename = config.CLEANED_MEMBERS_SAMPLE_FILENAME
        review_filename = config.MANUAL_REVIEW_SAMPLE_FILENAME
        qa_filename = config.QA_REPORT_SAMPLE_FILENAME

    out_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = out_dir / cleaned_filename
    review_path = out_dir / review_filename
    qa_path = out_dir / qa_filename

    write_simple_workbook(cleaned_df, cleaned_path, sheet_title="Cleaned Members")
    write_simple_workbook(manual_review_df, review_path, sheet_title="Manual Review")

    output_files_exist = cleaned_path.exists() and review_path.exists()

    checksum_after = compute_file_checksum(input_path)

    validation_results = run_validations(
        cleaned_df=cleaned_df,
        manual_review_df=manual_review_df,
        stats=stats,
        column_mapping_complete=True,
        checksum_before=checksum_before,
        checksum_after=checksum_after,
        output_files_exist=output_files_exist,
    )
    qa_status = overall_status(validation_results)
    reconciliation_ok = any(
        r["rule"].startswith("Reconciliation formula") and r["passed"] == "Passed" for r in validation_results
    )

    summary_rows = build_summary_rows(stats, reconciliation_ok, qa_status, mode)

    missing_values_rows = [
        {"Field": "original_member_no", "Missing Count": stats["missing_member_number_count"]},
        {"Field": "member_name", "Missing Count": stats["missing_member_name_count"]},
        {"Field": "nepali_name", "Missing Count": stats["missing_nepali_name_count"]},
        {"Field": "gender", "Missing Count": stats["missing_gender_count"]},
    ]

    duplicate_summary_rows = [
        {"Duplicate Type": "Exact duplicates removed", "Count": stats["exact_duplicate_rows_removed"]},
        {"Duplicate Type": "Same member number/name duplicates removed", "Count": stats["same_name_duplicate_rows_removed"]},
        {"Duplicate Type": "Repeated member-number groups", "Count": stats["repeated_member_number_groups"]},
        {"Duplicate Type": "Conflicting member-number groups", "Count": stats["conflicting_member_number_groups"]},
    ]

    total_gender = stats["male_count"] + stats["female_count"] + stats["null_gender_count"]
    def pct(n):
        return f"{(n / total_gender * 100):.1f}%" if total_gender else "0.0%"

    gender_distribution_rows = [
        {"Gender": "Male", "Count": stats["male_count"], "Percentage": pct(stats["male_count"])},
        {"Gender": "Female", "Count": stats["female_count"], "Percentage": pct(stats["female_count"])},
        {"Gender": "Null/Not Applicable", "Count": stats["null_gender_count"], "Percentage": pct(stats["null_gender_count"])},
    ]

    completion_time = datetime.now()
    run_metadata_rows = [
        {"Field": "Project Name", "Value": "Automated Member Data Migration and QA System"},
        {"Field": "Run ID", "Value": run_id},
        {"Field": "Start Time", "Value": start_time.isoformat(timespec="seconds")},
        {"Field": "Completion Time", "Value": completion_time.isoformat(timespec="seconds")},
        {"Field": "Execution Mode", "Value": mode},
        {"Field": "Input Label", "Value": "source_member_data.xlsx" if mode == config.MODE_PRIVATE else "synthetic_member_data.xlsx"},
        {"Field": "Selected Sheet", "Value": extraction_meta.selected_sheet_label},
        {"Field": "Python Version", "Value": sys.version.split()[0]},
        {"Field": "Pandas Version", "Value": pd.__version__},
        {"Field": "Cleaned Output Location", "Value": str(cleaned_path)},
        {"Field": "Manual Review Output Location", "Value": str(review_path)},
        {"Field": "QA Report Output Location", "Value": str(qa_path)},
    ]

    write_qa_report(
        qa_path,
        summary_rows,
        missing_values_rows,
        duplicate_summary_rows,
        duplicate_details,
        gender_distribution_rows,
        validation_results,
        run_metadata_rows,
    )

    logger.info("QA report written. status=%s", qa_status)
    logger.info(
        "Reconciliation check: raw=%d cleaned=%d manual_review=%d duplicates_removed=%d",
        stats["raw_record_count"],
        stats["cleaned_record_count"],
        stats["manual_review_record_count"],
        stats["total_duplicate_rows_removed"],
    )
    logger.info("Checksum before=%s after=%s unchanged=%s", checksum_before, checksum_after, checksum_before == checksum_after)
    logger.info("Run completed. run_id=%s", run_id)

    return {
        "stats": stats,
        "qa_status": qa_status,
        "cleaned_path": cleaned_path,
        "review_path": review_path,
        "qa_path": qa_path,
        "validation_results": validation_results,
        "cleaned_df": cleaned_df,
    }


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    config.ensure_directories()

    if args.generate_sample:
        path = generate_sample_workbook()
        print(f"Synthetic sample dataset generated at: {path}")
        if not args.input:
            return 0

    if not args.input:
        print("Error: --input is required unless only --generate-sample is used.")
        return 2

    input_path = Path(args.input)
    logger = configure_logging(args.mode)

    try:
        outcome = run_pipeline(input_path, args.mode, logger)
    except ExtractionError as exc:
        print(f"Extraction failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected processing failure: %s", exc)
        print(f"Unexpected processing failure: {exc}")
        return 1

    print("\n=== Safe Aggregate Summary ===")
    stats = outcome["stats"]
    print(f"Raw records:            {stats['raw_record_count']}")
    print(f"Cleaned records:        {stats['cleaned_record_count']}")
    print(f"Manual review records:  {stats['manual_review_record_count']}")
    print(f"Duplicates removed:     {stats['total_duplicate_rows_removed']}")
    print(f"Overall QA status:      {outcome['qa_status']}")

    if args.load_sql:
        try:
            sql_result = load_to_sql_server(outcome["cleaned_df"], cli_flag_enabled=True)
            print(f"SQL load result (aggregate): {sql_result}")
        except SqlLoadError as exc:
            print(f"SQL load not performed: {exc}")

    if outcome["qa_status"] == "FAILED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
