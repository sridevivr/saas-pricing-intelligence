"""
SaaS Pricing Change Detector
=============================
Compares two snapshots and identifies what changed in pricing.
Optionally uses Claude to classify each change as a strategic signal.

Usage:
    python compare.py                              # Compare two most recent snapshots
    python compare.py --old 2025-04-17 --new 2025-04-24   # Compare specific dates
    python compare.py --classify                    # Use Claude to classify change types
    python compare.py --company "Apollo"            # Check one company

Requirements:
    pip install pandas anthropic (anthropic only needed with --classify)

Output:
    - pricing_changes.csv     (all detected changes)
    - pricing_changes.json    (detailed change records)
    - change_report.md        (human-readable summary)
"""

import pandas as pd
import json
import argparse
import os
from pathlib import Path
from datetime import datetime


SNAPSHOTS_DIR = "snapshots"
OUTPUT_CHANGES_CSV = "pricing_changes.csv"
OUTPUT_CHANGES_JSON = "pricing_changes.json"
OUTPUT_REPORT = "change_report.md"


def list_snapshots():
    """List all available snapshot dates."""
    snap_path = Path(SNAPSHOTS_DIR)
    if not snap_path.exists():
        return []
    folders = sorted([f.name for f in snap_path.iterdir() if f.is_dir()])
    return folders


def load_snapshot(date_label):
    """Load pricing_data.json from a snapshot."""
    json_path = os.path.join(SNAPSHOTS_DIR, date_label, "pricing_data.json")
    if not os.path.exists(json_path):
        print("No pricing_data.json found in snapshot " + date_label)
        print("Did you run classify.py after scraping?")
        return None
    with open(json_path) as f:
        return json.load(f)


def build_company_map(data):
    """Convert JSON list to dict keyed by company name."""
    result = {}
    for entry in data:
        company = entry.get("company", "Unknown")
        result[company] = entry
    return result


def compare_tiers(old_tiers, new_tiers):
    """Compare pricing tiers between two snapshots for one company."""
    changes = []

    old_by_name = {t.get("name", "").lower(): t for t in old_tiers}
    new_by_name = {t.get("name", "").lower(): t for t in new_tiers}

    all_tier_names = set(list(old_by_name.keys()) + list(new_by_name.keys()))

    for tier_name in all_tier_names:
        old_tier = old_by_name.get(tier_name)
        new_tier = new_by_name.get(tier_name)

        if old_tier and not new_tier:
            changes.append({
                "type": "tier_removed",
                "tier": tier_name,
                "detail": "Tier '" + tier_name + "' was removed",
                "old_value": str(old_tier.get("monthly_price", "N/A")),
                "new_value": "N/A",
            })

        elif new_tier and not old_tier:
            changes.append({
                "type": "tier_added",
                "tier": tier_name,
                "detail": "New tier '" + tier_name + "' added",
                "old_value": "N/A",
                "new_value": str(new_tier.get("monthly_price", "N/A")),
            })

        elif old_tier and new_tier:
            # Check price change
            old_price = old_tier.get("monthly_price")
            new_price = new_tier.get("monthly_price")
            if old_price and new_price and old_price != new_price:
                direction = "increase" if new_price > old_price else "decrease"
                pct = ((new_price - old_price) / old_price * 100)
                changes.append({
                    "type": "price_" + direction,
                    "tier": tier_name,
                    "detail": "Price " + direction + " from $"
                             + str(old_price) + " to $" + str(new_price)
                             + " (" + "{:+.1f}".format(pct) + "%)",
                    "old_value": str(old_price),
                    "new_value": str(new_price),
                })

            # Check AI features change
            old_ai = set(old_tier.get("ai_features", []))
            new_ai = set(new_tier.get("ai_features", []))
            added_ai = new_ai - old_ai
            removed_ai = old_ai - new_ai
            if added_ai:
                changes.append({
                    "type": "ai_feature_added",
                    "tier": tier_name,
                    "detail": "AI features added: " + ", ".join(added_ai),
                    "old_value": str(list(old_ai)),
                    "new_value": str(list(new_ai)),
                })
            if removed_ai:
                changes.append({
                    "type": "ai_feature_removed",
                    "tier": tier_name,
                    "detail": "AI features removed: " + ", ".join(removed_ai),
                    "old_value": str(list(old_ai)),
                    "new_value": str(list(new_ai)),
                })

    return changes


def compare_company(old_data, new_data):
    """Compare all pricing attributes for one company."""
    changes = []

    # Pricing model change
    old_model = old_data.get("pricing_model", "unknown")
    new_model = new_data.get("pricing_model", "unknown")
    if old_model != new_model:
        changes.append({
            "type": "model_change",
            "tier": "N/A",
            "detail": "Pricing model changed from " + old_model + " to " + new_model,
            "old_value": old_model,
            "new_value": new_model,
        })

    # Free tier change
    old_free = old_data.get("free_tier", {}).get("exists", False)
    new_free = new_data.get("free_tier", {}).get("exists", False)
    if old_free and not new_free:
        changes.append({
            "type": "free_tier_removed",
            "tier": "N/A",
            "detail": "Free tier was removed",
            "old_value": "true",
            "new_value": "false",
        })
    elif not old_free and new_free:
        changes.append({
            "type": "free_tier_added",
            "tier": "N/A",
            "detail": "Free tier was added",
            "old_value": "false",
            "new_value": "true",
        })

    # Public pricing change
    old_public = old_data.get("has_public_pricing", False)
    new_public = new_data.get("has_public_pricing", False)
    if old_public and not new_public:
        changes.append({
            "type": "pricing_hidden",
            "tier": "N/A",
            "detail": "Public pricing was removed (moved to contact sales)",
            "old_value": "public",
            "new_value": "hidden",
        })
    elif not old_public and new_public:
        changes.append({
            "type": "pricing_revealed",
            "tier": "N/A",
            "detail": "Pricing was made public",
            "old_value": "hidden",
            "new_value": "public",
        })

    # Number of tiers changed
    old_tiers = old_data.get("tiers", [])
    new_tiers = new_data.get("tiers", [])
    if len(old_tiers) != len(new_tiers):
        changes.append({
            "type": "tier_count_change",
            "tier": "N/A",
            "detail": "Number of tiers changed from "
                     + str(len(old_tiers)) + " to " + str(len(new_tiers)),
            "old_value": str(len(old_tiers)),
            "new_value": str(len(new_tiers)),
        })

    # Tier-level changes
    tier_changes = compare_tiers(old_tiers, new_tiers)
    changes.extend(tier_changes)

    return changes


def classify_changes_with_claude(changes_by_company):
    """Use Claude to classify each change as a strategic signal."""
    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed. Run: pip install anthropic")
        return changes_by_company

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Skipping AI classification.")
        return changes_by_company

    client = anthropic.Anthropic(api_key=api_key)

    # Build a summary of all changes for Claude to classify
    summary_lines = []
    for company, changes in changes_by_company.items():
        for c in changes:
            summary_lines.append(
                company + ": " + c["detail"]
            )

    if not summary_lines:
        return changes_by_company

    prompt = (
        "You are a SaaS pricing strategy analyst. "
        "Below is a list of pricing changes detected across SaaS companies. "
        "For each change, classify it into one of these strategic categories:\n\n"
        "- MOVING_UPMARKET: raising prices, removing free tier, adding enterprise-only features\n"
        "- MOVING_DOWNMARKET: lowering prices, adding free tier, making features more accessible\n"
        "- AI_MONETIZATION: bundling AI, adding AI add-ons, creating AI-specific tiers\n"
        "- USAGE_BASED_SHIFT: moving from per-seat to usage-based or consumption pricing\n"
        "- SIMPLIFICATION: reducing tiers, consolidating plans\n"
        "- EXPANSION: adding tiers, creating new plan levels\n"
        "- COMPETITIVE_RESPONSE: price matching, undercut pricing\n"
        "- UNKNOWN: cannot determine strategic intent\n\n"
        "Return a JSON array where each item has: "
        '"company", "change", "category", "one_line_insight"\n\n'
        "Changes:\n" + "\n".join(summary_lines) + "\n\n"
        "Return ONLY the JSON array."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        classifications = json.loads(text)

        # Merge classifications back into changes
        class_map = {}
        for c in classifications:
            key = c.get("company", "") + "|" + c.get("change", "")
            class_map[key] = {
                "category": c.get("category", "UNKNOWN"),
                "insight": c.get("one_line_insight", ""),
            }

        for company, changes in changes_by_company.items():
            for change in changes:
                key = company + "|" + change["detail"]
                if key in class_map:
                    change["strategic_category"] = class_map[key]["category"]
                    change["insight"] = class_map[key]["insight"]

        print("AI classification complete.")

    except Exception as e:
        print("AI classification failed: " + str(e)[:100])

    return changes_by_company


def generate_report(changes_by_company, old_date, new_date):
    """Generate a markdown report of all changes."""
    lines = []
    lines.append("# SaaS Pricing Change Report")
    lines.append("")
    lines.append("**Period:** " + old_date + " to " + new_date)
    lines.append("**Generated:** " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    lines.append("")

    total_changes = sum(len(v) for v in changes_by_company.values())
    companies_changed = len(changes_by_company)

    lines.append("## Summary")
    lines.append("")
    lines.append("- **" + str(total_changes) + "** pricing changes detected")
    lines.append("- **" + str(companies_changed) + "** companies made changes")
    lines.append("")

    if total_changes == 0:
        lines.append("No pricing changes detected in this period.")
        return "\n".join(lines)

    # Count by change type
    type_counts = {}
    for changes in changes_by_company.values():
        for c in changes:
            t = c.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

    lines.append("## Changes by Type")
    lines.append("")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        label = t.replace("_", " ").title()
        lines.append("- **" + label + "**: " + str(count))
    lines.append("")

    # Strategic categories (if classified)
    cat_counts = {}
    for changes in changes_by_company.values():
        for c in changes:
            cat = c.get("strategic_category")
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

    if cat_counts:
        lines.append("## Strategic Signals")
        lines.append("")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append("- **" + cat + "**: " + str(count))
        lines.append("")

    # Detail per company
    lines.append("## Changes by Company")
    lines.append("")

    for company in sorted(changes_by_company.keys()):
        changes = changes_by_company[company]
        lines.append("### " + company)
        lines.append("")
        for c in changes:
            line = "- " + c["detail"]
            if c.get("strategic_category"):
                line = line + " [**" + c["strategic_category"] + "**]"
            if c.get("insight"):
                line = line + " -- " + c["insight"]
            lines.append(line)
        lines.append("")

    return "\n".join(lines)


def run_comparison(old_date=None, new_date=None, company_filter=None,
                   classify=False):
    """Main comparison logic."""
    snapshots = list_snapshots()

    if len(snapshots) == 0:
        print("No snapshots found in " + SNAPSHOTS_DIR + "/")
        print("Run scraper.py first to create your first snapshot.")
        return

    if len(snapshots) == 1 and not old_date:
        print("Only one snapshot found: " + snapshots[0])
        print("Run the scraper again next week to create a second snapshot,")
        print("then you can compare the two.")
        print("")
        print("Available snapshots: " + ", ".join(snapshots))
        return

    # Determine which snapshots to compare
    if old_date and new_date:
        if old_date not in snapshots:
            print("Snapshot " + old_date + " not found.")
            print("Available: " + ", ".join(snapshots))
            return
        if new_date not in snapshots:
            print("Snapshot " + new_date + " not found.")
            print("Available: " + ", ".join(snapshots))
            return
    else:
        old_date = snapshots[-2]
        new_date = snapshots[-1]

    print("")
    print("=" * 60)
    print("SaaS Pricing Change Detector")
    print("=" * 60)
    print("Comparing: " + old_date + " --> " + new_date)
    print("=" * 60)

    # Load both snapshots
    old_data = load_snapshot(old_date)
    new_data = load_snapshot(new_date)

    if not old_data or not new_data:
        return

    old_map = build_company_map(old_data)
    new_map = build_company_map(new_data)

    # Compare
    all_changes = {}
    all_companies = set(list(old_map.keys()) + list(new_map.keys()))

    if company_filter:
        all_companies = {c for c in all_companies
                         if company_filter.lower() in c.lower()}

    no_change = 0
    for company in sorted(all_companies):
        old_entry = old_map.get(company)
        new_entry = new_map.get(company)

        if old_entry and not new_entry:
            all_changes[company] = [{
                "type": "company_removed",
                "tier": "N/A",
                "detail": "Company no longer in dataset",
                "old_value": "present",
                "new_value": "missing",
            }]
        elif new_entry and not old_entry:
            all_changes[company] = [{
                "type": "company_added",
                "tier": "N/A",
                "detail": "New company added to dataset",
                "old_value": "missing",
                "new_value": "present",
            }]
        else:
            changes = compare_company(old_entry, new_entry)
            if changes:
                all_changes[company] = changes
            else:
                no_change += 1

    total = sum(len(v) for v in all_changes.values())
    print("")
    print("Results:")
    print("  Companies with changes: " + str(len(all_changes)))
    print("  Companies unchanged: " + str(no_change))
    print("  Total changes detected: " + str(total))

    # Quick summary
    if all_changes:
        print("")
        for company, changes in sorted(all_changes.items()):
            for c in changes:
                print("  " + company + ": " + c["detail"])

    # Classify with AI if requested
    if classify and all_changes:
        print("")
        print("Running AI classification...")
        all_changes = classify_changes_with_claude(all_changes)

    # Save outputs
    if all_changes:
        # Flatten for CSV
        csv_rows = []
        for company, changes in all_changes.items():
            for c in changes:
                row = {"company": company, "old_snapshot": old_date,
                       "new_snapshot": new_date}
                row.update(c)
                csv_rows.append(row)

        df = pd.DataFrame(csv_rows)
        df.to_csv(OUTPUT_CHANGES_CSV, index=False)
        print("")
        print("Changes saved to: " + OUTPUT_CHANGES_CSV)

        # Save JSON
        with open(OUTPUT_CHANGES_JSON, "w") as f:
            json.dump(all_changes, f, indent=2)
        print("JSON saved to: " + OUTPUT_CHANGES_JSON)

        # Generate report
        report = generate_report(all_changes, old_date, new_date)
        with open(OUTPUT_REPORT, "w") as f:
            f.write(report)
        print("Report saved to: " + OUTPUT_REPORT)

    print("")
    print("=" * 60)
    print("Done")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS Pricing Change Detector")
    parser.add_argument("--old", type=str,
                        help="Old snapshot date (e.g. 2025-04-17)")
    parser.add_argument("--new", type=str,
                        help="New snapshot date (e.g. 2025-04-24)")
    parser.add_argument("--company", type=str,
                        help="Filter to specific company")
    parser.add_argument("--classify", action="store_true",
                        help="Use Claude to classify change types")
    parser.add_argument("--list", action="store_true",
                        help="List available snapshots")
    args = parser.parse_args()

    if args.list:
        snaps = list_snapshots()
        if snaps:
            print("Available snapshots:")
            for s in snaps:
                print("  " + s)
        else:
            print("No snapshots found. Run scraper.py first.")
    else:
        run_comparison(
            old_date=args.old,
            new_date=args.new,
            company_filter=args.company,
            classify=args.classify,
        )
