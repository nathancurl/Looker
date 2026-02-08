# TikTok/ByteDance Fetcher Integration Patch

This file shows the exact code changes needed to integrate the TikTok/ByteDance fetchers into your existing system.

## Step 1: Add Import to main.py

**File**: `/Users/ncurl/side-projects/job-notification-discord/main.py`

Add this import after line 37 (after the Oracle import):

```python
from fetchers.oracle import OracleFetcher
from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher  # ADD THIS LINE
from filtering import filter_job
```

## Step 2: Add to Fetcher Registry

**File**: `/Users/ncurl/side-projects/job-notification-discord/main.py`

Add to the `FETCHER_REGISTRY` dict (after line 69):

```python
FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
    "newgrad_json": NewGradJSONFetcher,
    # ... existing fetchers ...
    "oracle": OracleFetcher,
    "tiktok": TikTokFetcher,        # ADD THIS LINE
    "bytedance": ByteDanceFetcher,  # ADD THIS LINE
}
```

## Step 3: Add Configuration

**File**: Create or edit your sources configuration file (e.g., `config.json` or `sources.yaml`)

### Option A: JSON Configuration

```json
{
  "sources": {
    "tiktok": [
      {
        "name": "TikTok New Grad",
        "company": "TikTok",
        "brand": "tiktok",
        "keywords": ["new grad", "graduate", "software engineer"],
        "use_selenium": false,
        "poll_interval_seconds": 3600
      }
    ],
    "bytedance": [
      {
        "name": "ByteDance Engineering",
        "company": "ByteDance",
        "keywords": ["engineer", "software"],
        "use_selenium": false,
        "poll_interval_seconds": 3600
      }
    ]
  }
}
```

### Option B: YAML Configuration

```yaml
sources:
  tiktok:
    - name: "TikTok New Grad"
      company: "TikTok"
      brand: "tiktok"
      keywords:
        - "new grad"
        - "graduate"
        - "software engineer"
      use_selenium: false
      poll_interval_seconds: 3600

  bytedance:
    - name: "ByteDance Engineering"
      company: "ByteDance"
      keywords:
        - "engineer"
        - "software"
      use_selenium: false
      poll_interval_seconds: 3600
```

## Complete Diff

### main.py Changes

```diff
--- a/main.py
+++ b/main.py
@@ -37,6 +37,7 @@ from fetchers.yelp import YelpFetcher
 from fetchers.oracle import OracleFetcher
+from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher
 from filtering import filter_job
 from state import StateStore

@@ -68,6 +69,8 @@ FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
     "rivian": RivianFetcher,
     "yelp": YelpFetcher,
     "oracle": OracleFetcher,
+    "tiktok": TikTokFetcher,
+    "bytedance": ByteDanceFetcher,
 }
```

## Verification Steps

### 1. Test Imports

```bash
python3 -c "from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher; print('Import successful')"
```

Expected output: `Import successful`

### 2. Run Test Suite

```bash
python3 test_tiktok_fetcher.py
```

Expected: Should complete without import errors

### 3. Test with Main Application

```bash
# Dry run to test without sending notifications
export DRY_RUN=true
python3 main.py
```

Check logs for:
```
Built X fetcher(s)  # Should include TikTok/ByteDance if configured
```

### 4. Test Specific Source

If your app supports source-specific testing:

```bash
python3 main.py --source "TikTok New Grad" --dry-run
```

## Configuration Examples

### Minimal Configuration (No Selenium)

```yaml
sources:
  tiktok:
    - name: "TikTok"
      company: "TikTok"
      use_selenium: false
```

### Full Configuration (With Selenium)

```yaml
sources:
  tiktok:
    - name: "TikTok New Grad SWE"
      company: "TikTok"
      brand: "tiktok"
      keywords:
        - "new grad"
        - "graduate"
        - "software engineer"
        - "SWE"
      use_selenium: true
      poll_interval_seconds: 3600
      enabled: true
```

### Multiple TikTok Sources

```yaml
sources:
  tiktok:
    - name: "TikTok New Grad"
      company: "TikTok"
      keywords: ["new grad", "graduate"]
      use_selenium: true
      poll_interval_seconds: 3600

    - name: "TikTok Internships"
      company: "TikTok"
      keywords: ["intern", "internship"]
      use_selenium: true
      poll_interval_seconds: 7200

  bytedance:
    - name: "ByteDance Engineering"
      company: "ByteDance"
      keywords: ["engineer"]
      use_selenium: false
      poll_interval_seconds: 3600
```

## Expected Behavior

### Without Selenium

```log
[INFO] Built 15 fetcher(s)
[INFO] TikTok New Grad: fetched 0 jobs
[WARNING] TikTok New Grad: no jobs found. The page may be JavaScript-rendered. Consider setting use_selenium=true in config for better results.
```

This is **expected** - the pages require JavaScript rendering.

### With Selenium (Recommended)

```log
[INFO] Built 15 fetcher(s)
[INFO] TikTok New Grad: found 12 jobs from HTML patterns
[INFO] TikTok New Grad: fetched 12 jobs
[INFO] Sent 3 new notification(s), total seen: 245
```

### Rate Limited

```log
[WARNING] TikTok New Grad: request timed out. The site may have bot detection. Try using selenium or check rate limits.
[INFO] TikTok New Grad: fetched 0 jobs
```

If you see this, increase `poll_interval_seconds` to 3600+ (1 hour).

## Troubleshooting

### "ModuleNotFoundError: No module named 'fetchers.tiktok'"

**Cause**: File not in correct location
**Fix**: Ensure `/Users/ncurl/side-projects/job-notification-discord/fetchers/tiktok.py` exists

```bash
ls -la fetchers/tiktok.py
```

### "NameError: name 'TikTokFetcher' is not defined"

**Cause**: Import not added to main.py
**Fix**: Add the import line from Step 1 above

### "KeyError: 'tiktok' in FETCHER_REGISTRY"

**Cause**: Not added to registry
**Fix**: Add to FETCHER_REGISTRY as shown in Step 2

### All Jobs Filtered Out

**Cause**: Keywords too restrictive or title parsing issues
**Fix**:
1. Check filter configuration
2. Review keywords
3. Check logs for filtered job titles

### 0 Jobs Found

**Cause**: JavaScript not rendered
**Fix**: Enable Selenium in config:

```yaml
use_selenium: true
```

## Performance Tuning

### Recommended Intervals

```yaml
# Without Selenium (fast but may return 0 jobs)
poll_interval_seconds: 3600  # 1 hour

# With Selenium (slower but more reliable)
poll_interval_seconds: 7200  # 2 hours
```

### Caching (Advanced)

If you have many sources, consider caching:

```python
# In your fetcher wrapper
from functools import lru_cache
import time

@lru_cache(maxsize=100)
def fetch_with_cache(source_key, timestamp):
    # timestamp rounded to hour ensures hourly refresh
    # actual fetching logic here
    pass

# Use rounded timestamp
hourly_timestamp = int(time.time() // 3600)
jobs = fetch_with_cache(source.name, hourly_timestamp)
```

## Rollback Instructions

If you need to remove the integration:

### 1. Remove from main.py

```diff
--- a/main.py
+++ b/main.py
@@ -37,7 +37,6 @@ from fetchers.yelp import YelpFetcher
 from fetchers.oracle import OracleFetcher
-from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher
 from filtering import filter_job

@@ -69,8 +68,6 @@ FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
     "yelp": YelpFetcher,
     "oracle": OracleFetcher,
-    "tiktok": TikTokFetcher,
-    "bytedance": ByteDanceFetcher,
 }
```

### 2. Remove from Configuration

Delete or comment out the `tiktok:` and `bytedance:` sections from your config file.

### 3. Optionally Remove Files

```bash
rm fetchers/tiktok.py
rm test_tiktok_fetcher.py
rm config_example_tiktok.yaml
rm TIKTOK_*.md
```

## Next Steps After Integration

1. Monitor logs for first 24 hours
2. Adjust `poll_interval_seconds` based on rate limits
3. Enable Selenium if getting 0 jobs
4. Fine-tune keywords for better filtering
5. Consider using job aggregators as primary source

## Questions?

See the full documentation:
- **Main README**: `TIKTOK_FETCHER_README.md`
- **API Details**: `TIKTOK_API_STRUCTURE.md`
- **Integration Guide**: `TIKTOK_INTEGRATION_GUIDE.md`
- **Summary**: `TIKTOK_FETCHER_SUMMARY.md`

---

**Integration Status**: Ready for deployment
**Testing**: Completed with test suite
**Documentation**: Complete
