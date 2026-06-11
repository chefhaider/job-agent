"""
Save results to CSV, load target URLs, print summaries.
"""

import csv
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from parser import JobListing


# ─────────────────────────────────────────────────────────────
# Target URL model
# ─────────────────────────────────────────────────────────────

@dataclass
class TargetURL:
    search_query: str
    url: str


# ─────────────────────────────────────────────────────────────
# Load target URLs from CSV
# ─────────────────────────────────────────────────────────────

def load_target_urls(filepath: str) -> list[TargetURL]:
    """
    Load target URLs from a CSV file.
    Expected columns: search_query, url
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"❌ Target URLs file not found: {filepath}")

    targets: list[TargetURL] = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate headers
        if not reader.fieldnames:
            raise ValueError(f"❌ Empty CSV file: {filepath}")

        headers = [h.strip().lower() for h in reader.fieldnames]
        if "url" not in headers:
            raise ValueError(
                f"❌ CSV must have 'url' column.\n"
                f"   Found columns: {reader.fieldnames}\n"
                f"   Expected: search_query, url"
            )

        for row_num, row in enumerate(reader, start=2):
            url = row.get("url", "").strip()
            query = row.get("search_query", "").strip()

            if not url:
                print(f"  ⚠️  Row {row_num}: empty URL, skipping")
                continue

            if not url.startswith("http"):
                print(f"  ⚠️  Row {row_num}: invalid URL '{url}', skipping")
                continue

            # Auto-generate query name from URL if not provided
            if not query:
                import re
                match = re.search(r"keywords=([^&]+)", url)
                if match:
                    from urllib.parse import unquote_plus
                    query = unquote_plus(match.group(1))
                else:
                    query = f"Search #{row_num - 1}"

            targets.append(TargetURL(search_query=query, url=url))

    if not targets:
        raise ValueError(f"❌ No valid URLs found in {filepath}")

    print(f"\n  📋 Loaded {len(targets)} target URLs from {filepath}")
    for i, t in enumerate(targets, 1):
        print(f"     {i}. {t.search_query}")

    return targets


# ─────────────────────────────────────────────────────────────
# Save to CSV
# ─────────────────────────────────────────────────────────────

def save_to_csv(
    jobs: list[JobListing],
    filename: Optional[str] = None,
    output_dir: str = "output",
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"linkedin_jobs_{timestamp}.csv"

    if not filename.endswith(".csv"):
        filename += ".csv"

    filepath = os.path.join(output_dir, filename)

    if not jobs:
        print("⚠️  No jobs to save.")
        return filepath

    fieldnames = ["search_query", "job_title", "company_name", "job_url"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.to_dict())

    print(f"\n📄 CSV saved → {filepath}  ({len(jobs)} jobs)")
    return filepath


# ─────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────

def print_jobs_summary(jobs: list[JobListing]):
    print("\n" + "=" * 65)
    print(f"  📊 TOTAL EXTRACTED: {len(jobs)} JOBS")
    print("=" * 65)

    # Group by search query
    grouped: dict[str, list[JobListing]] = {}
    for job in jobs:
        key = job.search_query or "Unknown"
        grouped.setdefault(key, []).append(job)

    for query, query_jobs in grouped.items():
        print(f"\n  🔍 {query} ({len(query_jobs)} jobs)")
        print(f"  {'─' * 55}")
        for i, job in enumerate(query_jobs, 1):
            print(f"    {i:>3}. {job.job_title}")
            print(f"         {job.company_name}")
            print(f"         {job.job_url}")

    print("\n" + "=" * 65)
    companies = set(j.company_name for j in jobs if j.company_name)
    queries = set(j.search_query for j in jobs if j.search_query)
    print(f"  📈 Searches run:      {len(queries)}")
    print(f"     Total jobs:        {len(jobs)}")
    print(f"     Unique companies:  {len(companies)}")
    print("=" * 65)