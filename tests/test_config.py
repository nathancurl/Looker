"""Tests for config.py."""

import json
import os
from pathlib import Path

import pytest

from config import AppConfig, get_webhook_url, is_dry_run, load_config


class TestLoadConfig:
    def test_valid_config(self, tmp_path):
        config_data = {
            "poll_interval_seconds": 300,
            "filtering": {
                "include_keywords": ["python"],
                "exclude_keywords": ["senior"],
                "level_keywords": {"enabled": False, "terms": []},
            },
            "routing": {"test": "DISCORD_WEBHOOK_TEST"},
            "sources": {},
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        config = load_config(str(config_file), env_path=None)
        assert config.poll_interval_seconds == 300
        assert config.filtering.include_keywords == ["python"]

    def test_missing_config_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json", env_path=None)

    def test_missing_webhook_warns(self, tmp_path, caplog):
        config_data = {
            "routing": {"test": "DISCORD_WEBHOOK_NONEXISTENT"},
            "sources": {},
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        # Ensure the env var is not set
        os.environ.pop("DISCORD_WEBHOOK_NONEXISTENT", None)

        with caplog.at_level("WARNING"):
            load_config(str(config_file), env_path=None)

        assert "DISCORD_WEBHOOK_NONEXISTENT" in caplog.text


class TestGetWebhookUrl:
    def test_returns_url(self, sample_config, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_TEST", "https://discord.com/api/webhooks/123/abc")
        url = get_webhook_url(sample_config, "test")
        assert url == "https://discord.com/api/webhooks/123/abc"

    def test_missing_routing(self, sample_config):
        url = get_webhook_url(sample_config, "nonexistent")
        assert url is None

    def test_missing_env_var(self, sample_config, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_TEST", raising=False)
        url = get_webhook_url(sample_config, "test")
        assert url is None


class TestDryRun:
    def test_dry_run_true(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        assert is_dry_run() is True

    def test_dry_run_false(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        assert is_dry_run() is False

    def test_dry_run_default(self, monkeypatch):
        monkeypatch.delenv("DRY_RUN", raising=False)
        assert is_dry_run() is False

    def test_dry_run_one(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "1")
        assert is_dry_run() is True
