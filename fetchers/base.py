"""Abstract base fetcher and resilient HTTP helpers."""

import logging
from abc import ABC, abstractmethod

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models import Job

logger = logging.getLogger(__name__)

USER_AGENT = "job-notification-discord/0.1 (github.com/ncurl/job-notification-discord)"
DEFAULT_TIMEOUT = 15


class BaseFetcher(ABC):
    """Abstract base class for job fetchers."""

    source_group: str = ""

    def __init__(self, source_config: dict):
        self._config = source_config
        self._name = source_config.get("name", self.__class__.__name__)

    @property
    def source_name(self) -> str:
        return self._name

    @abstractmethod
    def fetch(self) -> list[Job]:
        """Fetch and return normalized jobs. Subclasses must implement."""
        ...

    def safe_fetch(self) -> list[Job]:
        """Wrap fetch() with error handling. Returns [] on failure."""
        try:
            jobs = self.fetch()
            logger.info("%s: fetched %d jobs", self.source_name, len(jobs))
            return jobs
        except Exception:
            logger.exception("%s: fetch failed", self.source_name)
            return []


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def resilient_get(url: str, **kwargs) -> requests.Response:
    """GET with retry on connection errors and timeouts."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("headers", {})
    kwargs["headers"].setdefault("User-Agent", USER_AGENT)
    resp = requests.get(url, **kwargs)
    if resp.status_code >= 500:
        raise requests.ConnectionError(f"Server error {resp.status_code} from {url}")
    return resp


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def resilient_post(url: str, **kwargs) -> requests.Response:
    """POST with retry on connection errors and timeouts."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("headers", {})
    kwargs["headers"].setdefault("User-Agent", USER_AGENT)
    resp = requests.post(url, **kwargs)
    if resp.status_code >= 500:
        raise requests.ConnectionError(f"Server error {resp.status_code} from {url}")
    return resp
