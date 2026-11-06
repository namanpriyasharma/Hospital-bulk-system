"""Tests for standalone CSV validation endpoint (Bonus 6.4)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validate_endpoint_valid_csv(async_client: AsyncClient):
    csv_content = """name,address,phone
Hospital One,Address One,555-1111
Hospital Two,Address Two,
"""
    files = {"file": ("check.csv", csv_content, "text/csv")}
    response = await async_client.post("/hospitals/bulk/validate", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["total_rows"] == 2
    assert data["max_allowed_rows"] == 20
    assert len(data["errors"]) == 0
    assert len(data["preview"]) == 2


@pytest.mark.asyncio
async def test_validate_endpoint_invalid_csv(async_client: AsyncClient):
    csv_content = """phone,notes
555-1111,missing name and address
"""
    files = {"file": ("bad.csv", csv_content, "text/csv")}
    response = await async_client.post("/hospitals/bulk/validate", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) >= 2
