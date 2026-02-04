#!/usr/bin/env python3
"""Quick test script for Ripplematch fetcher.

Usage:
    poetry run python scripts/test_ripplematch.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.ripplematch import RipplematchFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Test Ripplematch fetcher."""
    logger.info("Testing Ripplematch fetcher...")

    config = {
        "name": "Ripplematch",
        "max_scrolls": 5,  # Limit scrolls for faster testing
        "headless": True,
    }

    fetcher = RipplematchFetcher(config)

    try:
        jobs = fetcher.fetch()
        logger.info("Successfully fetched %d jobs", len(jobs))

        if jobs:
            logger.info("Sample jobs:")
            for job in jobs[:5]:  # Show first 5
                logger.info(
                    "  - %s at %s (%s)",
                    job.title,
                    job.company,
                    job.url,
                )
        else:
            logger.warning("No jobs found - this may indicate a parsing issue")

    except ImportError as e:
        logger.error("Selenium not installed: %s", e)
        logger.error("Install with: poetry install --extras selenium")
        return 1
    except Exception as e:
        logger.error("Error fetching jobs: %s", e, exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
