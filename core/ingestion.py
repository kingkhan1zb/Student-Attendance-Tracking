"""
Data ingestion: reads CSV / XLSX files and returns validated StudentRecord objects.
"""

from __future__ import annotations

import io
import logging
from typing import List, Tuple

import pandas as pd

from core.models import StudentRecord

logger = logging.getLogger(__name__)

# ── Column aliases ─────────────────────────────────────────────────────────────
# Maps common column name variations → canonical internal name.
COLUMN_ALIASES: dict[str, str] = {
    # Student Name
    "student name": "Student Name",
    "name": "Student Name",
    "student": "Student Name",
    "full name": "Student Name",
    # Roll Number
    "roll number": "Roll Number",
    "roll no": "Roll Number",
    "roll no.": "Roll Number",
    "rollno": "Roll Number",
    "id": "Roll Number",
    "student id": "Roll Number",
    # Total Classes Held
    "total classes held": "Total Classes Held",
    "total classes": "Total Classes Held",
    "classes held": "Total Classes Held",
    "total": "Total Classes Held",
    # Classes Attended
    "classes attended": "Classes Attended",
    "attended": "Classes Attended",
    "present": "Classes Attended",
    "attendance": "Classes Attended",
}

REQUIRED_COLUMNS = {"Student Name", "Roll Number", "Total Classes Held", "Classes Attended"}


class DataIngestionError(Exception):
    """Raised when the input file cannot be read or parsed."""


class ColumnMappingError(DataIngestionError):
    """Raised when required columns are missing after alias resolution."""


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename DataFrame columns using COLUMN_ALIASES.

    Args:
        df: Raw DataFrame from file read.

    Returns:
        DataFrame with canonical column names.

    Raises:
        ColumnMappingError: If any required column cannot be resolved.
    """
    renamed = {
        col: COLUMN_ALIASES.get(col.strip().lower(), col.strip())
        for col in df.columns
    }
    df = df.rename(columns=renamed)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ColumnMappingError(
            f"Missing required column(s): {', '.join(sorted(missing))}.\n"
            f"Found columns: {', '.join(df.columns.tolist())}.\n"
            "Please ensure your file has: Student Name, Roll Number, "
            "Total Classes Held, Classes Attended."
        )
    return df


def _read_file(file_source: str | bytes | io.BytesIO, filename: str) -> pd.DataFrame:
    """
    Read a CSV or XLSX file into a DataFrame.

    Args:
        file_source: File path string, raw bytes, or BytesIO buffer.
        filename: Original filename (used for extension detection).

    Returns:
        Raw pandas DataFrame.

    Raises:
        DataIngestionError: On unrecognised format or parse failure.
    """
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        if ext == "csv":
            if isinstance(file_source, (bytes, io.BytesIO)):
                buf = io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source
                return pd.read_csv(buf, dtype=str, skipinitialspace=True)
            return pd.read_csv(file_source, dtype=str, skipinitialspace=True)

        elif ext in ("xlsx", "xls"):
            if isinstance(file_source, (bytes, io.BytesIO)):
                buf = io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source
                return pd.read_excel(buf, dtype=str)
            return pd.read_excel(file_source, dtype=str)

        else:
            raise DataIngestionError(
                f"Unsupported file format '.{ext}'. Please upload a .csv or .xlsx file."
            )
    except DataIngestionError:
        raise
    except Exception as exc:
        raise DataIngestionError(f"Failed to parse '{filename}': {exc}") from exc


def _coerce_numeric(df: pd.DataFrame, row_idx: int, col: str) -> int:
    """
    Safely coerce a DataFrame cell to int.

    Args:
        df: The DataFrame.
        row_idx: Row index.
        col: Column name.

    Returns:
        Integer value.

    Raises:
        ValueError: On non-numeric or negative input.
    """
    raw = str(df.at[row_idx, col]).strip()
    try:
        value = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"'{col}' has non-numeric value '{raw}'")
    if value != int(value):
        logger.warning("Row %d: '%s' value %.2f will be rounded to %d.", row_idx, col, value, int(value))
    return int(value)


def parse_file(
    file_source: str | bytes | io.BytesIO,
    filename: str,
    threshold: float = 75.0,
) -> Tuple[List[StudentRecord], List[str]]:
    """
    Parse an attendance file and return student records with any warnings.

    Args:
        file_source: Path, bytes, or BytesIO of the input file.
        filename: Original filename for format detection.
        threshold: Attendance percentage threshold (0–100).

    Returns:
        Tuple of (list of StudentRecord, list of warning strings).

    Raises:
        DataIngestionError: On file read / column mapping errors.
    """
    df = _read_file(file_source, filename)
    df = _normalise_columns(df)

    # Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    records: List[StudentRecord] = []
    warnings: List[str] = []

    for idx in range(len(df)):
        row_label = f"Row {idx + 2}"  # +2 for header + 1-based

        name_raw = str(df.at[idx, "Student Name"]).strip()
        roll_raw = str(df.at[idx, "Roll Number"]).strip()

        # Skip rows where name or roll is missing/NaN
        if name_raw in ("", "nan", "NaN", "None"):
            warnings.append(f"{row_label}: Skipped — 'Student Name' is empty.")
            continue
        if roll_raw in ("", "nan", "NaN", "None"):
            warnings.append(f"{row_label}: Skipped — 'Roll Number' is empty for '{name_raw}'.")
            continue

        try:
            total = _coerce_numeric(df, idx, "Total Classes Held")
            attended = _coerce_numeric(df, idx, "Classes Attended")
        except ValueError as exc:
            warnings.append(f"{row_label} ('{name_raw}'): Skipped — {exc}.")
            continue

        if total == 0:
            warnings.append(
                f"{row_label} ('{name_raw}'): Total Classes is 0; attendance set to 0%."
            )

        try:
            record = StudentRecord(
                name=name_raw,
                roll_number=roll_raw,
                total_classes=total,
                classes_attended=attended,
                threshold=threshold,
            )
        except ValueError as exc:
            warnings.append(f"{row_label} ('{name_raw}'): Skipped — {exc}.")
            continue

        records.append(record)

    if not records:
        raise DataIngestionError("No valid student records found in the uploaded file.")

    logger.info("Parsed %d records with %d warnings.", len(records), len(warnings))
    return records, warnings
