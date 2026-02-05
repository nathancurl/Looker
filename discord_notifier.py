"""Discord webhook notification with embeds and retry logic."""

import logging
import time
from typing import Dict

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

# Global rate limit tracker: webhook_url -> timestamp when cooldown expires
_rate_limit_cooldowns: Dict[str, float] = {}


def build_embed(job: Job, matched_keywords: list[str]) -> dict:
    """Build a Discord embed dict for a job posting."""
    # Truncate title if needed (Discord limit: 256 chars)
    title = f"{job.company} — {job.title}"
    if len(title) > 256:
        title = title[:253] + "..."

    embed = {
        "title": title,
        "url": job.url,
        "color": DISCORD_BLURPLE,
        "fields": [
            {"name": "Source", "value": job.source_name, "inline": True},
        ],
    }

    if job.snippet:
        # Truncate description if needed (Discord limit: 2048 chars)
        snippet = job.snippet
        if len(snippet) > 2048:
            snippet = snippet[:2045] + "..."
        embed["description"] = snippet

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
    """Post a job embed to Discord. Returns True on success, False on failure (or rate-limited)."""
    if is_dry_run():
        logger.info("[DRY RUN] Would notify: %s — %s (%s)", job.company, job.title, job.url)
        return True

    webhook_url = get_webhook_url(config, job.source_group)
    if not webhook_url:
        logger.warning("No webhook URL for source group '%s', skipping", job.source_group)
        return False

    # Check if this webhook is currently rate-limited
    now = time.time()
    cooldown_until = _rate_limit_cooldowns.get(webhook_url, 0)
    if now < cooldown_until:
        # Still in cooldown, skip without blocking
        return False

    embed = build_embed(job, matched_keywords)
    payload = {"embeds": [embed]}

    try:
        _send_with_retry(webhook_url, payload)
        return True
    except DiscordRateLimitError as e:
        # Record the cooldown and return False to retry later
        _rate_limit_cooldowns[webhook_url] = now + e.retry_after
        logger.warning("Discord rate limited for %s, cooldown until %s", job.source_group, time.ctime(now + e.retry_after))
        return False
    except Exception:
        logger.exception("Failed to send Discord notification for %s", job.uid)
        return False


@retry(
    retry=retry_if_exception_type(DiscordServerError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _send_with_retry(webhook_url: str, payload: dict) -> None:
    """POST to Discord webhook with retry only on 5xx. Raises DiscordRateLimitError on 429."""
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
        # Don't log here, let the caller handle it
        raise DiscordRateLimitError(retry_after)

    if resp.status_code >= 500:
        logger.warning("Discord server error %d", resp.status_code)
        raise DiscordServerError(f"Status {resp.status_code}")

    resp.raise_for_status()
