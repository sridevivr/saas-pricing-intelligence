# -*- coding: utf-8 -*-
"""
Pricing Data Classifier (Claude-powered)
=========================================
Takes raw pricing page text from scraper.py and uses Claude to extract
structured pricing data.

Usage:
    python classify.py
    python classify.py --company "Apollo"
    python classify.py --dry-run

Requirements:
    pip install anthropic pandas

Setup:
    export ANTHROPIC_API_KEY='your-key-here'

Output:
    - pricing_data.csv
    - pricing_data.json
"""

import anthropic
import pandas as pd
import os
import json
import argparse
from pathlib import Path
from datetime import datetime


# --- Configuration ---
RAW_PAGES_DIR = "raw_pages"
OUTPUT_CSV = "pricing_data.csv"
OUTPUT_JSON = "pricing_data.json"
SCRAPE_LOG = "scrape_log.csv"
SNAPSHOTS_DIR = "snapshots"

MODEL = "claude-haiku-4-5-20251001"


def get_latest_snapshot():
    """Find the most recent snapshot folder."""
    snap_path = Path(SNAPSHOTS_DIR)
    if not snap_path.exists():
        return None
    folders = sorted([f.name for f in snap_path.iterdir() if f.is_dir()])
    return folders[-1] if folders else None


def build_prompt(company, subsector, page_text):
    """Build the extraction prompt using only ASCII characters."""
    return (
        "You are a pricing data extraction specialist. "
        "Given the raw text from a SaaS company pricing page, "
        "extract structured pricing information.\n\n"
        "Company: " + company + "\n"
        "Subsector: " + subsector + "\n\n"
        "Return a JSON object with this exact structure:\n"
        "{\n"
        '  "company": "' + company + '",\n'
        '  "subsector": "' + subsector + '",\n'
        '  "has_public_pricing": true or false,\n'
        '  "pricing_model": "per_seat" or "usage_based" or "flat_rate" or "hybrid" or "custom_only" or "freemium" or "unknown",\n'
        '  "currency": "USD" or "EUR" or "GBP" or "other",\n'
        '  "billing_options": ["monthly", "annual"],\n'
        '  "annual_discount_pct": null or number,\n'
        '  "free_tier": {\n'
        '    "exists": true or false,\n'
        '    "name": "string or null",\n'
        '    "limitations": "brief description or null"\n'
        '  },\n'
        '  "free_trial": {\n'
        '    "exists": true or false,\n'
        '    "duration_days": null or number\n'
        '  },\n'
        '  "tiers": [\n'
        '    {\n'
        '      "name": "tier name",\n'
        '      "monthly_price": null or number,\n'
        '      "annual_price_per_month": null or number,\n'
        '      "price_unit": "per user" or "flat" or "per credit" or "per contact" or "custom",\n'
        '      "is_enterprise": false,\n'
        '      "key_features": ["feature 1", "feature 2", "feature 3"],\n'
        '      "ai_features": ["ai feature 1"] or []\n'
        '    }\n'
        '  ],\n'
        '  "enterprise_tier": {\n'
        '    "exists": true or false,\n'
        '    "contact_sales": true or false,\n'
        '    "name": "string or null"\n'
        '  },\n'
        '  "ai_mentions": {\n'
        '    "has_ai_features": true or false,\n'
        '    "ai_feature_names": ["list of specific AI features mentioned"],\n'
        '    "ai_in_pricing": "none" or "included" or "add_on" or "higher_tiers_only"\n'
        '  },\n'
        '  "notes": "any important context about the pricing"\n'
        "}\n\n"
        "Rules:\n"
        "- If a price is listed as annual total, divide by 12 for monthly equivalent\n"
        "- If pricing says Contact Sales or Get a Quote, set monthly_price to null and is_enterprise to true\n"
        "- If the page has no pricing information at all, set has_public_pricing to false\n"
        "- For AI features, look for keywords like: AI, machine learning, intelligence, automated insights, predictive, copilot, assistant\n"
        "- Be precise with numbers. Do not guess prices that are not on the page.\n"
        "- Return ONLY the JSON object, no other text.\n\n"
        "Raw page text:\n"
        + page_text
    )


def sanitize_text(text):
    """Replace problematic unicode characters with ASCII equivalents."""
    replacements = {
        chr(0x2018): "'",
        chr(0x2019): "'",
        chr(0x201C): '"',
        chr(0x201D): '"',
        chr(0x2013): '-',
        chr(0x2014): '-',
        chr(0x2026): '...',
        chr(0x00A0): ' ',
        chr(0x200B): '',
        chr(0x00AE): '(R)',
        chr(0x2122): '(TM)',
        chr(0x00A9): '(c)',
        chr(0xFEFF): '',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    text = text.encode('ascii', errors='replace').decode('ascii')
    return text


def get_client():
    """Initialize Anthropic client."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Run: export ANTHROPIC_API_KEY='your-key-here'")
        exit(1)
    return anthropic.Anthropic(api_key=api_key)


def load_raw_page(company):
    """Load raw page text for a company."""
    safe_name = company.lower().replace(" ", "_").replace(".", "_").replace("/", "_")
    filepath = os.path.join(RAW_PAGES_DIR, safe_name + ".txt")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    return sanitize_text(text)


def classify_pricing(client, company, subsector, page_text):
    """Send page text to Claude for structured extraction."""
    max_chars = 15000
    if len(page_text) > max_chars:
        page_text = page_text[:max_chars] + "\n\n[PAGE TRUNCATED]"

    prompt = build_prompt(
        sanitize_text(company),
        sanitize_text(subsector),
        page_text
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()

        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        data = json.loads(response_text)
        return {"success": True, "data": data}

    except json.JSONDecodeError as e:
        return {"success": False, "error": "JSON parse error: " + str(e)[:100]}
    except Exception as e:
        return {"success": False, "error": "API error: " + str(e)[:100]}


def flatten_for_csv(data):
    """Flatten nested pricing data for CSV output."""
    rows = []
    company = data.get("company", "")
    subsector = data.get("subsector", data.get("subcategory", ""))

    ai_mentions = data.get("ai_mentions", {})
    free_tier = data.get("free_tier", {})
    free_trial = data.get("free_trial", {})
    enterprise = data.get("enterprise_tier", {})

    base = {
        "company": company,
        "sector": data.get("sector", "Unknown"),
        "subsector": subsector,
        "has_public_pricing": data.get("has_public_pricing"),
        "pricing_model": data.get("pricing_model"),
        "currency": data.get("currency"),
        "annual_discount_pct": data.get("annual_discount_pct"),
        "free_tier_exists": free_tier.get("exists"),
        "free_trial_exists": free_trial.get("exists"),
        "free_trial_days": free_trial.get("duration_days"),
        "enterprise_tier_exists": enterprise.get("exists"),
        "enterprise_contact_sales": enterprise.get("contact_sales"),
        "has_ai_features": ai_mentions.get("has_ai_features"),
        "ai_in_pricing": ai_mentions.get("ai_in_pricing"),
        "ai_features_list": "; ".join(ai_mentions.get("ai_feature_names", [])),
        "notes": data.get("notes"),
        "classified_at": datetime.now().isoformat(),
    }

    tiers = data.get("tiers", [])
    if tiers:
        for tier in tiers:
            row = dict(base)
            row["tier_name"] = tier.get("name")
            row["monthly_price"] = tier.get("monthly_price")
            row["annual_price_per_month"] = tier.get("annual_price_per_month")
            row["price_unit"] = tier.get("price_unit")
            row["is_enterprise_tier"] = tier.get("is_enterprise")
            row["key_features"] = "; ".join(tier.get("key_features", []))
            row["tier_ai_features"] = "; ".join(tier.get("ai_features", []))
            rows.append(row)
    else:
        base["tier_name"] = "N/A"
        rows.append(base)

    return rows


def run_classifier(company_filter=None, dry_run=False):
    """Main classification loop."""
    if os.path.exists(SCRAPE_LOG):
        log_df = pd.read_csv(SCRAPE_LOG)
        scraped = log_df[log_df["success"] == True]
    else:
        files = list(Path(RAW_PAGES_DIR).glob("*.txt"))
        print("No scrape log found. Found " + str(len(files)) + " raw page files.")
        scraped = pd.DataFrame({
            "company": [f.stem.replace("_", " ").title() for f in files],
            "subsector": ["Unknown"] * len(files),
        })

    if company_filter:
        scraped = scraped[scraped["company"].str.contains(company_filter, case=False)]

    print("")
    print("=" * 60)
    if dry_run:
        print("Pricing Classifier - DRY RUN")
    else:
        print("Pricing Classifier - Starting")
    print("=" * 60)
    print("Companies to classify: " + str(len(scraped)))

    if dry_run:
        for _, row in scraped.iterrows():
            print("  Would classify: " + row["company"])
        return

    client = get_client()
    all_rows = []
    all_json = []
    successful = 0
    failed = 0

    for idx, row in scraped.iterrows():
        company = row["company"]
        sector = row.get("sector", "Unknown")
        subsector = row.get("subsector", row.get("subcategory", "Unknown"))

        print("")
        print("[" + str(idx + 1) + "/" + str(len(scraped)) + "] Classifying " + company + "... ", end="")

        page_text = load_raw_page(company)
        if not page_text:
            print("SKIPPED - no raw page file found")
            failed += 1
            continue

        result = classify_pricing(client, company, subsector, page_text)

        if result["success"]:
            data = result["data"]
            data["sector"] = sector
            tier_count = len(data.get("tiers", []))
            model = data.get("pricing_model", "unknown")
            print("OK (" + str(tier_count) + " tiers, model: " + model + ")")

            csv_rows = flatten_for_csv(data)
            all_rows.extend(csv_rows)
            all_json.append(data)
            successful += 1
        else:
            print("FAILED - " + result["error"])
            failed += 1

    # Save to main directory (latest)
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT_CSV, index=False)
        print("")
        print("CSV saved to: " + OUTPUT_CSV)

    if all_json:
        with open(OUTPUT_JSON, "w") as f:
            json.dump(all_json, f, indent=2)
        print("JSON saved to: " + OUTPUT_JSON)

    # Also save to snapshot folder if one exists
    snap_date = get_latest_snapshot()
    if snap_date:
        snap_dir = os.path.join(SNAPSHOTS_DIR, snap_date)
        if all_rows:
            df.to_csv(os.path.join(snap_dir, "pricing_data.csv"), index=False)
        if all_json:
            with open(os.path.join(snap_dir, "pricing_data.json"), "w") as f:
                json.dump(all_json, f, indent=2)
        print("Snapshot copy saved to: " + snap_dir + "/")

    print("")
    print("=" * 60)
    print("Classification Complete")
    print("=" * 60)
    print("Successful: " + str(successful))
    print("Failed: " + str(failed))
    if snap_date:
        print("Snapshot: " + snap_date)
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pricing Data Classifier")
    parser.add_argument("--company", type=str, help="Classify specific company")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be classified")
    args = parser.parse_args()

    run_classifier(company_filter=args.company, dry_run=args.dry_run)
