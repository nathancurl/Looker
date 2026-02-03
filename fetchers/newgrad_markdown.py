"""Fetcher for markdown-based new-grad repos (speedyapply, zapplyjobs)."""

import hashlib
import logging
import re

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class NewGradMarkdownFetcher(BaseFetcher):
    source_group = "newgrad"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._owner = source_config["owner"]
        self._repo = source_config["repo"]
        self._branch = source_config.get("branch", "main")
        self._files = source_config.get("files", [])

    def fetch(self) -> list[Job]:
        jobs = []
        for filename in self._files:
            url = (
                f"https://raw.githubusercontent.com/{self._owner}/{self._repo}"
                f"/{self._branch}/{filename}"
            )
            resp = resilient_get(url)
            resp.raise_for_status()
            jobs.extend(self._parse_markdown_table(resp.text, filename))
        return jobs

    def _parse_markdown_table(self, text: str, filename: str) -> list[Job]:
        """Parse markdown tables with | delimiters into Job objects."""
        jobs = []
        lines = text.strip().split("\n")
        header_indices = {}
        in_table = False

        for line in lines:
            line = line.strip()
            if not line.startswith("|"):
                in_table = False
                header_indices = {}
                continue

            cells = [c.strip() for c in line.split("|")[1:-1]]

            # Detect separator row (e.g., |---|---|---|)
            if all(re.match(r"^[-:]+$", c) for c in cells if c):
                in_table = True
                continue

            # Detect header row
            if not in_table:
                for i, cell in enumerate(cells):
                    cell_lower = cell.lower()
                    if "company" in cell_lower:
                        header_indices["company"] = i
                    elif "role" in cell_lower or "position" in cell_lower or "title" in cell_lower:
                        header_indices["title"] = i
                    elif "location" in cell_lower:
                        header_indices["location"] = i
                    elif "link" in cell_lower or "apply" in cell_lower or "application" in cell_lower:
                        header_indices["link"] = i
                    elif "date" in cell_lower or "posted" in cell_lower:
                        header_indices["date"] = i
                continue

            if not in_table or not header_indices:
                continue

            # Parse data row
            company = self._extract_text(cells, header_indices.get("company"))
            title = self._extract_text(cells, header_indices.get("title"))
            location = self._extract_text(cells, header_indices.get("location"))
            link_cell = cells[header_indices["link"]] if header_indices.get("link") is not None and header_indices["link"] < len(cells) else ""
            apply_url = self._extract_url(link_cell)

            if not apply_url or not company:
                continue

            uid = Job.generate_uid(self.source_group, url=apply_url)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title or "Unknown Position",
                    company=company,
                    location=location,
                    url=apply_url,
                )
            )

        return jobs

    @staticmethod
    def _extract_text(cells: list[str], index: int | None) -> str:
        """Extract plain text from a cell, stripping markdown links."""
        if index is None or index >= len(cells):
            return ""
        cell = cells[index]
        # Strip markdown links: [text](url) -> text
        cell = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell)
        # Strip HTML tags
        cell = re.sub(r"<[^>]+>", "", cell)
        return cell.strip()

    @staticmethod
    def _extract_url(cell: str) -> str:
        """Extract URL from a markdown cell."""
        # Try markdown link first: [text](url)
        match = re.search(r"\[([^\]]*)\]\(([^)]+)\)", cell)
        if match:
            return match.group(2)
        # Try bare URL
        match = re.search(r"https?://[^\s<>\"']+", cell)
        if match:
            return match.group(0)
        return ""
