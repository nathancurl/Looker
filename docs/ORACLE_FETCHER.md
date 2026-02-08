# Oracle Job Fetcher

This document provides comprehensive information about the Oracle job fetcher, including API structure, usage instructions, and configuration examples.

## Overview

Oracle uses **Oracle Recruiting Cloud** (formerly Taleo Enterprise) as their applicant tracking system. This is Oracle's own proprietary solution built on Oracle Fusion Cloud infrastructure. The fetcher interfaces with their HCM (Human Capital Management) REST API.

### Career Site
- **URL**: https://careers.oracle.com
- **Platform**: Oracle Recruiting Cloud / Oracle HCM
- **Total Job Count**: ~4,000+ active positions (as of Feb 2026)

## API Structure

### Base Endpoint
```
https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions
```

### Authentication
- **Type**: Public API (no authentication required)
- **Headers**: `Accept: application/json`

### Request Format

The API uses a **finder pattern** where search parameters are encoded in a semicolon-delimited format:

```
GET /hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber=CX_1,keyword=software,offset=0,limit=25
```

#### Key Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `onlyData` | Yes | Set to `true` to return only data (no metadata) |
| `expand` | No | Comma-separated list of fields to expand (e.g., `requisitionList.secondaryLocations`) |
| `finder` | Yes | Search query string in format: `findReqs;param1=value1,param2=value2` |

#### Finder Parameters

The `finder` parameter uses this format: `findReqs;siteNumber=CX_1,keyword=value,location=value,offset=N,limit=M`

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `siteNumber` | Yes | Oracle's site identifier | `CX_1` |
| `keyword` | No | Search term for job title/description | `software engineer` |
| `location` | No | Location filter | `United States` |
| `offset` | No | Pagination offset (must be in finder!) | `0`, `25`, `50` |
| `limit` | No | Results per page (must be in finder!) | `25` (max and default) |

**Important**: The `offset` and `limit` parameters MUST be included in the finder string, not as separate query parameters. The API ignores them if passed separately.

### Response Format

```json
{
  "items": [
    {
      "SearchId": 1,
      "Keyword": "software engineer",
      "TotalJobsCount": 1737,
      "Offset": 0,
      "Limit": 25,
      "requisitionList": [
        {
          "Id": "313051",
          "Title": "Principal Applications Engineer",
          "PostedDate": "2025-10-27",
          "PrimaryLocation": "Redwood City, CA, United States",
          "PrimaryLocationCountry": "US",
          "ShortDescriptionStr": "Principal Applications Engineer, SCM Cloud",
          "HotJobFlag": false,
          "TrendingFlag": true,
          "WorkplaceType": "",
          "secondaryLocations": []
        }
      ]
    }
  ]
}
```

#### Key Response Fields

**Search Metadata** (in `items[0]`):
- `TotalJobsCount`: Total number of jobs matching the query
- `Offset`: Current pagination offset
- `Limit`: Number of results returned (always 25)

**Job Fields** (in `items[0].requisitionList[]`):
- `Id`: Unique job requisition ID
- `Title`: Job title
- `PostedDate`: Date posted (format: `YYYY-MM-DD`)
- `PrimaryLocation`: Primary work location
- `PrimaryLocationCountry`: ISO country code
- `ShortDescriptionStr`: Brief job description
- `HotJobFlag`: Boolean indicating if it's a "hot job"
- `TrendingFlag`: Boolean indicating if it's trending
- `WorkplaceType`: Remote/hybrid/on-site indicator (often empty)
- `secondaryLocations`: Array of additional work locations

### Pagination

- **Results per page**: Fixed at 25 jobs
- **Maximum offset**: Varies by query (equal to `TotalJobsCount`)
- **Implementation**: Increment offset by 25 for each page

Example pagination:
```
Page 1: offset=0  (jobs 1-25)
Page 2: offset=25 (jobs 26-50)
Page 3: offset=50 (jobs 51-75)
```

### Rate Limits

Oracle does not publicly document rate limits for their recruiting API. Based on testing:

- **Recommended**: 1 request per 2-3 seconds for sustained scraping
- **Maximum**: No hard limit observed, but be respectful
- **Timeout**: 15 seconds per request (as configured in base fetcher)

The fetcher uses exponential backoff retry logic for failed requests (via `resilient_get`).

## Configuration

### Basic Configuration

Add to your source configuration file:

```yaml
sources:
  - name: Oracle - All Jobs
    fetcher: oracle
    max_jobs: 100
```

### Search by Keyword

Filter for specific roles (e.g., software engineer, new grad):

```yaml
sources:
  - name: Oracle - Software Engineers
    fetcher: oracle
    keyword: software engineer
    max_jobs: 200

  - name: Oracle - New Grads
    fetcher: oracle
    keyword: new grad
    max_jobs: 100
```

### Search by Location

Filter by location:

```yaml
sources:
  - name: Oracle - US Jobs
    fetcher: oracle
    location: United States
    max_jobs: 150
```

### Combined Filters

Combine keyword and location:

```yaml
sources:
  - name: Oracle - US Software Engineers
    fetcher: oracle
    keyword: software engineer
    location: United States
    max_jobs: 200
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | Required | Display name for this source |
| `keyword` | string | `""` | Search term for filtering jobs |
| `location` | string | `""` | Location filter (city, state, country) |
| `max_jobs` | integer | `500` | Maximum number of jobs to fetch |

## Job Data Fields

Each job returned by the fetcher includes:

| Field | Type | Description | Always Present? |
|-------|------|-------------|-----------------|
| `uid` | string | Unique identifier (format: `oracle:{job_id}`) | Yes |
| `source_group` | string | Always `"oracle"` | Yes |
| `source_name` | string | Configured source name | Yes |
| `title` | string | Job title | Yes |
| `company` | string | Always `"Oracle"` | Yes |
| `location` | string | Primary + secondary locations | Yes |
| `remote` | boolean | Detected from location text | Yes |
| `url` | string | Job detail page URL | Yes |
| `snippet` | string | Job description snippet (max 300 chars) | Usually (96%+) |
| `posted_at` | datetime | Date job was posted | Yes (100%) |
| `raw_id` | string | Oracle requisition ID | Yes |
| `tags` | list[string] | Hot Job, Trending, etc. | Sometimes (68%+) |

### Example Job Object

```python
Job(
    uid='oracle:313051',
    source_group='oracle',
    source_name='Oracle - Software Engineers',
    title='Principal Applications Engineer',
    company='Oracle',
    location='Redwood City, CA, United States',
    remote=False,
    url='https://careers.oracle.com/jobs/#en/sites/jobsearch/job/313051',
    snippet='Principal Applications Engineer, SCM Cloud',
    posted_at=datetime(2025, 10, 27, 0, 0),
    raw_id='313051',
    tags=['Hot Job', 'Trending']
)
```

## Usage Examples

### Programmatic Usage

```python
from fetchers.oracle import OracleFetcher

# Basic fetch
config = {
    "name": "Oracle Jobs",
    "keyword": "software engineer",
    "max_jobs": 50
}

fetcher = OracleFetcher(config)
jobs = fetcher.fetch()

for job in jobs:
    print(f"{job.title} - {job.location}")
    print(f"  URL: {job.url}")
    print(f"  Posted: {job.posted_at}")
    print()
```

### Integration with Job Notification System

```python
from fetchers.oracle import OracleFetcher

# Define source configuration
sources = [
    {
        "name": "Oracle - New Grad Software",
        "fetcher": "oracle",
        "keyword": "new grad software",
        "location": "United States",
        "max_jobs": 100,
    },
    {
        "name": "Oracle - Early Career",
        "fetcher": "oracle",
        "keyword": "early career",
        "max_jobs": 100,
    }
]

# Fetch jobs from each source
all_jobs = []
for source_config in sources:
    fetcher = OracleFetcher(source_config)
    jobs = fetcher.safe_fetch()  # Uses error handling
    all_jobs.extend(jobs)

print(f"Fetched {len(all_jobs)} total jobs from Oracle")
```

## Search Keywords for New Grad Positions

Based on testing, these keywords work well for finding new grad/early career positions:

| Keyword | Jobs Found | Notes |
|---------|------------|-------|
| `graduate` | ~140 | Best for international new grad programs |
| `early career` | ~240 | Broader, includes internships and entry-level |
| `entry level` | ~30 | More limited, very specific roles |
| `new grad` | ~10 | Most specific, fewer results |
| `software engineer graduate` | Varies | Combines role and level |

**Recommended approach**: Use multiple sources with different keywords to capture all relevant positions.

```yaml
sources:
  - name: Oracle - Graduates
    fetcher: oracle
    keyword: graduate
    max_jobs: 150

  - name: Oracle - Early Career
    fetcher: oracle
    keyword: early career
    max_jobs: 250
```

## API Quirks and Notes

### 1. Pagination Parameters Must Be in Finder
Unlike typical REST APIs, Oracle's API requires pagination parameters (`offset`, `limit`) to be embedded in the `finder` string, not passed as separate query parameters.

**Wrong** (doesn't work):
```
?finder=findReqs;siteNumber=CX_1&offset=25&limit=25
```

**Correct**:
```
?finder=findReqs;siteNumber=CX_1,offset=25,limit=25
```

### 2. Fixed Page Size
The API always returns exactly 25 results per page, regardless of the `limit` parameter value. Setting `limit=100` still returns 25 jobs.

### 3. Workplace Type Often Empty
The `WorkplaceType` field is frequently empty or contains an empty string, even for remote positions. Remote detection is done via location text analysis instead.

### 4. Tags Are Inconsistent
Not all jobs have tags. About 68% of jobs include at least one tag (Hot Job, Trending, etc.).

### 5. Job URLs Use Fragment Routing
Job detail URLs use hash-based routing:
```
https://careers.oracle.com/jobs/#en/sites/jobsearch/job/313051
```

This makes them suitable for direct linking but may complicate scraping if you need full job details.

### 6. Secondary Locations
Some jobs have multiple work locations. These are returned in the `secondaryLocations` array when you include `requisitionList.secondaryLocations` in the expand parameter.

## Testing

A comprehensive test suite is included in `test_oracle_fetcher.py`:

```bash
# Run the full test suite
poetry run python test_oracle_fetcher.py

# Expected output: 6/6 tests passed
```

### Test Coverage

1. **Basic Fetch**: Validates core fetching functionality
2. **Software Engineer Search**: Tests keyword filtering
3. **New Grad Search**: Tests multiple new grad keywords
4. **Location Filter**: Tests location-based filtering
5. **Pagination**: Verifies correct pagination (150+ jobs, no duplicates)
6. **Data Quality**: Checks field completeness and correctness

## Troubleshooting

### No Jobs Returned
- Check that `siteNumber=CX_1` is included in the finder
- Verify the keyword/location combination returns results on careers.oracle.com
- Try broadening your search terms

### Duplicate Jobs in Results
- Ensure offset/limit are in the finder string (not query params)
- Check that offset is being incremented correctly (by 25 per page)

### Rate Limiting Errors
- Add delays between requests (2-3 seconds recommended)
- Reduce `max_jobs` to fetch fewer results
- The base fetcher includes automatic retry with exponential backoff

### Parse Errors
- Check that the API response structure hasn't changed
- Enable debug logging to see raw API responses
- Verify job requisitions have required fields (Id, Title)

## Performance

Based on testing:

- **Fetch time**: ~1.5 seconds per page (25 jobs)
- **150 jobs**: ~10-15 seconds
- **500 jobs**: ~30-40 seconds

Performance varies based on network latency and Oracle's API response times.

## Future Enhancements

Potential improvements for the fetcher:

1. **Category/Facet Filtering**: The API supports category facets (e.g., Engineering, Sales) but this isn't currently exposed
2. **Posting Date Filtering**: Filter jobs posted within last N days
3. **Job Family Filtering**: Filter by Oracle's internal job family taxonomy
4. **Full Job Details**: Fetch complete job descriptions by making additional API calls
5. **Geographic Filtering**: More precise location filtering (city, state, country)

## Related Documentation

- Oracle Recruiting Cloud: https://docs.oracle.com/en/cloud/saas/recruiting/
- Oracle HCM REST API: https://docs.oracle.com/en/cloud/saas/human-resources/

## License

This fetcher is part of the job-notification-discord project and is provided as-is for educational purposes.

## Support

For issues or questions:
- Check the test suite for examples
- Review this documentation
- Check Oracle's careers site for API changes
- Open an issue on the project repository
