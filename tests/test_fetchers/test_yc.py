"""Tests for Y Combinator fetcher."""

import responses

from fetchers.yc import YCFetcher

HN_JOBS_URL = "https://news.ycombinator.com/jobs"


class TestYCFetcher:
    @responses.activate
    def test_fetch_jobs(self):
        html_response = """
        <html>
        <table>
        <tr class="athing submission" id="46848260">
            <td class="title">
                <span class="titleline">
                    <a href="https://www.ycombinator.com/companies/clearspace/jobs/abc">
                        Clearspace (YC W23) Is Hiring an Applied Researcher (ML)
                    </a>
                </span>
            </td>
        </tr>
        <tr class="athing submission" id="46840801">
            <td class="title">
                <span class="titleline">
                    <a href="https://www.ycombinator.com/companies/collectwise/jobs/xyz">
                        CollectWise (YC F24) Is Hiring
                    </a>
                </span>
            </td>
        </tr>
        </table>
        </html>
        """
        responses.add(responses.GET, HN_JOBS_URL, body=html_response, status=200)

        fetcher = YCFetcher({"name": "YC Jobs"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2

        # First job - has specific role
        assert jobs[0].title == "Applied Researcher (ML)"
        assert jobs[0].company == "Clearspace"
        assert jobs[0].uid == "yc:yc:46848260"
        assert "YC W23" in jobs[0].tags

        # Second job - generic role
        assert jobs[1].company == "CollectWise"
        assert "YC F24" in jobs[1].tags

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            HN_JOBS_URL,
            body="<html><body>No jobs</body></html>",
            status=200,
        )

        fetcher = YCFetcher({"name": "YC Jobs"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(responses.GET, HN_JOBS_URL, body="Error", status=500)

        fetcher = YCFetcher({"name": "YC Jobs"})
        jobs = fetcher.safe_fetch()
        assert jobs == []

    @responses.activate
    def test_pagination(self):
        page1 = """
        <html>
        <tr class="athing submission" id="100">
            <td class="title"><span class="titleline">
                <a href="https://example.com/job1">Company1 (YC S24) Is Hiring</a>
            </span></td>
        </tr>
        <a href="jobs?p=2" class="morelink">More</a>
        </html>
        """
        page2 = """
        <html>
        <tr class="athing submission" id="200">
            <td class="title"><span class="titleline">
                <a href="https://example.com/job2">Company2 (YC W24) Is Hiring</a>
            </span></td>
        </tr>
        </html>
        """
        responses.add(responses.GET, HN_JOBS_URL, body=page1, status=200)
        responses.add(
            responses.GET,
            "https://news.ycombinator.com/jobs?p=2",
            body=page2,
            status=200,
        )

        fetcher = YCFetcher({"name": "YC Jobs", "max_pages": 5})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].uid == "yc:yc:100"
        assert jobs[1].uid == "yc:yc:200"
