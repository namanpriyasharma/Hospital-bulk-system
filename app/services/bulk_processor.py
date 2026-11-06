"""Bulk processing orchestrator service."""

import asyncio
import time
import uuid
from typing import List, Optional

from app.config import settings
from app.models.batch import BatchRecord, batch_store
from app.models.schemas import (
    BulkProcessingResponse,
    HospitalRecordInput,
    HospitalResultItem,
)
from app.services.directory_client import (
    DirectoryAPIError,
    HospitalDirectoryClient,
    directory_client,
)
from app.services.progress_tracker import progress_tracker
from app.utils.logger import logger


class BulkProcessorService:
    """Coordinates asynchronous bulk ingestion, activation, and status tracking."""

    def __init__(self, client: Optional[HospitalDirectoryClient] = None):
        self.directory_client = client or directory_client

    async def process_bulk(
        self,
        records: List[HospitalRecordInput],
        batch_id: Optional[str] = None,
    ) -> BulkProcessingResponse:
        """
        Execute full bulk creation workflow:
        1. Generate UUID batch ID.
        2. Concurrently create records via Directory API POST /hospitals/.
        3. Activate batch via PATCH /hospitals/batch/{batch_id}/activate if all succeed.
        4. Return standardized processing results.
        """
        start_time = time.time()
        actual_batch_id = batch_id or str(uuid.uuid4())
        total = len(records)

        # Initialize batch record
        batch_rec = batch_store.get(actual_batch_id)
        if not batch_rec:
            batch_rec = BatchRecord(
                batch_id=actual_batch_id,
                total_hospitals=total,
                inputs=records,
                status="processing",
                start_time=start_time,
            )
            batch_store.save(batch_rec)
        else:
            batch_rec.status = "processing"

        logger.info(f"Starting bulk processing for batch_id={actual_batch_id} with {total} records.")

        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

        async def _process_single(record: HospitalRecordInput) -> HospitalResultItem:
            async with semaphore:
                try:
                    # Delegate entirely to the injectable directory_client (mockable in tests)
                    res = await self.directory_client.create_hospital(
                        name=record.name,
                        address=record.address,
                        phone=record.phone,
                        batch_id=actual_batch_id,
                    )
                    hospital_id = res.get("id")
                    result_item = HospitalResultItem(
                        row=record.row,
                        hospital_id=hospital_id,
                        name=record.name,
                        status="created_inactive",
                    )
                    batch_rec.processed_hospitals += 1
                except (DirectoryAPIError, Exception) as exc:
                    result_item = HospitalResultItem(
                        row=record.row,
                        hospital_id=None,
                        name=record.name,
                        status="failed",
                        error=str(exc),
                    )
                    batch_rec.failed_hospitals += 1

                # Broadcast per-item progress update via WebSocket
                await progress_tracker.broadcast(
                    actual_batch_id,
                    {
                        "event": "item_processed",
                        "row": record.row,
                        "name": record.name,
                        "status": result_item.status,
                        "progress": batch_rec.progress_percentage,
                    },
                )
                return result_item

        # Concurrently execute all hospital creations
        tasks = [_process_single(rec) for rec in records]
        results: List[HospitalResultItem] = await asyncio.gather(*tasks)

        # Sort results strictly by CSV row order
        results.sort(key=lambda r: r.row)
        batch_rec.results = results

        # Batch Activation: only if ALL hospitals created successfully
        batch_activated = False
        if batch_rec.failed_hospitals == 0 and batch_rec.processed_hospitals > 0:
            try:
                logger.info(f"Activating batch {actual_batch_id}...")
                await self.directory_client.activate_batch(actual_batch_id)
                batch_activated = True
                batch_rec.batch_activated = True
                batch_rec.status = "completed"
                # Update item statuses
                for item in batch_rec.results:
                    if item.status == "created_inactive":
                        item.status = "created_and_activated"
            except (DirectoryAPIError, Exception) as exc:
                logger.error(f"Batch activation failed for {actual_batch_id}: {exc}")
                batch_rec.status = "activation_failed"
        else:
            batch_rec.status = (
                "partially_failed" if batch_rec.processed_hospitals > 0 else "failed"
            )

        batch_rec.end_time = time.time()
        elapsed_time = round(batch_rec.end_time - start_time, 3)

        # Broadcast final completion event
        await progress_tracker.broadcast(
            actual_batch_id,
            {
                "event": "batch_completed",
                "batch_id": actual_batch_id,
                "status": batch_rec.status,
                "batch_activated": batch_activated,
                "total_hospitals": total,
                "processed_hospitals": batch_rec.processed_hospitals,
                "failed_hospitals": batch_rec.failed_hospitals,
                "processing_time_seconds": elapsed_time,
            },
        )

        return BulkProcessingResponse(
            batch_id=actual_batch_id,
            total_hospitals=batch_rec.total_hospitals,
            processed_hospitals=batch_rec.processed_hospitals,
            failed_hospitals=batch_rec.failed_hospitals,
            processing_time_seconds=elapsed_time,
            batch_activated=batch_activated,
            hospitals=batch_rec.results,
        )

    async def resume_batch(self, batch_id: str) -> BulkProcessingResponse:
        """
        Bonus 6.3: Resume capability.
        Retry failed hospital creations for an existing batch without restarting successful ones.
        """
        batch_rec = batch_store.get(batch_id)
        if not batch_rec:
            raise KeyError(f"Batch with ID '{batch_id}' not found.")

        # Find items that failed
        failed_rows = {item.row for item in batch_rec.results if item.status == "failed"}

        if not failed_rows:
            # Nothing failed — check if activation is still needed
            if not batch_rec.batch_activated and batch_rec.processed_hospitals == batch_rec.total_hospitals:
                try:
                    await self.directory_client.activate_batch(batch_id)
                    batch_rec.batch_activated = True
                    batch_rec.status = "completed"
                    for item in batch_rec.results:
                        item.status = "created_and_activated"
                except Exception as exc:
                    logger.error(f"Activation on resume failed: {exc}")

            return BulkProcessingResponse(
                batch_id=batch_rec.batch_id,
                total_hospitals=batch_rec.total_hospitals,
                processed_hospitals=batch_rec.processed_hospitals,
                failed_hospitals=batch_rec.failed_hospitals,
                processing_time_seconds=batch_rec.processing_time_seconds,
                batch_activated=batch_rec.batch_activated,
                hospitals=batch_rec.results,
            )

        records_to_retry = [rec for rec in batch_rec.inputs if rec.row in failed_rows]
        logger.info(f"Resuming batch {batch_id}: retrying {len(records_to_retry)} failed records.")

        for rec in records_to_retry:
            try:
                res = await self.directory_client.create_hospital(
                    name=rec.name,
                    address=rec.address,
                    phone=rec.phone,
                    batch_id=batch_id,
                )
                for item in batch_rec.results:
                    if item.row == rec.row:
                        item.hospital_id = res.get("id")
                        item.status = "created_inactive"
                        item.error = None
                batch_rec.processed_hospitals += 1
                batch_rec.failed_hospitals -= 1
            except Exception as exc:
                logger.warning(f"Retry failed for row {rec.row}: {exc}")

        # Activate if all records are now created
        if batch_rec.failed_hospitals == 0:
            try:
                await self.directory_client.activate_batch(batch_id)
                batch_rec.batch_activated = True
                batch_rec.status = "completed"
                for item in batch_rec.results:
                    if item.status == "created_inactive":
                        item.status = "created_and_activated"
            except Exception as exc:
                logger.error(f"Activation failed on resume for batch {batch_id}: {exc}")
                batch_rec.status = "activation_failed"

        return BulkProcessingResponse(
            batch_id=batch_rec.batch_id,
            total_hospitals=batch_rec.total_hospitals,
            processed_hospitals=batch_rec.processed_hospitals,
            failed_hospitals=batch_rec.failed_hospitals,
            processing_time_seconds=batch_rec.processing_time_seconds,
            batch_activated=batch_rec.batch_activated,
            hospitals=batch_rec.results,
        )


bulk_processor = BulkProcessorService()
