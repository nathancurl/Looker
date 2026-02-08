# JPMorgan Chase Job Fetcher

A custom fetcher for JPMorgan Chase jobs using their Oracle Cloud HCM API.

## Overview

JPMorgan Chase uses **Oracle Fusion HCM** (Human Capital Management) for their recruitment portal. The fetcher accesses their public REST API to retrieve job requisitions in JSON format.

### Key Information

- **Career Site**: https://careers.jpmorgan.com (redirects to https://www.jpmorganchase.com/careers)
- **Job Portal**: https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions
- **API Endpoint**: `https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions`
- **Site Number**: `CX_1001`

## API Structure

### Base URL
```
https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions
```

### Query Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `onlyData` | Yes | Return only data (no metadata) | `true` |
| `expand` | No | Expand related fields | `requisitionList.secondaryLocations` |
| `finder` | Yes | Search criteria | `findReqs;siteNumber=CX_1001,keyword=software` |
| `limit` | No | Results per page | `100` (default: 25) |
| `offset` | No | Pagination offset | `0` |

### Finder Syntax

The `finder` parameter uses a special Oracle Cloud syntax:

```
findReqs;siteNumber=CX_1001,keyword=software engineer,facetsList=CATEGORIES;CACATEGORY=Software Engineering
```

Components:
- `findReqs` - The finder operation name
- `siteNumber=CX_1001` - Required site identifier
- `keyword=<search_term>` - Optional keyword search
- `facetsList=CATEGORIES;CACATEGORY=<category>` - Optional category filter

### Response Structure

The API returns a unique structure where job listings are nested within a search result wrapper:

```json
{
  "items": [
    {
      "SearchId": 1,
      "Keyword": "software engineer",
      "TotalJobsCount": 1639,
      "requisitionList": [
        {
          "Id": "210694987",
          "Title": "Software Engineer II - Java Developer",
          "PostedDate": "2026-02-04",
          "PrimaryLocation": "Hyderabad, Telangana, India",
          "PrimaryLocationCountry": "IN",
          "JobFamily": "Software Engineering",
          "JobFunction": "Technology",
          "ShortDescriptionStr": "Design and deliver...",
          "secondaryLocations": []
        }
      ],
      "categoriesFacet": [...],
      "locationsFacet": [...],
      "postingDatesFacet": [...]
    }
  ],
  "count": 1,
  "hasMore": false,
  "limit": 25,
  "offset": 0
}
```

### Job Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `Id` | string | Unique requisition ID |
| `Title` | string | Job title |
| `PostedDate` | string | Posting date (YYYY-MM-DD) |
| `PrimaryLocation` | string | Main work location |
| `PrimaryLocationCountry` | string | Country code (US, GB, IN, etc.) |
| `JobFamily` | string | Job category (e.g., "Software Engineering") |
| `JobFunction` | string | Function area (e.g., "Technology") |
| `ShortDescriptionStr` | string | Brief job description |
| `PostingEndDate` | string/null | Expiration date |
| `secondaryLocations` | array | Additional work locations |

### Job URL Pattern

Job URLs follow this format:
```
https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{Id}
```

Example:
```
https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210694987
```

## Available Facets (Filters)

The API supports filtering by:

1. **Categories** (26 options):
   - Software Engineering
   - Predictive Science
   - Architecture
   - Product Development
   - Product Management
   - Data & Analytics
   - etc.

2. **Locations** (40+ options):
   - United States
   - India
   - United Kingdom
   - Specific states (NY, NJ, CA, TX, etc.)
   - Specific cities

3. **Posting Dates**:
   - Less than 7 days
   - Less than 30 days
   - Greater than 30 days

4. **Job Functions** (26+ titles):
   - Technology
   - Data & Analytics
   - Product
   - Client Management
   - etc.

5. **Work Locations** (40+ facilities):
   - Specific office buildings and campuses

6. **Workplace Types**:
   - On-site (currently all 7,331 positions)

## Rate Limits

- **No explicit rate limiting** observed in API responses
- Standard HTTP retry logic is sufficient
- Typical response time: 1-3 seconds for 100 results
- Recommend staying under 60 requests per minute

## Usage

### Basic Configuration

Add to your `config.json` under `"sources"`:

```json
{
  "sources": {
    "jpmorgan_software": {
      "fetcher": "jpmorgan",
      "name": "JPMorgan-SoftwareEngineers",
      "search_keyword": "software engineer",
      "limit": 100
    }
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `fetcher` | string | **required** | Must be `"jpmorgan"` |
| `name` | string | recommended | Display name for the source |
| `search_keyword` | string | `"software engineer"` | Keyword to search for |
| `limit` | integer | `100` | Results per API request (max: 100) |
| `category_filter` | string | `""` | Filter by job family (e.g., "Software Engineering") |

### Example Configurations

#### New Grad Software Engineers
```json
{
  "jpmorgan_newgrad": {
    "fetcher": "jpmorgan",
    "name": "JPMorgan-NewGrads",
    "search_keyword": "software engineer",
    "limit": 100
  }
}
```

Note: JPMorgan typically doesn't use "new grad" terminology. Instead, look for:
- "Associate Software Engineer"
- "Entry Level" positions
- "Analyst" roles
- "Early Career" programs

#### Early Career Positions
```json
{
  "jpmorgan_early_career": {
    "fetcher": "jpmorgan",
    "name": "JPMorgan-EarlyCareers",
    "search_keyword": "early career",
    "limit": 100
  }
}
```

#### Software Engineering Category (No Keyword)
```json
{
  "jpmorgan_swe_all": {
    "fetcher": "jpmorgan",
    "name": "JPMorgan-AllSoftwareEngineering",
    "search_keyword": "",
    "category_filter": "Software Engineering",
    "limit": 100
  }
}
```

#### Associate Software Engineers
```json
{
  "jpmorgan_associate": {
    "fetcher": "jpmorgan",
    "name": "JPMorgan-Associates",
    "search_keyword": "associate software",
    "limit": 100
  }
}
```

### Add Routing

Update the `"routing"` section in `config.json`:

```json
{
  "routing": {
    "jpmorgan": "DISCORD_WEBHOOK_JPMORGAN"
  }
}
```

### Set Webhook URL

Add to your `.env` file:

```bash
DISCORD_WEBHOOK_JPMORGAN=https://discord.com/api/webhooks/your-webhook-id/your-webhook-token
```

## Testing

### Run Test Script

```bash
poetry run python test_jpmorgan_fetcher.py
```

This will test:
1. Software engineer search (expects ~1,600+ results)
2. Early career search (expects ~70 results)
3. Category filter by "Software Engineering" (expects ~1,000+ results)
4. New grad search variations (searches: "new grad", "entry level", "associate software", "analyst")

### Manual API Testing

Use the debug script to inspect raw API responses:

```bash
poetry run python debug_jpmorgan_api.py
```

### Example cURL Request

```bash
curl -G "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions" \
  --data-urlencode "onlyData=true" \
  --data-urlencode "expand=requisitionList.secondaryLocations" \
  --data-urlencode "finder=findReqs;siteNumber=CX_1001,keyword=software engineer" \
  --data-urlencode "limit=5" \
  --data-urlencode "offset=0" \
  -H "User-Agent: Mozilla/5.0"
```

## Search Tips for New Grads

JPMorgan Chase doesn't heavily use "new grad" terminology in job titles. Instead, search for:

1. **Title Keywords**:
   - "Associate Software Engineer"
   - "Software Engineer II" (entry/mid-level)
   - "Analyst"
   - "Early Career"
   - "Entry Level"

2. **Programs**:
   - "Technology Analyst Program"
   - "Software Engineer Program"
   - "Early Careers"

3. **Filtering Strategy**:
   - Search broadly with "software engineer"
   - Filter results in your application layer by:
     - Excluding titles with "Senior", "Staff", "Principal", "Lead"
     - Looking for level indicators like "II", "Associate"
     - Checking posting dates (recent postings for campus hiring cycles)

## Current Statistics

As of February 2026:
- **Total Jobs**: ~7,331
- **Software Engineering Positions**: ~1,052
- **Software Engineer Keyword Search**: ~1,639
- **Early Career Positions**: ~70
- **Technology Jobs**: ~1,227

Most common locations:
- United States (904)
- India (291)
- United Kingdom (279)

## Implementation Details

### Fetcher Class

The `JPMorganFetcher` class is located at:
```
fetchers/jpmorgan.py
```

Key methods:
- `__init__(source_config)` - Initialize with configuration
- `fetch()` - Retrieve jobs from API
- `safe_fetch()` - Wrapped fetch with error handling

### Dependencies

- `requests` - HTTP client
- `tenacity` - Retry logic (via `resilient_get`)
- `pydantic` - Job model validation

### Error Handling

The fetcher uses `resilient_get()` which provides:
- 3 retry attempts
- Exponential backoff (2-15 seconds)
- Automatic retry on connection errors and timeouts
- Raises exception on 5xx server errors

## Troubleshooting

### No Results Returned

1. Check if the keyword is too specific
2. Try broader search terms like "software" or "engineer"
3. Use category filters instead of keywords
4. Check API response with debug script

### API Changes

Oracle Cloud HCM API endpoints may change. If the fetcher stops working:

1. Check the JPMorgan careers site for the new job portal URL
2. Inspect network traffic in browser DevTools
3. Look for API calls to `oraclecloud.com` domains
4. Update the `ORACLE_API_BASE` constant if needed

### Rate Limiting

If you encounter rate limiting:
1. Reduce `limit` parameter
2. Add delays between requests
3. Cache results to minimize API calls

## Future Enhancements

Potential improvements:
1. **Multiple keyword support** - Search for multiple terms in one configuration
2. **Location filtering** - Filter by US states or specific cities
3. **Date range filtering** - Only fetch jobs posted within X days
4. **Level detection** - Automatic classification of entry/mid/senior positions
5. **Department filtering** - Filter by specific business units

## Resources

- **API Documentation**: Not publicly available (reverse-engineered)
- **Oracle Cloud HCM**: https://www.oracle.com/human-capital-management/
- **JPMorgan Careers**: https://www.jpmorganchase.com/careers

## License

This fetcher is part of the job-notification-discord project and follows the same license.
