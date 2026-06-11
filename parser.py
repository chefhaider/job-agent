"""
HTML parser for LinkedIn job listings.
Extracts: Job Title, Company Name, Job URL.
"""

from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
import re


def _best_parser() -> str:
    for parser in ("lxml", "html5lib", "html.parser"):
        try:
            BeautifulSoup("<p>test</p>", parser)
            return parser
        except Exception:
            continue
    return "html.parser"


BS4_PARSER = _best_parser()


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, BS4_PARSER)


@dataclass
class JobListing:
    job_title: str = ""
    company_name: str = ""
    job_url: str = ""
    search_query: str = ""       # ← tracks which search produced this job

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"  Title:   {self.job_title}\n"
            f"  Company: {self.company_name}\n"
            f"  URL:     {self.job_url}"
        )


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_job_card(
    card,
    base_url: str = "https://www.linkedin.com",
    search_query: str = "",
) -> Optional[JobListing]:
    job = JobListing(search_query=search_query)

    try:
        # ── Job Title ────────────────────────────────────────
        title_el = card.select_one(
            "a.job-card-list__title--link span,"
            "a.job-card-container__link span,"
            ".job-card-list__title,"
            "h3.base-search-card__title,"
            "a[data-tracking-control-name] span"
        )
        if title_el:
            job.job_title = clean_text(title_el.get_text())

        if not job.job_title:
            link_el = card.select_one("a[aria-label]")
            if link_el:
                job.job_title = clean_text(link_el.get("aria-label", ""))

        # ── Job URL ──────────────────────────────────────────
        link_el = card.select_one(
            "a.job-card-list__title--link,"
            "a.job-card-container__link,"
            "a.base-card__full-link,"
            "a[data-tracking-control-name]"
        )
        if link_el and link_el.get("href"):
            href = link_el["href"]
            if href.startswith("/"):
                href = base_url + href
            job.job_url = href.split("?")[0]

        # ── Company Name ─────────────────────────────────────
        company_el = card.select_one(
            ".job-card-container__primary-description,"
            ".artdeco-entity-lockup__subtitle span,"
            "h4.base-search-card__subtitle a,"
            "h4.base-search-card__subtitle,"
            ".job-card-container__company-name"
        )
        if company_el:
            job.company_name = clean_text(company_el.get_text())

        return job if (job.job_title or job.company_name) else None

    except Exception as exc:
        print(f"    ⚠️  Card parse error: {exc}")
        return None


def parse_job_listings_page(html: str, search_query: str = "") -> list[JobListing]:
    soup = _soup(html)
    jobs: list[JobListing] = []

    card_selectors = [
        "li.jobs-search-results__list-item",
        "div.job-card-container",
        "li.job-card-container__link",
        "div.job-search-card",
        "li.result-card",
        "ul.jobs-search__results-list > li",
        "div[data-occludable-job-id]",
        ".scaffold-layout__list-container li",
    ]

    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if cards:
            print(f"    Selector hit: '{sel}'  →  {len(cards)} cards")
            break

    if not cards:
        cards = [
            tag for tag in soup.find_all(True)
            if any("job-card" in c for c in (tag.get("class") or []))
        ]
        if cards:
            print(f"    Fallback search → {len(cards)} cards")

    if not cards:
        print("    ⚠️  No job cards found in HTML")

    for card in cards:
        job = parse_job_card(card, search_query=search_query)
        if job:
            jobs.append(job)

    return jobs