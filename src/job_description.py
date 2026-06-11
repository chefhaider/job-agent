"""
LinkedIn Job Description Scraper
Reads jobs_sorted.csv → extracts "About the job" description
→ saves combined JSON with: job_title, company_name, job_url, job_description
"""

import asyncio
import random
import subprocess
import csv
import os
import re
import json
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


# ─────────────────────────────────────────────────────────────
# Stealth JS
# ─────────────────────────────────────────────────────────────

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'de'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin',  filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
            { name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
            { name: 'Native Client',      filename: 'internal-nacl-plugin', description: '', length: 2 },
        ];
        return Object.assign(Object.create(PluginArray.prototype), {
            length: plugins.length,
            item: (i) => plugins[i] || null,
            namedItem: (name) => plugins.find(p => p.name === name) || null,
            refresh: () => {},
            ...Object.fromEntries(plugins.map((p, i) => [i, p])),
        });
    }
});

window.chrome = {
    runtime: {},
    loadTimes: () => ({}),
    csi: () => ({}),
    app: { isInstalled: false },
};

const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(p);

const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.apply(this, arguments);
};

Object.defineProperty(screen, 'width',       { get: () => 1920 });
Object.defineProperty(screen, 'height',      { get: () => 1080 });
Object.defineProperty(screen, 'availWidth',  { get: () => 1920 });
Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
Object.defineProperty(screen, 'colorDepth',  { get: () => 24  });
Object.defineProperty(screen, 'pixelDepth',  { get: () => 24  });

delete window.__playwright;
delete window.__pw_manual;
delete window.__PW_inspect;
"""


# ─────────────────────────────────────────────────────────────
# Chrome detection
# ─────────────────────────────────────────────────────────────

def find_chrome() -> str:
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
            r = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                print(f"  ✅ Chrome: {path}  ({r.stdout.strip()})")
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise FileNotFoundError(
        "❌ Chrome not found!\n"
        "   Install: sudo apt install google-chrome-stable"
    )


# ─────────────────────────────────────────────────────────────
# Load jobs_sorted.csv
# ─────────────────────────────────────────────────────────────

def load_jobs_csv(filepath: str) -> list[dict]:
    """
    Read jobs_sorted.csv and return list of job dicts.
    Required columns : job_url
    Optional columns : job_title, company_name, search_query, sorted_by_model
    Skips rows with empty or invalid URLs.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"❌ File not found: {filepath}")

    jobs = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)

        if not reader.fieldnames:
            raise ValueError(f"❌ Empty CSV: {filepath}")

        headers = [h.strip().lower() for h in reader.fieldnames]
        if "job_url" not in headers:
            raise ValueError(
                f"❌ CSV must have a 'job_url' column.\n"
                f"   Found: {reader.fieldnames}"
            )

        for i, row in enumerate(reader, start=2):
            # Normalize keys
            clean = {k.strip().lower(): (v or "").strip() for k, v in row.items()}

            url = clean.get("job_url", "")
            if not url or not url.startswith("http"):
                print(f"  ⚠️  Row {i}: invalid URL → skipped")
                continue

            jobs.append({
                "job_title":    clean.get("job_title", ""),
                "company_name": clean.get("company_name", ""),
                "job_url":      url,
                # carry these through for reference but won't appear in output
                "search_query": clean.get("search_query", ""),
            })

    print(f"\n  📋 Loaded {len(jobs)} jobs from {filepath}")
    return jobs


# ─────────────────────────────────────────────────────────────
# Text cleaner
# ─────────────────────────────────────────────────────────────

def clean_description(text: str) -> str:
    """Normalize whitespace while keeping paragraph / bullet structure."""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────

class JobDescriptionScraper:

    DESCRIPTION_SELECTORS = [
        "div.show-more-less-html__markup",
        "div.show-more-less-html__markup--clamp-after-5",
        ".jobs-description__content .jobs-box__html-content",
        ".jobs-description-content__text",
        "#job-details",
        "section.show-more-less-html",
        "div.description__text",
        "[class*='description__text']",
        "[class*='job-description']",
    ]

    def __init__(self, headless: bool = False, slow_mo: int = 60):
        self.headless  = headless
        self.slow_mo   = slow_mo
        self.chrome    = find_chrome()
        self.playwright = None
        self.browser:  Optional[Browser]         = None
        self.context:  Optional[BrowserContext]  = None
        self.page:     Optional[Page]            = None

    # ── browser ───────────────────────────────────────────

    async def _start(self):
        print(f"\n  🚀 Launching Chrome (headless={self.headless})…")
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            executable_path=self.chrome,
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
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                "--lang=en-US",
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
            timezone_id="Europe/Berlin",
            color_scheme="light",
            extra_http_headers={
                "Accept-Language":    "en-US,en;q=0.9,de;q=0.8",
                "Accept-Encoding":    "gzip, deflate, br",
                "sec-ch-ua":          '"Google Chrome";v="125","Chromium";v="125"',
                "sec-ch-ua-platform": '"Linux"',
                "sec-ch-ua-mobile":   "?0",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        await self.context.add_init_script(STEALTH_JS)
        self.page = await self.context.new_page()

        # Block images / fonts / trackers
        await self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
            lambda route: route.abort(),
        )
        await self.page.route("**/li/track*",    lambda r: r.abort())
        await self.page.route("**/analytics/**", lambda r: r.abort())
        await self.page.route("**/beacon*",      lambda r: r.abort())
        await self.page.route("**/pixel*",       lambda r: r.abort())

        print("  ✅ Browser ready.\n")

    async def _stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("\n  🔒 Browser closed.")

    # ── helpers ───────────────────────────────────────────

    async def _delay(self, lo: float = 1.0, hi: float = 3.0):
        await asyncio.sleep(random.uniform(lo, hi))

    async def _slow_scroll(self):
        for _ in range(6):
            await self.page.mouse.wheel(0, random.randint(250, 450))
            await asyncio.sleep(random.uniform(0.3, 0.7))
        await self.page.evaluate("window.scrollTo(0, 0)")
        await self._delay(0.5, 1.0)

    async def _dismiss_prompt(self) -> bool:
        selectors = [
            'button[data-tracking-control-name*="modal_dismiss"]',
            'button[aria-label="Dismiss"]',
            'button[aria-label="Close"]',
            "button.modal__dismiss",
            "button.contextual-sign-in-modal__modal-dismiss-btn",
            "button.artdeco-modal__dismiss",
            "button[data-test-modal-close-btn]",
            'button[action-type="DENY"]',
            'button[data-control-name="ga-cookie.consent.deny.v3"]',
            "button#onetrust-reject-all-handler",
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=600):
                    await btn.click()
                    print(f"    ✖️  Dismissed: {sel}")
                    await self._delay(0.4, 0.9)
                    return True
            except Exception:
                continue
        try:
            modal = self.page.locator(
                '.artdeco-modal, [role="dialog"], .modal'
            ).first
            if await modal.is_visible(timeout=500):
                await self.page.keyboard.press("Escape")
                print("    ✖️  Closed modal (Escape)")
                await self._delay(0.4, 0.9)
                return True
        except Exception:
            pass
        return False

    async def _dismiss_all(self):
        for _ in range(6):
            if not await self._dismiss_prompt():
                break
            await self._delay(0.2, 0.4)

    async def _expand_description(self):
        """Click 'See more' so we get the untruncated description."""
        for sel in [
            "button.show-more-less-html__button--more",
            'button[aria-label="Click to see more description"]',
            "button.jobs-description__footer-button",
            'button[data-tracking-control-name*="see_more"]',
        ]:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    print("    🔽 Expanded 'See more'")
                    await self._delay(1.0, 2.0)
                    return
            except Exception:
                continue

    # ── extract one page ──────────────────────────────────

    async def _extract_description(self, url: str) -> Optional[str]:
        print(f"\n  🌐 {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            print(f"  ❌ Navigation failed: {e}")
            return None

        await self._delay(2.5, 4.5)
        await self._dismiss_all()
        await self._slow_scroll()
        await self._dismiss_all()
        await self._expand_description()

        # Try CSS selectors first
        for sel in self.DESCRIPTION_SELECTORS:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    text = await el.inner_text()
                    if text and len(text.strip()) > 50:
                        cleaned = clean_description(text)
                        print(f"    ✅ Got description ({len(cleaned)} chars) via {sel}")
                        return cleaned
            except Exception:
                continue

        # Regex fallback on raw page text
        print("  ⚠️  CSS selectors failed — trying page-text regex…")
        try:
            full = await self.page.inner_text("body")
            match = re.search(
                r"About the job\s*\n+(.*)",
                full, re.DOTALL | re.IGNORECASE,
            )
            if match:
                raw = re.split(
                    r"\n(?:About the company|Similar jobs|People also viewed"
                    r"|Show more jobs|Sign in|Join now)",
                    match.group(1), flags=re.IGNORECASE,
                )[0]
                cleaned = clean_description(raw)
                if len(cleaned) > 50:
                    print(f"    ✅ Got description ({len(cleaned)} chars) via regex")
                    return cleaned
        except Exception as e:
            print(f"  ❌ Regex fallback failed: {e}")

        print("  ❌ Could not extract description.")
        return None

    # ── public API ────────────────────────────────────────

    async def run(
        self,
        jobs: list[dict],
        delay_between: float = 6.0,
    ) -> list[dict]:
        """
        For every job dict (must have job_url, job_title, company_name)
        fetch the description and return enriched records.
        """
        results = []
        await self._start()

        try:
            total = len(jobs)
            for idx, job in enumerate(jobs, 1):
                print(f"\n{'━' * 60}")
                print(f"  [{idx}/{total}]  {job['job_title']}  —  {job['company_name']}")
                print("━" * 60)

                description = await self._extract_description(job["job_url"])

                results.append({
                    "job_title":       job["job_title"],
                    "company_name":    job["company_name"],
                    "job_url":         job["job_url"],
                    "job_description": description or "",
                })

                # Progress indicator
                ok_count = sum(1 for r in results if r["job_description"])
                print(f"  📊 Progress: {idx}/{total}  |  ✅ {ok_count} extracted")

                if idx < total:
                    wait = random.uniform(delay_between, delay_between + 4)
                    print(f"  ⏳ Waiting {wait:.1f}s…")
                    await asyncio.sleep(wait)

        finally:
            await self._stop()

        return results


# ─────────────────────────────────────────────────────────────
# Save JSON
# ─────────────────────────────────────────────────────────────

def save_json(results: list[dict], filepath: str):
    """
    Save results to JSON.
    Each record: job_title, company_name, job_url, job_description
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    output = {
        "metadata": {
            "scraped_at":  datetime.now().isoformat(),
            "total_jobs":  len(results),
            "extracted":   sum(1 for r in results if r["job_description"]),
            "failed":      sum(1 for r in results if not r["job_description"]),
        },
        "jobs": results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n💾 JSON saved → {filepath}")
    print(f"   ✅ {output['metadata']['extracted']} / {output['metadata']['total_jobs']} descriptions extracted")
    print(f"   ❌ {output['metadata']['failed']} failed")


# ─────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────

def print_summary(results: list[dict]):
    print("\n" + "=" * 65)
    print(f"  📋 RESULTS SUMMARY  ({len(results)} jobs)")
    print("=" * 65)
    for i, r in enumerate(results, 1):
        status = "✅" if r["job_description"] else "❌"
        chars  = len(r["job_description"])
        print(f"  {status} {i:>3}. {r['job_title']}")
        print(f"          {r['company_name']}")
        print(f"          {chars} chars  |  {r['job_url'][:60]}…")
    print("=" * 65)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

async def main_async(args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load input CSV
    jobs = load_jobs_csv(args.input)
    if not jobs:
        print("❌ No valid jobs found in input file.")
        return

    # Optionally limit rows (useful for testing)
    if args.limit:
        jobs = jobs[: args.limit]
        print(f"  ℹ️  Limited to first {args.limit} jobs (--limit flag)")

    # Scrape
    scraper = JobDescriptionScraper(headless=args.headless, slow_mo=70)
    results = await scraper.run(jobs, delay_between=args.delay)

    # Summary
    print_summary(results)

    # Save JSON
    out_path = args.output or f"output/job_descriptions.json"
    if not out_path.endswith(".json"):
        out_path += ".json"
    save_json(results, out_path)

    print(f"\n✅ All done!  →  {out_path}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Read jobs_sorted.csv → scrape LinkedIn 'About the job' descriptions "
            "→ save JSON with job_title, company_name, job_url, job_description"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (reads jobs_sorted.csv, saves JSON to output/)
  python job_description_scraper.py

  # Custom input file
  python job_description_scraper.py --input my_jobs.csv

  # Custom output file
  python job_description_scraper.py -o results/descriptions.json

  # Test with only the first 3 jobs
  python job_description_scraper.py --limit 3

  # Headless mode + longer delay (safer for large batches)
  python job_description_scraper.py --headless --delay 12

  # Full example
  python job_description_scraper.py --input jobs_sorted.csv -o output/descriptions.json --delay 8 --headless
        """,
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        default="output/jobs_sorted.csv",
        help="Input CSV file (default: output/jobs_sorted.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output JSON file (default: output/job_descriptions.json)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome without a visible window",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.0,
        help="Seconds to wait between requests (default: 6)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Only scrape the first N jobs (useful for testing)",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()