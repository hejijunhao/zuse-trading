"""HTTP Client - Base HTTP client with retries and rate limiting.

Provides reusable HTTP request handling for all data fetcher services.
Features:
- Exponential backoff retry logic via tenacity
- Configurable rate limiting (requests per second)
- Timeout handling
- Standardized error responses
"""

import logging
import time
from typing import Any, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(HTTPClientError):
    """Raised when rate limit is exceeded (429)."""

    pass


class APIError(HTTPClientError):
    """Raised for API errors (4xx, 5xx)."""

    pass


class HTTPClient:
    """Base HTTP client with retries and rate limiting.

    Used by all fetcher services to make HTTP requests to external APIs.

    Example:
        client = HTTPClient(
            base_url="https://api.financialdatasets.ai",
            api_key="your_api_key",
            rate_limit_rps=5.0
        )
        data = client.get("/prices/", {"ticker": "AAPL"})
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        rate_limit_rps: float = 5.0,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ):
        """Initialize HTTP client.

        Args:
            base_url: Base URL for API (e.g., "https://api.financialdatasets.ai")
            api_key: API key for authentication (optional)
            api_key_header: Header name for API key (default: "X-API-Key")
            rate_limit_rps: Max requests per second (default: 5.0)
            timeout_seconds: Request timeout in seconds (default: 30)
            max_retries: Max retry attempts on failure (default: 3)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.rate_limit_rps = rate_limit_rps
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Rate limiting state
        self._min_interval = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0
        self._last_request_time: float = 0

        # Session for connection pooling
        self._session = requests.Session()

        logger.debug(
            f"HTTPClient initialized: base_url={base_url}, "
            f"rate_limit={rate_limit_rps} rps, timeout={timeout_seconds}s"
        )

    def _build_headers(self) -> dict[str, str]:
        """Build request headers including API key if configured."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between requests."""
        if self._min_interval <= 0:
            return

        now = time.monotonic()
        elapsed = now - self._last_request_time
        wait_time = self._min_interval - elapsed

        if wait_time > 0:
            logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
            time.sleep(wait_time)

        self._last_request_time = time.monotonic()

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle response and raise appropriate errors.

        Args:
            response: Response object from requests

        Returns:
            Parsed JSON response

        Raises:
            RateLimitError: If rate limited (429)
            APIError: For other HTTP errors
        """
        if response.status_code == 429:
            raise RateLimitError(
                f"Rate limit exceeded: {response.text}",
                status_code=429,
            )

        if response.status_code >= 400:
            raise APIError(
                f"API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as e:
            raise APIError(f"Invalid JSON response: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, RateLimitError)),
        reraise=True,
    )
    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make GET request with retries and rate limiting.

        Args:
            endpoint: API endpoint (e.g., "/prices/")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            HTTPClientError: On request failure after retries
        """
        self._rate_limit_wait()

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        logger.debug(f"GET {url} params={params}")

        try:
            response = self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            return self._handle_response(response)

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise HTTPClientError(f"Request failed: {e}")

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self) -> "HTTPClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


class FinancialDatasetsHTTPClient(HTTPClient):
    """Pre-configured HTTP client for Financial Datasets API.

    Example:
        from app.core.config import settings

        client = FinancialDatasetsHTTPClient(
            api_key=settings.FINANCIAL_DATASETS_API_KEY
        )
        prices = client.get("/prices/", {"ticker": "AAPL"})
    """

    BASE_URL = "https://api.financialdatasets.ai"

    def __init__(
        self,
        api_key: str,
        rate_limit_rps: float = 5.0,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ):
        """Initialize Financial Datasets API client.

        Args:
            api_key: Financial Datasets API key
            rate_limit_rps: Max requests per second (default: 5.0)
            timeout_seconds: Request timeout in seconds (default: 30)
            max_retries: Max retry attempts on failure (default: 3)
        """
        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            api_key_header="X-API-Key",
            rate_limit_rps=rate_limit_rps,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
