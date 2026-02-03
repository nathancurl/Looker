"""Main orchestrator: scheduler loop + fetcher registry."""

import logging
import os
import signal
import sys
import time

from config import AppConfig, is_dry_run, load_config
from discord_notifier import notify
from fetchers.ashby import AshbyFetcher
from fetchers.base import BaseFetcher
from fetchers.greenhouse import GreenhouseFetcher
from fetchers.hnhiring import HNHiringFetcher
from fetchers.lever import LeverFetcher
from fetchers.newgrad_json import NewGradJSONFetcher
from fetchers.newgrad_markdown import NewGradMarkdownFetcher
from fetchers.smartrecruiters import SmartRecruitersFetcher
from fetchers.workable import WorkableFetcher
from fetchers.workday import WorkdayFetcher
from filtering import filter_job
from state import StateStore

logger = logging.getLogger(__name__)

FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
    "newgrad_json": NewGradJSONFetcher,
    "newgrad_markdown": NewGradMarkdownFetcher,
    "greenhouse": GreenhouseFetcher,
    "lever": LeverFetcher,
    "ashby": AshbyFetcher,
    "workable": WorkableFetcher,
    "smartrecruiters": SmartRecruitersFetcher,
    "workday": WorkdayFetcher,
    "hn_hiring": HNHiringFetcher,
}

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down gracefully...", signum)
    _shutdown = True


def build_fetchers(config: AppConfig) -> list[tuple[BaseFetcher, int]]:
    """Instantiate fetchers from config sources.

    Returns list of (fetcher, poll_interval_seconds) tuples.
    """
    fetchers = []

    for source_type, fetcher_cls in FETCHER_REGISTRY.items():
        source_conf = config.sources.get(source_type)
        if source_conf is None:
            continue

        if isinstance(source_conf, list):
            for item in source_conf:
                interval = item.get("poll_interval_seconds", config.poll_interval_seconds)
                fetchers.append((fetcher_cls(item), interval))
        elif isinstance(source_conf, dict):
            interval = source_conf.get("poll_interval_seconds", config.poll_interval_seconds)
            fetchers.append((fetcher_cls(source_conf), interval))

    logger.info("Built %d fetcher(s)", len(fetchers))
    return fetchers


def poll_once(
    fetchers: list[tuple[BaseFetcher, int]],
    state: StateStore,
    config: AppConfig,
    last_polled: dict[str, float],
) -> int:
    """Run one poll cycle. Returns count of new notifications sent."""
    now = time.time()
    new_count = 0

    for fetcher, interval in fetchers:
        key = fetcher.source_name
        elapsed = now - last_polled.get(key, 0)
        if elapsed < interval:
            continue

        last_polled[key] = now
        jobs = fetcher.safe_fetch()

        for job in jobs:
            if state.is_seen(job.uid):
                continue

            passed, matched_kw = filter_job(job, config)

            if not passed:
                # Filtered out — mark seen to avoid re-evaluation
                state.mark_seen(job.uid, job.source_group, job.url)
                continue

            success = notify(job, matched_kw, config)
            if success:
                state.mark_seen(job.uid, job.source_group, job.url)
                new_count += 1
            # If notify fails, don't mark seen — retry next cycle

    return new_count


def main():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    config_path = os.environ.get("CONFIG_PATH", "config.json")
    env_path = os.environ.get("ENV_PATH", ".env")
    db_path = os.environ.get("DB_PATH", "seen_jobs.db")

    config = load_config(config_path, env_path)
    state = StateStore(db_path)
    fetchers = build_fetchers(config)

    if not fetchers:
        logger.warning("No fetchers configured, exiting")
        return

    logger.info(
        "Starting poll loop (global interval=%ds, dry_run=%s, %d fetchers, %d seen items)",
        config.poll_interval_seconds,
        is_dry_run(),
        len(fetchers),
        state.count(),
    )

    last_polled: dict[str, float] = {}

    try:
        while not _shutdown:
            new = poll_once(fetchers, state, config, last_polled)
            if new:
                logger.info("Sent %d new notification(s), total seen: %d", new, state.count())
            time.sleep(min(config.poll_interval_seconds, 60))
    finally:
        state.close()
        logger.info("Shut down cleanly")


if __name__ == "__main__":
    main()
