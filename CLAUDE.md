# CLAUDE.md — Project Instructions

## Change Approval Process

**Never edit any project file without explicit approval from Sri.** This applies to all files: dashboard.py, classify.py, scraper.py, compare.py, targets.csv, and any new files.

### Process:
1. **Propose** — Describe exactly what will change and why
2. **Wait** — Let Sri review the proposal
3. **Adjust** — Incorporate any feedback Sri gives
4. **Ask** — Request explicit approval to proceed
5. **Edit** — Only make the change after receiving a clear "yes" or approval

### This applies to:
- Adding new features or tabs to the dashboard
- Changing how the scraper, classifier, or comparator works
- Modifying the targets list
- Creating new files
- Changing any logic, layout, or data flow

## Project Structure

- **Sector / Subsector** — Use this terminology consistently (not "category" or "subcategory")
- **Sectors:** Sales & Revenue, Marketing & Analytics (more to come)
- **Snapshots:** Stored in `snapshots/YYYY-MM-DD/` with raw pages, pricing data, and scrape logs

## Weekly Workflow

```
export ANTHROPIC_API_KEY='your-key-here'
python3 scraper.py
python3 classify.py
python3 compare.py --classify
git add -f pricing_data.csv pricing_data.json pricing_changes.csv change_report.md
git commit -m "Weekly pricing update"
git push
```

## Technical Notes

- All Python code must be 100% ASCII clean (no smart quotes, em dashes, etc.) to avoid encoding errors with the Anthropic API
- Use `python3` not `python` (Mac default)
- API key is never committed — only set via `export` in Terminal
- `pricing_data.csv` is force-added to git despite being in `.gitignore` (needed for live dashboard)
- Dashboard is deployed on Streamlit Community Cloud, auto-updates on push
