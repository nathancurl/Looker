"""Tests for Google fetcher."""

import responses

from fetchers.google import GoogleFetcher

FEED_URL = "https://www.google.com/about/careers/applications/jobs/feed.xml"


class TestGoogleFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture_text):
        fixture = load_fixture_text("google_response.xml")
        responses.add(
            responses.GET,
            FEED_URL,
            body=fixture,
            status=200,
            content_type="application/xml",
        )

        fetcher = GoogleFetcher({"name": "Google", "company": "Google"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2

        assert jobs[0].title == "Software Engineer, Backend"
        assert jobs[0].uid == "maang:google:123456"
        assert jobs[0].company == "Google"
        assert jobs[0].location == "Mountain View, CA, US"
        assert "scalable backend" in jobs[0].snippet.lower()

        # YouTube employer is preserved
        assert jobs[1].company == "YouTube"
        assert "San Bruno, CA, US" in jobs[1].location
        assert "New York, NY, US" in jobs[1].location

    @responses.activate
    def test_filters_non_allowed_countries(self, load_fixture_text):
        """Jobs in non-allowed countries are filtered out."""
        xml_with_india = """<?xml version="1.0" encoding="UTF-8"?>
        <jobs>
          <item>
            <id>111</id>
            <title>Engineer</title>
            <employer>Google</employer>
            <description>Test</description>
            <url>https://google.com/jobs/111</url>
            <locations>
              <location>
                <city>Bangalore</city>
                <country>IN</country>
              </location>
            </locations>
          </item>
          <item>
            <id>222</id>
            <title>Developer</title>
            <employer>Google</employer>
            <description>Test</description>
            <url>https://google.com/jobs/222</url>
            <locations>
              <location>
                <city>London</city>
                <country>UK</country>
              </location>
            </locations>
          </item>
        </jobs>"""
        responses.add(
            responses.GET,
            FEED_URL,
            body=xml_with_india,
            status=200,
            content_type="application/xml",
        )

        fetcher = GoogleFetcher({"name": "Google", "company": "Google"})
        jobs = fetcher.fetch()

        # Only UK job should be included
        assert len(jobs) == 1
        assert jobs[0].title == "Developer"
        assert "London" in jobs[0].location

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            FEED_URL,
            body="<?xml version='1.0'?><jobs></jobs>",
            status=200,
            content_type="application/xml",
        )

        fetcher = GoogleFetcher({"name": "Google", "company": "Google"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            FEED_URL,
            body="Server Error",
            status=404,
        )

        fetcher = GoogleFetcher({"name": "Google", "company": "Google"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
