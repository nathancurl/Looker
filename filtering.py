"""Keyword filtering for job postings."""

import re

from config import AppConfig
from models import Job


def filter_job(job: Job, config: AppConfig) -> tuple[bool, list[str]]:
    """Check if a job matches filtering criteria.

    Returns (should_notify, matched_keywords).
    Order: exclude check -> include check -> optional level gate.
    """
    searchable = f"{job.title} {job.snippet} {job.company}".lower()
    filtering = config.filtering

    # Exclude check — if any exclude keyword matches, reject
    for kw in filtering.exclude_keywords:
        if keyword_matches(kw, searchable):
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
    if " " in keyword_lower or "-" in keyword_lower:
        return keyword_lower in text
    return bool(re.search(rf"\b{re.escape(keyword_lower)}\b", text))
