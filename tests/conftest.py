"""Shared test fixtures."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from config import AppConfig
from models import Job
from state import StateStore

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_job():
    return Job(
        uid="test:123",
        source_group="test",
        source_name="TestSource",
        title="Software Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        remote=False,
        url="https://example.com/jobs/123",
        snippet="Build amazing things with Python and React.",
        posted_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        raw_id="123",
        tags=["python", "react"],
    )


@pytest.fixture
def sample_config():
    return AppConfig(
        poll_interval_seconds=600,
        filtering={
            "include_keywords": ["software engineer", "python", "backend"],
            "exclude_keywords": ["senior", "staff", "principal"],
            "level_keywords": {
                "enabled": False,
                "terms": ["new grad", "junior", "entry level"],
            },
        },
        routing={
            "test": "DISCORD_WEBHOOK_TEST",
            "newgrad": "DISCORD_WEBHOOK_GITHUB",
            "greenhouse": "DISCORD_WEBHOOK_GREENHOUSE",
        },
        sources={},
    )


@pytest.fixture
def in_memory_state():
    store = StateStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def fixture_path():
    """Return a function that resolves fixture file paths."""
    def _resolve(name: str) -> Path:
        return FIXTURES_DIR / name
    return _resolve


@pytest.fixture
def load_fixture():
    """Return a function that loads a JSON fixture."""
    def _load(name: str):
        with open(FIXTURES_DIR / name) as f:
            return json.load(f)
    return _load


@pytest.fixture
def load_fixture_text():
    """Return a function that loads a fixture as raw text (e.g. XML)."""
    def _load(name: str) -> str:
        with open(FIXTURES_DIR / name) as f:
            return f.read()
    return _load
