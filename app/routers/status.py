"""Batch status and progress monitoring router."""

from typing import List
from fastapi import APIRouter, HTTPException, status

from app.models.batch import batch_store
from app.models.schemas import BatchStatusResponse

router = APIRouter(prefix="/hospitals/bulk", tags=["Progress & Status"])


@router.get(
    "/{batch_id}/status",
    response_model=BatchStatusResponse,
    summary="Get Batch Status & Progress (Bonus 6.2 Polling)",
    description="Polling endpoint to monitor real-time progress, counts, and status of a batch.",
)
async def get_batch_status(batch_id: str) -> BatchStatusResponse:
    """Retrieve status and progress for a batch."""
    batch_rec = batch_store.get(batch_id)
    if not batch_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    return batch_rec.to_status_response()


@router.get(
    "/batches",
    response_model=List[BatchStatusResponse],
    summary="List All Batches",
    description="Retrieve all tracked batches and their current statuses.",
)
async def list_batches() -> List[BatchStatusResponse]:
    """List all tracked batches in the system."""
    return [b.to_status_response() for b in batch_store.list_all()]
