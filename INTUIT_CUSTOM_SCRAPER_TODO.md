# Intuit Custom Scraper - Implementation Needed

## Current Status
Intuit has been **removed** from both iCIMS and SmartRecruiters configurations as part of duplicate cleanup (2026-02-08).

## Reason
Intuit uses a custom careers site that requires a specialized scraper:
- **URL**: https://jobs.intuit.com/search-jobs
- **ATS**: Custom (not a standard platform like Greenhouse, Lever, Ashby, etc.)

## Implementation Required
To add Intuit back to the job scraper, you'll need to:

1. **Create a custom fetcher** in `fetchers/intuit.py` similar to other custom fetchers:
   - `fetchers/jpmorgan.py`
   - `fetchers/oracle.py`
   - `fetchers/qualcomm.py`
   - `fetchers/rivian.py`

2. **Research the API/scraping approach**:
   - Check if they have a public jobs API
   - If not, use Selenium/browser automation
   - Parse job listings from https://jobs.intuit.com/search-jobs

3. **Add config entry** to `config.json`:
   ```json
   "intuit": [
     {
       "name": "Intuit",
       "company": "Intuit",
       "base_url": "https://jobs.intuit.com/search-jobs"
     }
   ]
   ```

4. **Add routing** in config.json:
   ```json
   "routing": {
     ...
     "intuit": "DISCORD_WEBHOOK_CUSTOM"
   }
   ```

5. **Register the fetcher** in `main.py` or fetcher registry

## Priority
**Medium** - Intuit is a major tech company (TurboTax, QuickBooks, Mailchimp) with entry-level SWE positions, but not urgent.
