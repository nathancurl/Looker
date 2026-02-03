"""Configuration loading and validation."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LevelKeywordsConfig(BaseModel):
    enabled: bool = False
    terms: list[str] = []


class FilteringConfig(BaseModel):
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []
    level_keywords: LevelKeywordsConfig = LevelKeywordsConfig()


class AppConfig(BaseModel):
    poll_interval_seconds: int = 600
    filtering: FilteringConfig = FilteringConfig()
    routing: dict[str, str] = {}
    sources: dict[str, Any] = {}


def load_config(
    config_path: str = "config.json",
    env_path: Optional[str] = ".env",
) -> AppConfig:
    """Load .env and config.json, return validated AppConfig."""
    if env_path:
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        raw = json.load(f)

    config = AppConfig(**raw)

    # Warn about missing webhook URLs
    for source_group, env_var in config.routing.items():
        if not os.environ.get(env_var):
            logger.warning(
                "Webhook env var %s for source group '%s' is not set",
                env_var,
                source_group,
            )

    return config


def get_webhook_url(config: AppConfig, source_group: str) -> Optional[str]:
    """Resolve webhook URL for a source group via routing config."""
    env_var = config.routing.get(source_group)
    if not env_var:
        logger.warning("No routing entry for source group '%s'", source_group)
        return None
    url = os.environ.get(env_var)
    if not url:
        logger.warning("Webhook env var %s is not set", env_var)
        return None
    return url


def is_dry_run() -> bool:
    """Check if DRY_RUN is enabled."""
    return os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")
