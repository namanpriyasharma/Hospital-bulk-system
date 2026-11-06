"""CSV validation and parsing service."""

import csv
import io
from typing import List, Tuple
from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.models.schemas import HospitalRecordInput, CSVValidationResult


class CSVValidationError(Exception):
    """Raised when CSV validation fails."""

    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]


def parse_and_validate_csv_content(content: str) -> Tuple[List[HospitalRecordInput], List[str]]:
    """
    Parse and validate CSV string content.
    Returns:
        Tuple of (valid_records, error_list)
    """
    errors: List[str] = []
    records: List[HospitalRecordInput] = []

    if not content or not content.strip():
        errors.append("CSV file is empty.")
        return records, errors

    # Use StringIO and DictReader
    stream = io.StringIO(content.strip())
    
    # Sniff or default delimiter
    sample = content[:1024]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    reader = csv.DictReader(stream, delimiter=delimiter)

    if not reader.fieldnames:
        errors.append("CSV does not contain any headers.")
        return records, errors

    # Normalize headers
    normalized_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    
    # Required columns: name, address
    if "name" not in normalized_headers:
        errors.append("Missing required CSV header: 'name'.")
    if "address" not in normalized_headers:
        errors.append("Missing required CSV header: 'address'.")

    if errors:
        return records, errors

    name_col = normalized_headers["name"]
    addr_col = normalized_headers["address"]
    phone_col = normalized_headers.get("phone")

    raw_rows = list(reader)

    # Check constraint: maximum 20 hospitals
    if len(raw_rows) > settings.MAX_CSV_RECORDS:
        errors.append(
            f"CSV contains {len(raw_rows)} records, which exceeds the maximum limit of {settings.MAX_CSV_RECORDS} hospitals."
        )

    if len(raw_rows) == 0:
        errors.append("CSV contains headers but no data rows.")
        return records, errors

    for idx, row in enumerate(raw_rows, start=1):
        name_val = (row.get(name_col) or "").strip()
        addr_val = (row.get(addr_col) or "").strip()
        phone_val = (row.get(phone_col) or "").strip() if phone_col else None
        
        # Phone is optional, but if empty string, normalize to None
        phone_clean = phone_val if (phone_val and phone_val.strip()) else None

        row_errors = []
        if not name_val:
            row_errors.append(f"Row {idx}: 'name' cannot be empty.")
        if not addr_val:
            row_errors.append(f"Row {idx}: 'address' cannot be empty.")

        if row_errors:
            errors.extend(row_errors)
        else:
            records.append(
                HospitalRecordInput(
                    row=idx,
                    name=name_val,
                    address=addr_val,
                    phone=phone_clean,
                )
            )

    return records, errors


async def read_and_validate_upload(file: UploadFile) -> List[HospitalRecordInput]:
    """
    Read uploaded file and validate CSV constraints.
    Raises HTTPException 400 if validation fails.
    """
    filename = file.filename or ""
    if not (filename.lower().endswith(".csv") or file.content_type in ("text/csv", "application/vnd.ms-excel", "text/plain")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format '{filename}'. Please upload a valid .csv file.",
        )

    try:
        raw_bytes = await file.read()
        # Support utf-8, with fallback to latin-1
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded file: {str(exc)}",
        )

    records, errors = parse_and_validate_csv_content(content)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "CSV validation failed.",
                "errors": errors,
            },
        )

    return records


def validate_csv_preview(content: str) -> CSVValidationResult:
    """Validate CSV and produce structured preview report (Bonus 6.4)."""
    records, errors = parse_and_validate_csv_content(content)
    preview_data = [
        {"row": r.row, "name": r.name, "address": r.address, "phone": r.phone}
        for r in records[:5]
    ]
    return CSVValidationResult(
        valid=len(errors) == 0,
        total_rows=len(records),
        max_allowed_rows=settings.MAX_CSV_RECORDS,
        errors=errors,
        preview=preview_data,
    )
