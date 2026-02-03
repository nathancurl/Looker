"""Tests for NewGrad Markdown fetcher."""

import responses

from fetchers.newgrad_markdown import NewGradMarkdownFetcher

SAMPLE_MD = """\
# New Grad Jobs 2026

| Company | Role | Location | Link | Date |
|---------|------|----------|------|------|
| [TechCo](https://techco.com) | Software Engineer | San Francisco, CA | [Apply](https://techco.com/apply) | Jan 15 |
| DataCorp | Data Analyst | New York, NY | [Apply](https://datacorp.com/apply) | Jan 10 |
| | Missing Company | Remote | [Apply](https://nocompany.com) | Jan 5 |
"""


class TestNewGradMarkdownFetcher:
    @responses.activate
    def test_parse_markdown_table(self):
        url = "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_USA.md"
        responses.add(responses.GET, url, body=SAMPLE_MD, status=200)

        fetcher = NewGradMarkdownFetcher({
            "name": "speedyapply-2026",
            "owner": "speedyapply",
            "repo": "2026-SWE-College-Jobs",
            "branch": "main",
            "files": ["NEW_GRAD_USA.md"],
        })
        jobs = fetcher.fetch()

        # Should parse 2 valid rows (3rd has no company)
        assert len(jobs) == 2
        assert jobs[0].company == "TechCo"
        assert jobs[0].title == "Software Engineer"
        assert jobs[0].location == "San Francisco, CA"
        assert jobs[0].url == "https://techco.com/apply"

        assert jobs[1].company == "DataCorp"

    @responses.activate
    def test_empty_markdown(self):
        url = "https://raw.githubusercontent.com/test/repo/main/EMPTY.md"
        responses.add(responses.GET, url, body="# No tables here\nJust text.", status=200)

        fetcher = NewGradMarkdownFetcher({
            "name": "test",
            "owner": "test",
            "repo": "repo",
            "branch": "main",
            "files": ["EMPTY.md"],
        })
        jobs = fetcher.fetch()
        assert jobs == []
