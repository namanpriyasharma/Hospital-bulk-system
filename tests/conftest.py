"""Pytest configuration and fixtures."""

import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.batch import batch_store
from app.services.bulk_processor import bulk_processor


@pytest.fixture(autouse=True)
def reset_batch_store():
    """Reset in-memory storage before each test run."""
    batch_store.clear()
    yield
    batch_store.clear()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client bound to the FastAPI ASGI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def mock_directory_client():
    """Mock external Hospital Directory API interactions."""
    mock = AsyncMock()

    async def mock_create(name, address, phone, batch_id, client=None):
        import random
        return {
            "id": random.randint(100, 999),
            "name": name,
            "address": address,
            "phone": phone,
            "creation_batch_id": batch_id,
            "active": False,
        }

    async def mock_activate(batch_id, client=None):
        return {
            "batch_id": batch_id,
            "status": "activated",
            "activated_count": 5,
        }

    mock.create_hospital.side_effect = mock_create
    mock.activate_batch.side_effect = mock_activate
    # Give it a fake base_url and limits/timeout so bulk_processor doesn't crash
    mock.base_url = "http://mock-hospital-directory.test"

    import httpx
    mock._limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    mock._timeout = httpx.Timeout(10.0)

    with patch.object(bulk_processor, "directory_client", mock):
        yield mock
