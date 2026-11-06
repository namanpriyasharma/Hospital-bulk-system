"""HTTP client service for the external Hospital Directory API."""

from typing import Any, Dict, Optional
import httpx
from app.config import settings
from app.utils.logger import logger


class DirectoryAPIError(Exception):
    """Exception raised when an external API call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data


class HospitalDirectoryClient:
    """Asynchronous client interacting with the deployed Hospital Directory API."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.DIRECTORY_API_BASE_URL).rstrip("/")
        self._limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0,
        )
        self._timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS, connect=10.0)

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            limits=self._limits,
            timeout=self._timeout,
        )

    async def create_hospital(
        self,
        name: str,
        address: str,
        phone: Optional[str],
        batch_id: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Create a single hospital record associated with a batch_id.
        Makes POST /hospitals/
        """
        payload: Dict[str, Any] = {
            "name": name,
            "address": address,
            "creation_batch_id": batch_id,
        }
        if phone:
            payload["phone"] = phone

        url = "/hospitals/"
        owns_client = False
        if client is None:
            client = self._get_client()
            owns_client = True

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            error_detail = exc.response.text
            logger.warning(
                f"Directory API POST /hospitals/ failed ({exc.response.status_code}): {error_detail}"
            )
            raise DirectoryAPIError(
                message=f"Failed to create hospital '{name}': {error_detail}",
                status_code=exc.response.status_code,
                response_data=error_detail,
            ) from exc
        except httpx.RequestError as exc:
            logger.error(f"Network error calling POST /hospitals/: {str(exc)}")
            raise DirectoryAPIError(
                message=f"Network connectivity error to directory API: {str(exc)}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

    async def activate_batch(
        self,
        batch_id: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Activate all hospitals associated with a batch_id.
        Makes PATCH /hospitals/batch/{batch_id}/activate
        """
        url = f"/hospitals/batch/{batch_id}/activate"
        owns_client = False
        if client is None:
            client = self._get_client()
            owns_client = True

        try:
            response = await client.patch(url)
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {"status": "activated", "batch_id": batch_id}
        except httpx.HTTPStatusError as exc:
            error_detail = exc.response.text
            logger.error(
                f"Directory API PATCH /hospitals/batch/{batch_id}/activate failed ({exc.response.status_code}): {error_detail}"
            )
            raise DirectoryAPIError(
                message=f"Failed to activate batch '{batch_id}': {error_detail}",
                status_code=exc.response.status_code,
                response_data=error_detail,
            ) from exc
        except httpx.RequestError as exc:
            logger.error(f"Network error calling PATCH /hospitals/batch/{batch_id}/activate: {str(exc)}")
            raise DirectoryAPIError(
                message=f"Network error during batch activation: {str(exc)}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

    async def get_batch_hospitals(
        self,
        batch_id: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Any:
        """Retrieve hospitals belonging to a batch ID."""
        url = f"/hospitals/batch/{batch_id}"
        owns_client = False
        if client is None:
            client = self._get_client()
            owns_client = True

        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error(f"Failed to retrieve batch {batch_id}: {str(exc)}")
            raise DirectoryAPIError(message=str(exc)) from exc
        finally:
            if owns_client:
                await client.aclose()


directory_client = HospitalDirectoryClient()
