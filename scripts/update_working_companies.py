#!/usr/bin/env python3
"""Generate WORKING_COMPANIES.md from validation results.

Usage:
    python scripts/validate_sources.py --json > test_results.json
    python scripts/update_working_companies.py test_results.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_working_companies.py test_results.json")
        return 1

    results_path = Path(sys.argv[1])
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        return 1

    with open(results_path) as f:
        data = json.load(f)

    # Group results by platform
    by_platform = defaultdict(lambda: {"passed": [], "failed": [], "warnings": [], "skipped": []})

    for result in data["results"]:
        source_type = result["source_type"]
        status = result["status"]
        by_platform[source_type][status].append(result)

    # Generate markdown
    md_lines = []
    md_lines.append("# Working Companies Status Report")
    md_lines.append("")
    md_lines.append(f"**Last Updated**: {data['timestamp']}")
    md_lines.append("")

    # Summary
    summary = data["summary"]
    md_lines.append("## Summary Statistics")
    md_lines.append("")
    md_lines.append(f"- **Total Companies Tested**: {summary['total']}")
    md_lines.append(f"- **Working**: {summary['passed']} ({summary['success_rate']}%)")
    md_lines.append(f"- **Failing**: {summary['failed']}")
    md_lines.append(f"- **Warnings**: {summary['warnings']}")
    md_lines.append(f"- **Skipped**: {summary['skipped']}")
    md_lines.append("")

    # Platform breakdown table
    md_lines.append("## Platform Breakdown")
    md_lines.append("")
    md_lines.append("| Platform | Total | Working | Failing | Success Rate |")
    md_lines.append("|----------|-------|---------|---------|--------------|")

    platform_stats = []
    for platform in sorted(by_platform.keys()):
        stats = by_platform[platform]
        total = len(stats["passed"]) + len(stats["failed"]) + len(stats["warnings"])
        working = len(stats["passed"]) + len(stats["warnings"])
        failing = len(stats["failed"])
        success_rate = (working / total * 100) if total > 0 else 0

        platform_stats.append((platform, total, working, failing, success_rate))
        md_lines.append(
            f"| {platform} | {total} | {working} | {failing} | {success_rate:.1f}% |"
        )

    md_lines.append("")

    # Detailed per-platform sections
    md_lines.append("## Detailed Results by Platform")
    md_lines.append("")

    for platform in sorted(by_platform.keys()):
        stats = by_platform[platform]
        total = len(stats["passed"]) + len(stats["failed"]) + len(stats["warnings"])

        md_lines.append(f"### {platform.upper()} ({total} companies)")
        md_lines.append("")

        # Working companies
        if stats["passed"]:
            md_lines.append(f"#### ✅ Working ({len(stats['passed'])})")
            md_lines.append("")
            for result in sorted(stats["passed"], key=lambda x: x["name"]):
                md_lines.append(f"- **{result['name']}**: {result['message']}")
            md_lines.append("")

        # Warnings
        if stats["warnings"]:
            md_lines.append(f"#### ⚠️ Warnings ({len(stats['warnings'])})")
            md_lines.append("")
            for result in sorted(stats["warnings"], key=lambda x: x["name"]):
                md_lines.append(f"- **{result['name']}**: {result['message']}")
            md_lines.append("")

        # Failed companies
        if stats["failed"]:
            md_lines.append(f"#### ❌ Failing ({len(stats['failed'])})")
            md_lines.append("")
            for result in sorted(stats["failed"], key=lambda x: x["name"]):
                md_lines.append(f"- **{result['name']}**: {result['message']}")
            md_lines.append("")

        # Skipped companies
        if stats["skipped"]:
            md_lines.append(f"#### ⊘ Skipped ({len(stats['skipped'])})")
            md_lines.append("")
            for result in sorted(stats["skipped"], key=lambda x: x["name"]):
                md_lines.append(f"- **{result['name']}**: {result['message']}")
            md_lines.append("")

    # Notes section
    md_lines.append("## Notes")
    md_lines.append("")
    md_lines.append("### Platform Migrations")
    md_lines.append("")
    md_lines.append(
        "If a company returns HTTP 404, they may have migrated to a different ATS platform. "
        "Check their careers page to find the new platform and update config.json accordingly."
    )
    md_lines.append("")
    md_lines.append("### Removal Candidates")
    md_lines.append("")
    md_lines.append(
        "Companies with persistent failures (HTTP 403, invalid tokens, DNS errors) should be "
        "investigated and potentially removed from config.json if they are no longer hiring "
        "or have changed their job board system."
    )
    md_lines.append("")
    md_lines.append("### Zero Jobs")
    md_lines.append("")
    md_lines.append(
        "Companies showing 0 jobs are not necessarily broken - they may simply not be hiring "
        "at the moment. These are marked as working but should be monitored."
    )
    md_lines.append("")

    # Write to file
    output_path = Path(__file__).parent.parent / "WORKING_COMPANIES.md"
    with open(output_path, "w") as f:
        f.write("\n".join(md_lines))

    print(f"✓ Generated {output_path}")
    print(f"  Total: {summary['total']} | Working: {summary['passed']} | Failed: {summary['failed']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
