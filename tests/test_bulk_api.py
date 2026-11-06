"""Integration tests for POST /hospitals/bulk."""

import pytest
from httpx import AsyncClient
from app.services.directory_client import DirectoryAPIError


@pytest.mark.asyncio
async def test_bulk_create_success(async_client: AsyncClient, mock_directory_client):
    """Test successful end-to-end bulk creation and activation workflow."""
    csv_content = """name,address,phone
Mercy Hospital,100 Mercy Way,555-1000
St. Luke Medical,200 Luke Blvd,555-2000
Community Health,300 Park Ave,
"""
    files = {"file": ("hospitals.csv", csv_content, "text/csv")}

    response = await async_client.post("/hospitals/bulk", files=files)
    assert response.status_code == 200
    data = response.json()

    assert "batch_id" in data
    assert data["total_hospitals"] == 3
    assert data["processed_hospitals"] == 3
    assert data["failed_hospitals"] == 0
    assert data["batch_activated"] is True
    assert isinstance(data["processing_time_seconds"], (int, float))
    assert len(data["hospitals"]) == 3

    for item in data["hospitals"]:
        assert item["status"] == "created_and_activated"
        assert item["hospital_id"] is not None

    # Verify external API mock calls
    assert mock_directory_client.create_hospital.call_count == 3
    assert mock_directory_client.activate_batch.call_count == 1


@pytest.mark.asyncio
async def test_bulk_create_exceeds_max_20_limit(async_client: AsyncClient, mock_directory_client):
    """Test that CSVs with more than 20 hospitals are rejected per Section 4."""
    rows = ["name,address,phone"]
    for i in range(1, 22):  # 21 rows
        rows.append(f"Hospital {i},Address {i},555-{i:04d}")
    csv_content = "\n".join(rows)

    files = {"file": ("large.csv", csv_content, "text/csv")}
    response = await async_client.post("/hospitals/bulk", files=files)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any("exceeds the maximum limit of 20 hospitals" in err for err in detail["errors"])
    # External API should not have been called
    assert mock_directory_client.create_hospital.call_count == 0


@pytest.mark.asyncio
async def test_bulk_create_invalid_headers(async_client: AsyncClient, mock_directory_client):
    """Test rejection when missing required columns."""
    csv_content = "hospital_name,street\nCity Health,1st Ave\n"
    files = {"file": ("invalid.csv", csv_content, "text/csv")}

    response = await async_client.post("/hospitals/bulk", files=files)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any("Missing required CSV header: 'name'" in err for err in detail["errors"])


@pytest.mark.asyncio
async def test_bulk_create_partial_failure_behavior(async_client: AsyncClient, mock_directory_client):
    """Test that if any hospital creation fails, the batch is NOT activated."""
    async def mock_create_with_one_failure(name, address, phone, batch_id, client=None):
        if "Bad Hospital" in name:
            raise DirectoryAPIError("Simulated remote validation failure", status_code=400)
        return {"id": 101, "name": name, "address": address, "active": False}

    mock_directory_client.create_hospital.side_effect = mock_create_with_one_failure

    csv_content = """name,address,phone
Good Hospital,100 Good St,555-0001
Bad Hospital,200 Bad St,555-0002
"""
    files = {"file": ("test.csv", csv_content, "text/csv")}
    response = await async_client.post("/hospitals/bulk", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["total_hospitals"] == 2
    assert data["processed_hospitals"] == 1
    assert data["failed_hospitals"] == 1
    assert data["batch_activated"] is False

    # External activate_batch should NOT have been called
    assert mock_directory_client.activate_batch.call_count == 0
