"""Tests for models.py."""

from datetime import datetime, timezone

from models import Job


class TestJobModel:
    def test_basic_creation(self, sample_job):
        assert sample_job.title == "Software Engineer"
        assert sample_job.company == "Acme Corp"
        assert sample_job.source_group == "test"

    def test_snippet_truncation(self):
        long_text = "x" * 500
        job = Job(
            uid="test:1",
            source_group="test",
            source_name="Test",
            title="Eng",
            company="Co",
            url="https://example.com",
            snippet=long_text,
        )
        assert len(job.snippet) == 300
        assert job.snippet.endswith("...")

    def test_snippet_short_unchanged(self):
        job = Job(
            uid="test:1",
            source_group="test",
            source_name="Test",
            title="Eng",
            company="Co",
            url="https://example.com",
            snippet="Short snippet",
        )
        assert job.snippet == "Short snippet"

    def test_snippet_empty(self):
        job = Job(
            uid="test:1",
            source_group="test",
            source_name="Test",
            title="Eng",
            company="Co",
            url="https://example.com",
            snippet="",
        )
        assert job.snippet == ""

    def test_serialization(self, sample_job):
        data = sample_job.model_dump()
        assert data["uid"] == "test:123"
        assert data["tags"] == ["python", "react"]
        assert isinstance(data["posted_at"], datetime)


class TestUIDGeneration:
    def test_tier1_raw_id(self):
        uid = Job.generate_uid("greenhouse", raw_id="12345")
        assert uid == "greenhouse:12345"

    def test_tier2_url(self):
        uid = Job.generate_uid("lever", url="https://jobs.lever.co/acme/abc-123")
        assert uid.startswith("lever:url:")
        assert len(uid) > len("lever:url:")

    def test_tier2_url_canonicalization(self):
        uid1 = Job.generate_uid("lever", url="https://Jobs.Lever.co/acme/abc-123/")
        uid2 = Job.generate_uid("lever", url="https://jobs.lever.co/acme/abc-123")
        assert uid1 == uid2

    def test_tier2_url_strips_query(self):
        uid1 = Job.generate_uid("lever", url="https://example.com/job?ref=twitter")
        uid2 = Job.generate_uid("lever", url="https://example.com/job")
        assert uid1 == uid2

    def test_tier3_hash_fallback(self):
        uid = Job.generate_uid(
            "hn",
            title="Backend Engineer",
            company="Acme",
            location="SF",
            posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert uid.startswith("hn:hash:")

    def test_tier3_deterministic(self):
        kwargs = {
            "title": "Backend",
            "company": "Acme",
            "location": "SF",
            "posted_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        uid1 = Job.generate_uid("hn", **kwargs)
        uid2 = Job.generate_uid("hn", **kwargs)
        assert uid1 == uid2

    def test_raw_id_takes_precedence(self):
        uid = Job.generate_uid(
            "greenhouse",
            raw_id="12345",
            url="https://example.com/job",
        )
        assert uid == "greenhouse:12345"
