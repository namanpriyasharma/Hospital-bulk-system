"""In-memory thread-safe batch job storage."""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.models.schemas import HospitalRecordInput, HospitalResultItem, BatchStatusResponse


@dataclass
class BatchRecord:
    """Internal model for tracking a batch lifecycle."""

    batch_id: str
    total_hospitals: int
    inputs: List[HospitalRecordInput]
    processed_hospitals: int = 0
    failed_hospitals: int = 0
    batch_activated: bool = False
    status: str = "queued"  # queued, processing, completed, failed, partially_failed
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    results: List[HospitalResultItem] = field(default_factory=list)

    @property
    def processing_time_seconds(self) -> float:
        """Calculate elapsed or total processing time."""
        if self.end_time is not None:
            return round(self.end_time - self.start_time, 3)
        return round(time.time() - self.start_time, 3)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage [0.0 - 100.0]."""
        if self.total_hospitals == 0:
            return 100.0
        completed = self.processed_hospitals + self.failed_hospitals
        return round((completed / self.total_hospitals) * 100.0, 1)

    def to_status_response(self) -> BatchStatusResponse:
        """Convert to public schema response."""
        return BatchStatusResponse(
            batch_id=self.batch_id,
            status=self.status,
            total_hospitals=self.total_hospitals,
            processed_hospitals=self.processed_hospitals,
            failed_hospitals=self.failed_hospitals,
            batch_activated=self.batch_activated,
            progress_percentage=self.progress_percentage,
            processing_time_seconds=self.processing_time_seconds,
            hospitals=self.results,
        )


class BatchStore:
    """Singleton in-memory registry of all batches."""

    def __init__(self) -> None:
        self._batches: Dict[str, BatchRecord] = {}

    def save(self, record: BatchRecord) -> None:
        """Save or update batch record."""
        self._batches[record.batch_id] = record

    def get(self, batch_id: str) -> Optional[BatchRecord]:
        """Retrieve batch record by UUID string."""
        return self._batches.get(batch_id)

    def list_all(self) -> List[BatchRecord]:
        """List all tracked batches."""
        return list(self._batches.values())

    def clear(self) -> None:
        """Clear all batches (primarily for test resets)."""
        self._batches.clear()


# Global in-memory instance
batch_store = BatchStore()
