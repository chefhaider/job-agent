"""
LinkedIn Job Scraper — multi-URL support.
Reads target URLs from CSV, scrapes all, saves combined CSV.
"""

import asyncio
import argparse
import sys

from scraper import LinkedInScraper, find_chrome_executable
from utils import save_to_csv, print_jobs_summary, load_target_urls


def verify_chrome():
    print("=" * 60)
    print("  🔍 LinkedIn Job Scraper — Multi-URL")
    print("=" * 60)
    try:
        find_chrome_executable()
    except FileNotFoundError as err:
        print(err)
        sys.exit(1)


async def run(
    urls_file: str,
    max_pages: int,
    headless: bool,
    output_file: str,
    delay: float,
):
    # Load target URLs
    try:
        targets = load_target_urls(urls_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}")
        sys.exit(1)

    # Scrape all targets
    scraper = LinkedInScraper(headless=headless, slow_mo=60)
    jobs = await scraper.scrape_multiple_urls(
        targets=targets,
        max_pages=max_pages,
        delay_between=delay,
    )

    if not jobs:
        print(
            "\n⚠️  No jobs extracted from any URL.\n"
            "   • Run without --headless to debug\n"
            "   • Check target_urls.csv for valid URLs\n"
        )
        return

    # Print summary and save
    print_jobs_summary(jobs)
    csv_path = save_to_csv(jobs, filename=output_file)
    print(f"\n✅ Done! {len(jobs)} jobs → {csv_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn jobs from multiple search URLs → CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                        # uses target_urls.csv
  python main.py --urls my_searches.csv                 # custom URLs file
  python main.py --urls target_urls.csv --pages 3       # 3 pages per search
  python main.py --headless -o all_jobs.csv             # headless + custom output
  python main.py --delay 10                             # 10s delay between searches
        """,
    )
    parser.add_argument(
        "--urls", type=str, default="target_urls.csv",
        help="Path to CSV file with target URLs (default: target_urls.csv)",
    )
    parser.add_argument(
        "--pages", type=int, default=2,
        help="Pages to scrape per URL (default: 2)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run without visible browser",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output CSV filename (default: auto-timestamped)",
    )
    parser.add_argument(
        "--delay", type=float, default=5.0,
        help="Seconds to wait between different searches (default: 5)",
    )

    args = parser.parse_args()

    verify_chrome()

    print(f"\n  URLs file  : {args.urls}")
    print(f"  Pages/URL  : {args.pages}")
    print(f"  Headless   : {args.headless}")
    print(f"  Delay      : {args.delay}s")
    print(f"  Output     : {args.output or 'auto'}")
    print("=" * 60)

    asyncio.run(
        run(
            urls_file=args.urls,
            max_pages=args.pages,
            headless=args.headless,
            output_file=args.output,
            delay=args.delay,
        )
    )


if __name__ == "__main__":
    main()