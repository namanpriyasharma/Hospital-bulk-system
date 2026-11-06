"""Pydantic schemas and data transfer models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class HospitalRecordInput(BaseModel):
    """Parsed single record from uploaded CSV."""

    row: int = Field(..., description="1-indexed row number in the CSV file")
    name: str = Field(..., min_length=1, description="Hospital name")
    address: str = Field(..., min_length=1, description="Hospital address")
    phone: Optional[str] = Field(default=None, description="Optional phone number")


class HospitalResultItem(BaseModel):
    """Result status for an individual hospital in a batch."""

    row: int = Field(..., description="CSV row number")
    hospital_id: Optional[int] = Field(default=None, description="Hospital ID returned by API, if created")
    name: str = Field(..., description="Hospital name")
    status: str = Field(
        ...,
        description="Outcome status: 'created_and_activated', 'created_inactive', 'failed', etc.",
    )
    error: Optional[str] = Field(default=None, description="Error message if creation failed")


class BulkProcessingResponse(BaseModel):
    """Response returned upon bulk processing completion matching assignment specification."""

    batch_id: str = Field(..., description="Unique UUID for this processing batch")
    total_hospitals: int = Field(..., description="Total hospital records found in CSV")
    processed_hospitals: int = Field(..., description="Successfully created hospital records")
    failed_hospitals: int = Field(..., description="Number of records that failed creation")
    processing_time_seconds: float = Field(..., description="Total time taken to process the batch in seconds")
    batch_activated: bool = Field(..., description="Whether the batch activation was executed successfully")
    hospitals: List[HospitalResultItem] = Field(default_factory=list, description="Per-record result details")


class CSVValidationResult(BaseModel):
    """Result for pre-processing CSV validation endpoint (Bonus 6.4)."""

    valid: bool = Field(..., description="Whether the CSV conforms to all requirements")
    total_rows: int = Field(..., description="Number of valid data rows")
    max_allowed_rows: int = Field(..., description="Maximum allowed rows (20)")
    errors: List[str] = Field(default_factory=list, description="List of structural or semantic validation errors")
    preview: List[dict] = Field(default_factory=list, description="Preview of first few parsed records")


class BatchStatusResponse(BaseModel):
    """Real-time progress / status response for polling (Bonus 6.2)."""

    batch_id: str
    status: str = Field(..., description="'queued', 'processing', 'completed', 'failed', 'partially_failed'")
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    batch_activated: bool
    progress_percentage: float
    processing_time_seconds: Optional[float] = None
    hospitals: List[HospitalResultItem] = Field(default_factory=list)
