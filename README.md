# SaaS Pricing Intelligence Tracker

Track and analyze pricing strategies across 50+ Sales & Revenue SaaS companies.

## What This Does

1. **Scrapes** pricing pages from target companies
2. **Classifies** the raw data using Claude (extracts tiers, prices, models, AI features)
3. **Visualizes** everything in an interactive Streamlit dashboard

## Quick Start

### 1. Install dependencies

```bash
pip install requests beautifulsoup4 pandas anthropic streamlit plotly
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

You can get a key at https://console.anthropic.com/. The classifier uses Claude Haiku, which is very cheap — classifying all 50 companies will cost roughly $0.10-0.20.

### 3. Run the scraper

```bash
# Scrape first 5 companies (test run)
python scraper.py --limit 5

# Scrape all companies
python scraper.py

# Scrape a specific company
python scraper.py --company "Apollo"
```

This creates:
- `raw_pages/` — one text file per company with the cleaned page content
- `scrape_log.csv` — status of each scrape attempt

### 4. Classify the data

```bash
# See what would be classified
python classify.py --dry-run

# Classify all scraped pages
python classify.py

# Classify one company
python classify.py --company "Apollo"
```

This creates:
- `pricing_data.csv` — structured pricing data (one row per tier per company)
- `pricing_data.json` — same data in JSON (used by dashboard)

### 5. Launch the dashboard

```bash
streamlit run dashboard.py
```

Opens an interactive dashboard at http://localhost:8501 with:
- Key metrics (companies tracked, % with public pricing, % with AI features)
- Pricing model distribution by subcategory
- Free tier vs enterprise breakdown
- Price distribution histogram
- AI feature adoption rates
- Full pricing comparison table

## Project Structure

```
saas-pricing-tracker/
├── README.md              ← you are here
├── targets.csv            ← list of companies and pricing page URLs
├── scraper.py             ← web scraper (requests + BeautifulSoup)
├── classify.py            ← Claude-powered pricing data extractor
├── dashboard.py           ← Streamlit visual dashboard
├── raw_pages/             ← scraped page text (created by scraper)
├── scrape_log.csv         ← scrape results log (created by scraper)
├── pricing_data.csv       ← structured data (created by classifier)
└── pricing_data.json      ← structured data JSON (created by classifier)
```

## How to Add Companies

Edit `targets.csv` and add rows:

```csv
company,subcategory,pricing_url
NewCompany,Sales Engagement,https://newcompany.com/pricing
```

Then re-run the scraper and classifier for that company:

```bash
python scraper.py --company "NewCompany"
python classify.py --company "NewCompany"
```

## How to Track Changes Over Time

Run the scraper weekly. Each run creates timestamped data. To build a history:

1. Before each new run, copy `pricing_data.csv` to `history/pricing_data_YYYY-MM-DD.csv`
2. After the new run, compare the two files to spot changes

A future version will automate change detection.

## Known Limitations

- **JavaScript-rendered pages**: Some pricing pages load content via JavaScript.
  The current scraper only sees static HTML. For JS-heavy sites, you'll need to
  upgrade to `scrapy-playwright` or `selenium`. These companies will show as
  having few "pricing signals" in the scrape log.
- **"Contact Sales" companies**: Companies like Gong, Clari, and Seismic don't
  publish prices. The classifier will still extract what's available (tier names,
  features, model type) but prices will be null.
- **Rate limiting**: The scraper includes a 2-second delay between requests.
  If you get blocked, increase `REQUEST_DELAY` in scraper.py.

## Scaling to 2,000 Companies

To expand to 10 sectors × 200 companies:

1. Create separate target CSV files per sector (e.g., `targets_hr.csv`, `targets_marketing.csv`)
2. Run scrapers per sector: `python scraper.py --targets targets_hr.csv`
3. Merge all `pricing_data.csv` files into one master dataset
4. The dashboard will automatically handle multi-sector data via the subcategory filter

Consider upgrading to Scrapy at this scale for better concurrency, retry handling,
and built-in rate limiting.
