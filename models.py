"""Job model and UID generation."""

import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, field_validator


class Job(BaseModel):
    """Normalized job posting."""

    uid: str
    source_group: str
    source_name: str
    title: str
    company: str
    location: str = ""
    remote: bool = False
    url: str
    snippet: str = ""
    posted_at: Optional[datetime] = None
    raw_id: Optional[str] = None
    tags: list[str] = []

    @field_validator("snippet", mode="before")
    @classmethod
    def truncate_snippet(cls, v: str) -> str:
        if v and len(v) > 2000:
            return v[:1997] + "..."
        return v or ""

    @staticmethod
    def generate_uid(
        source_group: str,
        *,
        raw_id: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        posted_at: Optional[datetime] = None,
    ) -> str:
        """Generate a UID with 3-tier fallback.

        1. "{source_group}:{raw_id}" if raw_id provided
        2. SHA-256 of "{source_group}:{canonical_url}" if url provided
        3. SHA-256 of "{source_group}:{title}:{company}:{location}:{posted_at}"
        """
        if raw_id:
            return f"{source_group}:{raw_id}"

        if url:
            canonical = _canonicalize_url(url)
            digest = hashlib.sha256(f"{source_group}:{canonical}".encode()).hexdigest()[:16]
            return f"{source_group}:url:{digest}"

        parts = f"{source_group}:{title or ''}:{company or ''}:{location or ''}:{posted_at or ''}"
        digest = hashlib.sha256(parts.encode()).hexdigest()[:16]
        return f"{source_group}:hash:{digest}"


def _canonicalize_url(url: str) -> str:
    """Normalize URL: lowercase host, strip query params and trailing slash."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = (parsed.path or "").rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))
