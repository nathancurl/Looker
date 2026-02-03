"""Discord webhook notification with embeds and retry logic."""

import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import AppConfig, get_webhook_url, is_dry_run
from models import Job

logger = logging.getLogger(__name__)

DISCORD_BLURPLE = 0x5865F2


def build_embed(job: Job, matched_keywords: list[str]) -> dict:
    """Build a Discord embed dict for a job posting."""
    embed = {
        "title": f"{job.company} — {job.title}",
        "url": job.url,
        "color": DISCORD_BLURPLE,
        "fields": [
            {"name": "Source", "value": job.source_name, "inline": True},
        ],
    }

    if job.snippet:
        embed["description"] = job.snippet

    if job.location:
        embed["fields"].append(
            {"name": "Location", "value": job.location, "inline": True}
        )

    if job.remote:
        embed["fields"].append(
            {"name": "Remote", "value": "Yes", "inline": True}
        )

    if matched_keywords:
        embed["fields"].append(
            {"name": "Matched Keywords", "value": ", ".join(matched_keywords), "inline": False}
        )

    if job.posted_at:
        embed["timestamp"] = job.posted_at.isoformat()

    return embed


class DiscordRateLimitError(Exception):
    """Raised on 429 to trigger retry."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class DiscordServerError(Exception):
    """Raised on 5xx to trigger retry."""
    pass


def notify(job: Job, matched_keywords: list[str], config: AppConfig) -> bool:
    """Post a job embed to Discord. Returns True on success, False on failure."""
    if is_dry_run():
        logger.info("[DRY RUN] Would notify: %s — %s (%s)", job.company, job.title, job.url)
        return True

    webhook_url = get_webhook_url(config, job.source_group)
    if not webhook_url:
        logger.warning("No webhook URL for source group '%s', skipping", job.source_group)
        return False

    embed = build_embed(job, matched_keywords)
    payload = {"embeds": [embed]}

    try:
        _send_with_retry(webhook_url, payload)
        return True
    except Exception:
        logger.exception("Failed to send Discord notification for %s", job.uid)
        return False


@retry(
    retry=retry_if_exception_type((DiscordServerError, DiscordRateLimitError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _send_with_retry(webhook_url: str, payload: dict) -> None:
    """POST to Discord webhook with retry on 5xx and 429."""
    resp = requests.post(webhook_url, json=payload, timeout=15)

    if resp.status_code == 429:
        # Prefer Retry-After header, fallback to JSON body or default
        if "Retry-After" in resp.headers:
            retry_after = float(resp.headers["Retry-After"])
        else:
            try:
                retry_after = resp.json().get("retry_after", 5)
            except ValueError:
                retry_after = 5
        logger.warning("Discord rate limited, retry_after=%s", retry_after)
        # Let tenacity handle the wait via wait_exponential
        raise DiscordRateLimitError(retry_after)

    if resp.status_code >= 500:
        logger.warning("Discord server error %d", resp.status_code)
        raise DiscordServerError(f"Status {resp.status_code}")

    resp.raise_for_status()
