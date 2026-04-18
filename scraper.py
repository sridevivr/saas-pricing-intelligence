"""
SaaS Pricing Page Scraper
=========================
Scrapes pricing pages from Sales & Revenue SaaS companies and saves raw page
text for downstream analysis by Claude.

Usage:
    python scraper.py                    # Scrape all companies in targets.csv
    python scraper.py --limit 5          # Scrape first 5 companies only
    python scraper.py --company "Apollo"  # Scrape a specific company

Requirements:
    pip install requests beautifulsoup4 pandas

Output:
    - raw_pages/  folder with one .txt file per company (raw page text)
    - scrape_log.csv  with status of each scrape attempt
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import json
import argparse
from datetime import datetime
from pathlib import Path


# --- Configuration ---
TARGETS_FILE = "targets.csv"
RAW_PAGES_DIR = "raw_pages"
SCRAPE_LOG_FILE = "scrape_log.csv"
SNAPSHOTS_DIR = "snapshots"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Polite delay between requests (seconds)
REQUEST_DELAY = 2
REQUEST_TIMEOUT = 20


def get_snapshot_date():
    """Return today's date as the snapshot label."""
    return datetime.now().strftime("%Y-%m-%d")


def setup_directories(snapshot_dir=None):
    """Create output directories if they don't exist."""
    Path(RAW_PAGES_DIR).mkdir(exist_ok=True)
    if snapshot_dir:
        Path(snapshot_dir).mkdir(parents=True, exist_ok=True)


def load_targets(limit=None, company_filter=None):
    """Load target companies from CSV."""
    df = pd.read_csv(TARGETS_FILE)
    if company_filter:
        df = df[df["company"].str.contains(company_filter, case=False)]
    if limit:
        df = df.head(limit)
    print(f"Loaded {len(df)} target companies")
    return df


def scrape_pricing_page(company, url):
    """
    Scrape a single pricing page and return the extracted text.

    Returns:
        dict with keys: success, text, status_code, error, content_length
    """
    result = {
        "company": company,
        "url": url,
        "success": False,
        "text": "",
        "status_code": None,
        "error": None,
        "content_length": 0,
        "scraped_at": datetime.now().isoformat(),
    }

    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        result["status_code"] = response.status_code

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements (noise)
            for element in soup(["script", "style", "noscript", "svg", "path"]):
                element.decompose()

            # Extract text
            text = soup.get_text(separator="\n", strip=True)

            # Basic cleanup: remove excessive blank lines
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            clean_text = "\n".join(lines)

            result["text"] = clean_text
            result["content_length"] = len(clean_text)
            result["success"] = True

            # Quick diagnostic: check if page likely has pricing info
            pricing_signals = ["$", "/mo", "/month", "/year", "per user", "per seat",
                               "free", "starter", "professional", "enterprise",
                               "basic", "pro", "business", "contact sales"]
            signals_found = sum(1 for s in pricing_signals
                                if s.lower() in clean_text.lower())
            result["pricing_signals"] = signals_found

        elif response.status_code == 403:
            result["error"] = "403 Forbidden - site blocks scrapers"
        elif response.status_code == 404:
            result["error"] = "404 - pricing page not found at this URL"
        else:
            result["error"] = f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        result["error"] = "Timeout after 20 seconds"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)[:100]}"

    return result


def save_raw_page(company, text, snapshot_dir=None):
    """Save raw page text to file. Also saves a copy in the snapshot folder."""
    safe_name = company.lower().replace(" ", "_").replace(".", "_").replace("/", "_")

    # Save to main raw_pages/ (always, for backward compatibility)
    filepath = os.path.join(RAW_PAGES_DIR, f"{safe_name}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    # Also save to snapshot folder
    if snapshot_dir:
        snap_filepath = os.path.join(snapshot_dir, f"{safe_name}.txt")
        with open(snap_filepath, "w", encoding="utf-8") as f:
            f.write(text)

    return filepath


def run_scraper(limit=None, company_filter=None):
    """Main scraping loop. Saves a versioned snapshot for each run."""
    # Set up snapshot directory for this run
    snap_date = get_snapshot_date()
    snapshot_raw_dir = os.path.join(SNAPSHOTS_DIR, snap_date, "raw_pages")
    setup_directories(snapshot_dir=snapshot_raw_dir)

    targets = load_targets(limit=limit, company_filter=company_filter)

    log_entries = []
    successful = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"SaaS Pricing Scraper - Starting")
    print(f"{'='*60}")
    print(f"Snapshot: {snap_date}")
    print(f"Companies to scrape: {len(targets)}")
    print(f"Output directory: {RAW_PAGES_DIR}/ + {snapshot_raw_dir}/")
    print(f"{'='*60}\n")

    for idx, row in targets.iterrows():
        company = row["company"]
        url = row["pricing_url"]
        sector = row.get("sector", "Unknown")
        subsector = row.get("subsector", row.get("subcategory", "Unknown"))

        print(f"[{idx+1}/{len(targets)}] Scraping {company}...", end=" ")

        result = scrape_pricing_page(company, url)
        result["sector"] = sector
        result["subsector"] = subsector

        if result["success"]:
            filepath = save_raw_page(company, result["text"],
                                     snapshot_dir=snapshot_raw_dir)
            print(f"OK ({result['content_length']} chars, "
                  f"{result['pricing_signals']} pricing signals)")
            successful += 1
        else:
            print(f"FAILED - {result['error']}")
            failed += 1

        # Log entry (don't include full text in log)
        log_entry = {k: v for k, v in result.items() if k != "text"}
        log_entries.append(log_entry)

        # Polite delay
        time.sleep(REQUEST_DELAY)

    # Save scrape log (both to main dir and snapshot)
    log_df = pd.DataFrame(log_entries)
    log_df.to_csv(SCRAPE_LOG_FILE, index=False)
    snap_log = os.path.join(SNAPSHOTS_DIR, snap_date, "scrape_log.csv")
    log_df.to_csv(snap_log, index=False)

    print(f"\n{'='*60}")
    print(f"Scraping Complete")
    print(f"{'='*60}")
    print(f"Snapshot saved: {snap_date}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Log saved to: {SCRAPE_LOG_FILE}")
    print(f"Snapshot saved to: {SNAPSHOTS_DIR}/{snap_date}/")
    print(f"{'='*60}")

    return log_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS Pricing Page Scraper")
    parser.add_argument("--limit", type=int, help="Limit number of companies to scrape")
    parser.add_argument("--company", type=str, help="Scrape a specific company (partial match)")
    args = parser.parse_args()

    run_scraper(limit=args.limit, company_filter=args.company)
