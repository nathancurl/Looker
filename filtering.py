"""Keyword filtering for job postings."""

import re

from config import AppConfig
from models import Job


def filter_job(job: Job, config: AppConfig) -> tuple[bool, list[str]]:
    """Check if a job matches filtering criteria.

    Returns (should_notify, matched_keywords).
    Order: exclude check -> location check -> include check -> optional level gate.
    """
    searchable = f"{job.title} {job.snippet} {job.company}".lower()
    filtering = config.filtering

    # Exclude check — if any exclude keyword matches, reject
    for kw in filtering.exclude_keywords:
        if keyword_matches(kw, searchable):
            return False, []

    # Location check — if enabled, check if location is in allowed list
    if filtering.location.enabled:
        if not is_allowed_location(job.location, filtering.location):
            return False, []

    # Include check — at least one include keyword must match (if list non-empty)
    matched = []
    if filtering.include_keywords:
        for kw in filtering.include_keywords:
            if keyword_matches(kw, searchable):
                matched.append(kw)
        if not matched:
            return False, []

    # Level gate — if enabled, at least one level term must match
    if filtering.level_keywords.enabled and filtering.level_keywords.terms:
        level_match = any(
            keyword_matches(term, searchable)
            for term in filtering.level_keywords.terms
        )
        if not level_match:
            return False, matched

    return True, matched


def keyword_matches(keyword: str, text: str) -> bool:
    """Match keyword in text. Word boundary for single words, substring for multi-word."""
    keyword_lower = keyword.lower()
    # Use substring match for multi-word, hyphenated, or keywords with punctuation
    if " " in keyword_lower or "-" in keyword_lower or "." in keyword_lower or "," in keyword_lower:
        return keyword_lower in text
    return bool(re.search(rf"\b{re.escape(keyword_lower)}\b", text))


def is_allowed_location(location: str, location_config) -> bool:
    """Check if job location is in allowed list.

    Returns True if:
    - Location is empty/unknown (benefit of doubt)
    - Location contains an allowed country/state/keyword
    - Job is marked as remote in an allowed region
    """
    if not location:
        # If no location specified, allow it (benefit of doubt)
        return True

    location_lower = location.lower()

    # Check if location contains any excluded keywords first (international locations)
    for keyword in location_config.excluded_keywords:
        if keyword.lower() in location_lower:
            return False

    # Check if location contains any allowed keywords
    for keyword in location_config.allowed_keywords:
        if keyword.lower() in location_lower:
            return True

    # If no allowed keywords specified, allow all
    if not location_config.allowed_keywords:
        return True

    return False
