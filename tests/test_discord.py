"""Tests for discord_notifier.py."""

import os
from datetime import datetime, timezone

import responses

from config import AppConfig
from discord_notifier import build_embed, notify
from models import Job


def _make_job(**kwargs):
    defaults = {
        "uid": "test:1",
        "source_group": "test",
        "source_name": "TestSource",
        "title": "Software Engineer",
        "company": "Acme",
        "url": "https://example.com/job/1",
        "snippet": "Build things.",
        "location": "SF, CA",
    }
    defaults.update(kwargs)
    return Job(**defaults)


class TestBuildEmbed:
    def test_basic_embed(self):
        job = _make_job()
        embed = build_embed(job, ["python"])
        assert embed["title"] == "Acme — Software Engineer"
        assert embed["url"] == "https://example.com/job/1"
        assert embed["color"] == 0x5865F2
        assert embed["description"] == "Build things."

    def test_fields(self):
        job = _make_job(location="NYC", remote=True)
        embed = build_embed(job, ["api", "backend"])
        field_names = [f["name"] for f in embed["fields"]]
        assert "Source" in field_names
        assert "Location" in field_names
        assert "Remote" in field_names
        assert "Matched Keywords" in field_names

    def test_timestamp_included(self):
        job = _make_job(posted_at=datetime(2026, 1, 15, tzinfo=timezone.utc))
        embed = build_embed(job, [])
        assert "timestamp" in embed

    def test_no_timestamp_when_none(self):
        job = _make_job(posted_at=None)
        embed = build_embed(job, [])
        assert "timestamp" not in embed

    def test_no_location_field_when_empty(self):
        job = _make_job(location="")
        embed = build_embed(job, [])
        field_names = [f["name"] for f in embed["fields"]]
        assert "Location" not in field_names


class TestNotify:
    def test_dry_run(self, sample_config, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        job = _make_job()
        result = notify(job, ["python"], sample_config)
        assert result is True

    @responses.activate
    def test_successful_post(self, sample_config, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("DISCORD_WEBHOOK_TEST", "https://discord.com/api/webhooks/test/token")
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test/token",
            status=204,
        )
        job = _make_job()
        result = notify(job, ["python"], sample_config)
        assert result is True
        assert len(responses.calls) == 1

    def test_missing_webhook(self, sample_config, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.delenv("DISCORD_WEBHOOK_TEST", raising=False)
        job = _make_job()
        result = notify(job, [], sample_config)
        assert result is False
