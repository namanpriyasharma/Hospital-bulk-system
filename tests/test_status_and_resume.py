"""Tests for batch status tracking and resume capability (Bonus 6.2 & 6.3)."""

import pytest
from httpx import AsyncClient
from app.services.directory_client import DirectoryAPIError


@pytest.mark.asyncio
async def test_batch_status_polling(async_client: AsyncClient, mock_directory_client):
    csv_content = "name,address\nClinic Alpha,100 Alpha Rd\n"
    files = {"file": ("test.csv", csv_content, "text/csv")}

    create_res = await async_client.post("/hospitals/bulk", files=files)
    assert create_res.status_code == 200
    batch_id = create_res.json()["batch_id"]

    # Poll status endpoint
    status_res = await async_client.get(f"/hospitals/bulk/{batch_id}/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["batch_id"] == batch_id
    assert data["status"] == "completed"
    assert data["total_hospitals"] == 1
    assert data["processed_hospitals"] == 1
    assert data["batch_activated"] is True


@pytest.mark.asyncio
async def test_batch_status_not_found(async_client: AsyncClient):
    res = await async_client.get("/hospitals/bulk/non-existent-uuid/status")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_batch_resume_capability(async_client: AsyncClient, mock_directory_client):
    """Verify that a partially failed batch can be resumed without recreating succeeded items."""
    attempt_count = 0

    async def flaky_create(name, address, phone, batch_id, client=None):
        nonlocal attempt_count
        attempt_count += 1
        if "Flaky" in name and attempt_count == 2:
            raise DirectoryAPIError("Temporary network timeout", status_code=504)
        return {"id": 100 + attempt_count, "name": name, "address": address, "active": False}

    mock_directory_client.create_hospital.side_effect = flaky_create

    csv_content = """name,address,phone
Hospital Stable,101 Stable Way,555-1111
Hospital Flaky,102 Flaky Way,555-2222
"""
    files = {"file": ("flaky.csv", csv_content, "text/csv")}

    # Initial run - one succeeds, one fails
    res1 = await async_client.post("/hospitals/bulk", files=files)
    assert res1.status_code == 200
    data1 = res1.json()
    batch_id = data1["batch_id"]
    assert data1["failed_hospitals"] == 1
    assert data1["batch_activated"] is False

    # Now call resume endpoint
    resume_res = await async_client.post(f"/hospitals/bulk/{batch_id}/resume")
    assert resume_res.status_code == 200
    data2 = resume_res.json()

    # After resume, both should be processed and batch activated
    assert data2["failed_hospitals"] == 0
    assert data2["batch_activated"] is True
    assert data2["processed_hospitals"] == 2
