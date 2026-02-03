"""Tests for filtering.py."""

from config import AppConfig
from filtering import filter_job
from models import Job


def _make_job(**kwargs):
    defaults = {
        "uid": "test:1",
        "source_group": "test",
        "source_name": "Test",
        "title": "Software Engineer",
        "company": "Acme",
        "url": "https://example.com",
    }
    defaults.update(kwargs)
    return Job(**defaults)


def _make_config(include=None, exclude=None, level_enabled=False, level_terms=None):
    return AppConfig(
        filtering={
            "include_keywords": include or [],
            "exclude_keywords": exclude or [],
            "level_keywords": {
                "enabled": level_enabled,
                "terms": level_terms or [],
            },
        },
        routing={},
        sources={},
    )


class TestFiltering:
    def test_include_match(self):
        job = _make_job(title="Backend Software Engineer")
        config = _make_config(include=["software engineer"])
        passed, matched = filter_job(job, config)
        assert passed is True
        assert "software engineer" in matched

    def test_include_no_match(self):
        job = _make_job(title="Product Manager")
        config = _make_config(include=["software engineer", "python"])
        passed, matched = filter_job(job, config)
        assert passed is False
        assert matched == []

    def test_exclude_priority(self):
        job = _make_job(title="Senior Software Engineer")
        config = _make_config(include=["software engineer"], exclude=["senior"])
        passed, matched = filter_job(job, config)
        assert passed is False

    def test_exclude_blocks_even_with_include_match(self):
        job = _make_job(title="Staff Python Developer")
        config = _make_config(include=["python"], exclude=["staff"])
        passed, _ = filter_job(job, config)
        assert passed is False

    def test_word_boundary_single_word(self):
        job = _make_job(title="API Developer")
        config = _make_config(include=["api"])
        passed, matched = filter_job(job, config)
        assert passed is True
        assert "api" in matched

    def test_word_boundary_no_partial_match(self):
        """'api' should not match inside 'capital'."""
        job = _make_job(title="Capital Markets Analyst", company="CapitalOne")
        config = _make_config(include=["api"])
        passed, _ = filter_job(job, config)
        assert passed is False

    def test_multi_word_keyword_substring(self):
        job = _make_job(title="Full Stack Developer")
        config = _make_config(include=["full stack"])
        passed, matched = filter_job(job, config)
        assert passed is True

    def test_level_gate_enabled_pass(self):
        job = _make_job(title="Junior Software Engineer")
        config = _make_config(
            include=["software engineer"],
            level_enabled=True,
            level_terms=["junior", "new grad"],
        )
        passed, matched = filter_job(job, config)
        assert passed is True

    def test_level_gate_enabled_fail(self):
        job = _make_job(title="Software Engineer")
        config = _make_config(
            include=["software engineer"],
            level_enabled=True,
            level_terms=["junior", "new grad"],
        )
        passed, _ = filter_job(job, config)
        assert passed is False

    def test_level_gate_disabled(self):
        job = _make_job(title="Software Engineer")
        config = _make_config(
            include=["software engineer"],
            level_enabled=False,
            level_terms=["junior"],
        )
        passed, _ = filter_job(job, config)
        assert passed is True

    def test_empty_include_list_passes_all(self):
        job = _make_job(title="Anything")
        config = _make_config(include=[], exclude=[])
        passed, matched = filter_job(job, config)
        assert passed is True
        assert matched == []

    def test_snippet_searched(self):
        job = _make_job(title="Engineer", snippet="Work with Python and Django")
        config = _make_config(include=["python"])
        passed, matched = filter_job(job, config)
        assert passed is True

    def test_company_searched(self):
        job = _make_job(title="Engineer", company="Python Corp")
        config = _make_config(include=["python"])
        passed, matched = filter_job(job, config)
        assert passed is True

    def test_hyphenated_keyword_match(self):
        job = _make_job(title="Full-Stack Developer")
        config = _make_config(include=["full-stack"])
        passed, matched = filter_job(job, config)
        assert passed is True
