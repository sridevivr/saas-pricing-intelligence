# SaaS Pricing Intelligence Tracker

Track and analyze pricing strategies across 150+ B2B SaaS companies, detect pricing changes over time, and visualize strategic trends.

## What This Does

1. **Scrapes** pricing pages from target companies weekly
2. **Classifies** the raw data using Claude AI (extracts tiers, prices, models, AI features)
3. **Compares** snapshots over time to detect pricing changes (price increases, free tier removals, AI bundling, model shifts)
4. **Visualizes** everything in an interactive Streamlit dashboard with a Pricing Changes tab

## Live Dashboard

The dashboard is deployed on Streamlit Community Cloud and updates automatically when new data is pushed to this repo.

## Sectors Covered

- **Sales & Revenue** (91 companies, 8 subsectors): Conversation Intelligence, Revenue Attribution & Analytics, Sales Engagement, Sales Enablement, CRM & Pipeline, Prospecting & Data, Quotes & Contracts, Sales Compensation
- **Marketing & Analytics** (65 companies, 6 subsectors): SEO & Content, Email & Marketing Automation, Product Analytics, Social Media Management, Advertising & Paid Media, Customer Data Platforms

## Quick Start

### 1. Install dependencies

```bash
pip install requests beautifulsoup4 pandas anthropic streamlit plotly
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY='your-key-here'
```

You can get a key at https://console.anthropic.com/. The classifier uses Claude Haiku, which is very affordable — classifying all 150+ companies costs roughly $1-2 per run.

### 3. Run the scraper

```bash
# Scrape first 5 companies (test run)
python3 scraper.py --limit 5

# Scrape all companies
python3 scraper.py

# Scrape a specific company
python3 scraper.py --company "Apollo"
```

This creates:
- `raw_pages/` — one text file per company with the cleaned page content
- `scrape_log.csv` — status of each scrape attempt
- `snapshots/YYYY-MM-DD/raw_pages/` — a dated copy for change tracking

### 4. Classify the data

```bash
# See what would be classified
python3 classify.py --dry-run

# Classify all scraped pages
python3 classify.py

# Classify one company
python3 classify.py --company "Apollo"
```

This creates:
- `pricing_data.csv` — structured pricing data (one row per tier per company)
- `pricing_data.json` — same data in JSON format
- A copy in `snapshots/YYYY-MM-DD/` for the latest snapshot

### 5. Detect pricing changes (requires 2+ snapshots)

```bash
# Compare two most recent snapshots
python3 compare.py

# Compare specific dates
python3 compare.py --old 2026-04-18 --new 2026-04-25

# With AI-powered strategic classification
python3 compare.py --classify

# Check one company
python3 compare.py --company "Apollo"

# List all available snapshots
python3 compare.py --list
```

This creates:
- `pricing_changes.csv` — all detected changes
- `pricing_changes.json` — detailed change records
- `change_report.md` — human-readable summary

### 6. Launch the dashboard

```bash
streamlit run dashboard.py
```

Opens an interactive dashboard at http://localhost:8501 with two tabs:

**Current Pricing tab:**
- Key metrics (companies tracked, % with public pricing, % with AI features, median price)
- Pricing model distribution by subsector
- Free tier vs enterprise breakdown
- Bubble chart showing where companies price their tiers
- AI feature adoption rates
- Full pricing comparison table

**Pricing Changes tab:**
- Change summary metrics (total changes, companies changed, price movements)
- Changes by type chart
- Most active companies chart
- Key signals: free tier changes, pricing model shifts, price movements
- AI feature additions and removals
- Full searchable changes table

## Weekly Workflow

Run these commands once a week to update your dataset and live dashboard:

```bash
export ANTHROPIC_API_KEY='your-key-here'
python3 scraper.py
python3 classify.py
python3 compare.py --classify
git add -f pricing_data.csv pricing_data.json pricing_changes.csv change_report.md
git commit -m "Weekly pricing update"
git push
```

Each run creates a new snapshot under `snapshots/YYYY-MM-DD/`. The compare step diffs the two most recent snapshots and detects all pricing changes.

## Project Structure

```
saas-pricing-tracker/
├── README.md              ← you are here
├── CLAUDE.md              ← project instructions for Claude
├── .gitignore             ← keeps data files out of git
├── requirements.txt       ← dependencies for Streamlit Cloud
├── targets.csv            ← list of companies and pricing page URLs
├── scraper.py             ← web scraper (requests + BeautifulSoup)
├── classify.py            ← Claude-powered pricing data extractor
├── compare.py             ← snapshot comparison and change detection
├── dashboard.py           ← Streamlit dashboard (deployed live)
├── raw_pages/             ← scraped page text (created by scraper)
├── snapshots/             ← dated snapshots for change tracking
│   ├── 2026-04-18/
│   ├── 2026-04-27/
│   └── 2026-05-05/
├── pricing_data.csv       ← latest structured data (created by classifier)
├── pricing_data.json      ← latest structured data in JSON
├── pricing_changes.csv    ← detected changes (created by compare)
└── change_report.md       ← human-readable change report
```

## How to Add Companies

Edit `targets.csv` and add rows with sector and subsector:

```csv
company,sector,subsector,pricing_url
NewCompany,Sales & Revenue,Sales Engagement,https://newcompany.com/pricing
```

Then run the scraper and classifier for that company:

```bash
python3 scraper.py --company "NewCompany"
python3 classify.py --company "NewCompany"
```

## How to Add a New Sector

1. Add companies to `targets.csv` with the new sector name and subsectors
2. Run `python3 scraper.py` and `python3 classify.py`
3. The dashboard automatically picks up new sectors in the sidebar filter

## Known Limitations

- **JavaScript-rendered pages**: Some pricing pages load content via JavaScript. The current scraper only sees static HTML. For JS-heavy sites, you would need to upgrade to `scrapy-playwright` or `selenium`. These companies will show as having few "pricing signals" in the scrape log.
- **"Contact Sales" companies**: Companies like Gong, Clari, and Seismic don't publish prices. The classifier will still extract what's available (tier names, features, model type) but prices will be null.
- **Rate limiting**: The scraper includes a 2-second delay between requests. If you get blocked, increase `REQUEST_DELAY` in scraper.py.
- **AI classification token limits**: When comparing snapshots with many changes (300+), the `--classify` flag may fail due to response length. The changes are still detected and saved — only the strategic labels are skipped.
