"""
LinkedIn Job Scraper — Playwright + stealth, system Chrome.
Supports multiple target URLs.
"""

import asyncio
import random
import subprocess
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext, Browser

from stealth_config import STEALTH_JS
from parser import parse_job_listings_page, JobListing


def find_chrome_executable() -> str:
    candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome/chrome",
    ]
    for path in candidates:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                print(f"  ✅ Chrome: {path} ({result.stdout.strip()})")
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    raise FileNotFoundError(
        "❌ Chrome not found!\n"
        "   Install:  sudo apt install google-chrome-stable"
    )


class LinkedInScraper:
    def __init__(self, headless: bool = False, slow_mo: int = 50):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.chrome_path = find_chrome_executable()

    async def _init_browser(self):
        print(f"\n  🚀 Launching Chrome (headless={self.headless})...")

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            executable_path=self.chrome_path,
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="light",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125"',
                "sec-ch-ua-platform": '"Linux"',
            },
        )

        await self.context.add_init_script(STEALTH_JS)
        self.page = await self.context.new_page()

        await self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}",
            lambda route: route.abort(),
        )
        await self.page.route("**/li/track*", lambda route: route.abort())
        await self.page.route("**/analytics/**", lambda route: route.abort())

        print("  ✅ Browser ready.")

    async def _human_delay(self, lo: float = 1.0, hi: float = 3.0):
        await asyncio.sleep(random.uniform(lo, hi))

    async def _human_scroll(self, amount: int = 300):
        steps = random.randint(3, 6)
        for _ in range(steps):
            delta = amount // steps + random.randint(-50, 50)
            await self.page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.1, 0.4))

    async def _dismiss_login_prompt(self):
        selectors = [
            'button[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]',
            'button[aria-label="Dismiss"]',
            'button[aria-label="Close"]',
            "button.modal__dismiss",
            "button.contextual-sign-in-modal__modal-dismiss-btn",
            "button.artdeco-modal__dismiss",
            "button[data-test-modal-close-btn]",
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    print("    ✖️  Closed login prompt")
                    await self._human_delay(0.5, 1.0)
                    return True
            except Exception:
                continue

        try:
            modal = self.page.locator(
                '.artdeco-modal, .modal, [role="dialog"]'
            ).first
            if await modal.is_visible(timeout=500):
                await self.page.keyboard.press("Escape")
                print("    ✖️  Closed modal (Escape)")
                await self._human_delay(0.5, 1.0)
                return True
        except Exception:
            pass
        return False

    async def _dismiss_all_prompts(self):
        for _ in range(5):
            if not await self._dismiss_login_prompt():
                break
            await self._human_delay(0.3, 0.8)

    async def _scroll_job_list(self):
        print("    📜 Scrolling to load jobs...")

        container = None
        for sel in [
            ".jobs-search-results-list",
            ".scaffold-layout__list",
            ".jobs-search__results-list",
        ]:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    container = el
                    break
            except Exception:
                continue

        for _ in range(8):
            if container:
                await container.evaluate("el => el.scrollTop += 500")
            else:
                await self._human_scroll(500)
            await self._human_delay(0.8, 1.5)
            await self._dismiss_all_prompts()

        if container:
            await container.evaluate("el => el.scrollTop = 0")
        await self._human_delay(1.0, 2.0)

    async def _extract_jobs_from_page(self, search_query: str) -> list[JobListing]:
        print("    🔍 Extracting jobs...")
        html = await self.page.content()
        jobs = parse_job_listings_page(html, search_query=search_query)
        print(f"    ✅ Found {len(jobs)} jobs")
        return jobs

    async def _go_to_next_page(self) -> bool:
        for sel in [
            'button[aria-label="View next page"]',
            "button.artdeco-pagination__button--next",
        ]:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    await self._human_delay(3.0, 5.0)
                    await self._dismiss_all_prompts()
                    print("    ➡️  Next page")
                    return True
            except Exception:
                continue
        return False

    async def scrape_single_url(
        self,
        url: str,
        search_query: str,
        max_pages: int = 2,
    ) -> list[JobListing]:
        """Scrape jobs from a single target URL (multiple pages)."""
        all_jobs: list[JobListing] = []

        print(f"\n🌐 Opening: {search_query}")
        print(f"   URL: {url[:80]}...")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self._human_delay(3.0, 5.0)
        await self._dismiss_all_prompts()

        for page_num in range(1, max_pages + 1):
            print(f"\n  📄 Page {page_num}/{max_pages} — {search_query}")
            await self._dismiss_all_prompts()
            await self._scroll_job_list()

            jobs = await self._extract_jobs_from_page(search_query)

            if not jobs:
                await self._human_delay(3.0, 5.0)
                await self._dismiss_all_prompts()
                jobs = await self._extract_jobs_from_page(search_query)

            if not jobs:
                print("    ❌ No jobs found. Moving on.")
                break

            # Deduplicate by URL
            existing_urls = {j.job_url for j in all_jobs if j.job_url}
            for job in jobs:
                if not job.job_url or job.job_url not in existing_urls:
                    all_jobs.append(job)
                    if job.job_url:
                        existing_urls.add(job.job_url)

            print(f"    📊 Jobs for '{search_query}': {len(all_jobs)}")

            if page_num < max_pages:
                if not await self._go_to_next_page():
                    break

        return all_jobs

    async def scrape_multiple_urls(
        self,
        targets: list,           # list of TargetURL
        max_pages: int = 2,
        delay_between: float = 5.0,
    ) -> list[JobListing]:
        """
        Scrape multiple target URLs one by one.
        Reuses the same browser session to look more natural.
        """
        all_jobs: list[JobListing] = []

        try:
            await self._init_browser()

            for idx, target in enumerate(targets, 1):
                print("\n" + "━" * 60)
                print(f"  🎯 Target {idx}/{len(targets)}: {target.search_query}")
                print("━" * 60)

                try:
                    jobs = await self.scrape_single_url(
                        url=target.url,
                        search_query=target.search_query,
                        max_pages=max_pages,
                    )
                    all_jobs.extend(jobs)
                    print(f"\n  ✅ {target.search_query}: {len(jobs)} jobs extracted")

                except Exception as e:
                    print(f"\n  ❌ Error scraping '{target.search_query}': {e}")
                    print("     Continuing to next target...")
                    continue

                # Delay between different searches to avoid detection
                if idx < len(targets):
                    wait = random.uniform(delay_between, delay_between + 5)
                    print(f"\n  ⏳ Waiting {wait:.1f}s before next search...")
                    await asyncio.sleep(wait)

            return all_jobs

        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            raise
        finally:
            await self.close()

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("\n🔒 Browser closed.")