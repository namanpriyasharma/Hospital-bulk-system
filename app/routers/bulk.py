"""Bulk operations router."""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.schemas import BulkProcessingResponse, CSVValidationResult
from app.services.bulk_processor import bulk_processor
from app.services.csv_validator import read_and_validate_upload, validate_csv_preview
from app.utils.logger import logger

router = APIRouter(prefix="/hospitals/bulk", tags=["Bulk Hospital Operations"])


@router.post(
    "",
    response_model=BulkProcessingResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk Create Hospitals",
    description=(
        "Upload a CSV file containing hospital records (max 20). "
        "Generates a unique batch ID, concurrently creates each hospital, "
        "and activates the entire batch upon successful creation."
    ),
)
async def bulk_create_hospitals(
    file: UploadFile = File(..., description="CSV file with columns: name,address,phone"),
) -> BulkProcessingResponse:
    """Core endpoint: POST /hospitals/bulk."""
    logger.info(f"Received bulk upload request with filename: {file.filename}")
    records = await read_and_validate_upload(file)
    response = await bulk_processor.process_bulk(records)
    return response


@router.post(
    "/validate",
    response_model=CSVValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Validate CSV Structure (Bonus 6.4)",
    description="Validate CSV structure, column headers, and row count limit (<=20) before processing.",
)
async def validate_csv_file(
    file: UploadFile = File(..., description="CSV file to validate"),
) -> CSVValidationResult:
    """Bonus 6.4: Separate validation endpoint."""
    try:
        raw_bytes = await file.read()
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read file: {str(exc)}",
        )

    return validate_csv_preview(content)


@router.post(
    "/{batch_id}/resume",
    response_model=BulkProcessingResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume Failed Bulk Operation (Bonus 6.3)",
    description="Re-attempts creation of any failed hospital records for an existing batch ID without re-creating succeeded ones.",
)
async def resume_bulk_operation(batch_id: str) -> BulkProcessingResponse:
    """Bonus 6.3: Resume failed batch."""
    try:
        return await bulk_processor.resume_batch(batch_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch ID '{batch_id}' was not found in storage.",
        )
