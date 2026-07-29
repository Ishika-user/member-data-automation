"""
Optional SQL Server loading module for the Automated Member Data Migration
and QA System.

This module is DISABLED BY DEFAULT. Loading only occurs when both:
  1. The --load-sql command-line flag is passed, AND
  2. The ALLOW_SQL_LOAD environment variable is set to "true"

No credentials are hard-coded. Connection details are read exclusively
from environment variables (see .env.example). Table drops/truncates are
never performed automatically. All inserts run inside a transaction with
rollback on failure.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger("member_data_automation.database")


class SqlLoadError(Exception):
    """Raised when SQL loading cannot proceed or fails."""


def is_sql_load_authorized(cli_flag_enabled: bool) -> bool:
    """
    Both the CLI flag and the environment variable must be enabled.
    This dual-control design prevents accidental production loads.
    """
    env_enabled = os.getenv("ALLOW_SQL_LOAD", "false").strip().lower() == "true"
    return cli_flag_enabled and env_enabled


def _validate_cleaned_data(df: pd.DataFrame) -> None:
    """Validate the cleaned DataFrame before attempting a database load."""
    required_columns = {"member_no", "member_name", "nepali_name", "gender"}
    if not required_columns.issubset(set(df.columns)):
        raise SqlLoadError(f"Cleaned data is missing required columns: {required_columns - set(df.columns)}")
    if df["member_no"].isna().any():
        raise SqlLoadError("Cleaned data contains null member_no values; aborting load.")
    if df["member_no"].duplicated().any():
        raise SqlLoadError("Cleaned data contains duplicate member_no values; aborting load.")
    if df["member_name"].isna().any() or (df["member_name"].astype(str).str.strip() == "").any():
        raise SqlLoadError("Cleaned data contains blank member_name values; aborting load.")


def load_to_sql_server(
    df: pd.DataFrame,
    cli_flag_enabled: bool,
    connection_string: Optional[str] = None,
    target_table: Optional[str] = None,
) -> dict:
    """
    Load the cleaned DataFrame into SQL Server inside a transaction.

    Returns a dict with aggregate results (row counts only - no raw data is
    logged). Raises SqlLoadError if authorization checks fail, validation
    fails, or the database operation fails (with rollback).
    """
    if not is_sql_load_authorized(cli_flag_enabled):
        raise SqlLoadError(
            "SQL loading is not authorized. Both --load-sql and ALLOW_SQL_LOAD=true are required."
        )

    connection_string = connection_string or os.getenv("SQL_CONNECTION_STRING", "")
    target_table = target_table or os.getenv("SQL_TARGET_TABLE", "Member")

    if not connection_string:
        raise SqlLoadError("SQL_CONNECTION_STRING is not set. Cannot connect without credentials.")

    _validate_cleaned_data(df)

    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SqlLoadError(f"SQLAlchemy is not available: {exc}") from exc

    engine = create_engine(connection_string)
    inserted_rows = 0

    try:
        with engine.begin() as connection:  # transaction: commits on success, rolls back on exception
            for _, row in df.iterrows():
                connection.execute(
                    text(
                        f"INSERT INTO {target_table} (member_no, member_name, nepali_name, gender) "
                        "VALUES (:member_no, :member_name, :nepali_name, :gender)"
                    ),
                    {
                        "member_no": row["member_no"],
                        "member_name": row["member_name"],
                        "nepali_name": row["nepali_name"],
                        "gender": row["gender"],
                    },
                )
                inserted_rows += 1

            verify_result = connection.execute(text(f"SELECT COUNT(*) FROM {target_table}"))
            total_rows_after = verify_result.scalar()

    except Exception as exc:  # noqa: BLE001
        logger.error("SQL load failed and was rolled back. Aggregate rows attempted: %d", len(df))
        raise SqlLoadError(f"SQL load failed and was rolled back: {exc}") from exc

    result = {
        "inserted_rows": inserted_rows,
        "target_table": target_table,
        "total_rows_after_load": total_rows_after,
    }
    logger.info(
        "SQL load complete. inserted_rows=%d target_table=%s total_rows_after=%s",
        inserted_rows,
        target_table,
        total_rows_after,
    )
    return result


# ---------------------------------------------------------------------------
# Guidance for safe manual testing (not executed automatically):
#
# 1. Stand up a local or development SQL Server instance (e.g. Docker image
#    mcr.microsoft.com/mssql/server).
# 2. Create a development-only database and a `Member` table with columns
#    matching (member_no, member_name, nepali_name, gender).
# 3. Copy .env.example to .env and fill in a connection string that points
#    ONLY at the development database.
# 4. Set ALLOW_SQL_LOAD=true in .env.
# 5. Run: python main.py --input <cleaned_file>.xlsx --mode sample --load-sql
# 6. Verify inserted_rows in the console/log output, then inspect the table
#    directly in the development database.
# 7. Never point this module at a production database without a full review.
# ---------------------------------------------------------------------------
