# SenaHill Weekly Fintech Digest

A fully automated bot that every Monday morning pulls a week of global fintech news
(AI · payments · digital assets · deals), sorts it into sections, and posts a clean
weekly read to a Slack channel.

**Free to run. No API keys, nothing to purchase.** The only thing you set up is a
free Slack webhook. Scheduling runs on GitHub Actions' free cron. There's no AI
step, so there's no per-run cost.

```
Google News RSS + trusted feeds  ->  sort into sections + de-dupe
      ->  format weekly digest  ->  Slack Incoming Webhook
```

How the sorting works without AI: each Google News search is tagged with the lane it
feeds (AI, Payments, Digital Assets, Deals), so stories are categorised accurately at
the source. Stories from the general RSS feeds are sorted by keyword rules. It's
deterministic and free. The tradeoff versus an AI version is that you get clean,
sectioned headlines with source and date, but not written "why it matters" commentary.

---

## What you need (one-time, ~10 min)

1. **A Slack Incoming Webhook** for the target channel. Step by step:
   1. Go to https://api.slack.com/apps and click the green **Create New App** button (top right), then choose **From scratch**.
   2. Give it a name (e.g. "Fintech Digest"), pick your workspace, and click **Create App**.
   3. You'll land on the app's settings page. In the **left sidebar**, under the "Features" group, click **Incoming Webhooks**.
   4. At the top of that page, flip the **Activate Incoming Webhooks** toggle to **On**. (Important: the button in the next step only appears after you turn this on.)
   5. Scroll to the bottom of the same page and click **Add New Webhook to Workspace**.
   6. Choose the channel you want the digest posted to, then click **Allow**.
   7. Back on the Incoming Webhooks page, a **Webhook URL** now appears (it starts with `https://hooks.slack.com/services/...`). Click **Copy** — that's the value you'll use as `SLACK_WEBHOOK_URL`.

2. **A GitHub repo** (private is fine) to hold this code and run the weekly schedule.

That's it. No API accounts.

---

## Deploy (runs itself weekly)

1. Create a repo and push these files (keep the .github/workflows/ folder).
2. In the repo: Settings -> Secrets and variables -> Actions -> New repository secret, add:
   - SLACK_WEBHOOK_URL  (the only secret)
3. Done. The workflow in .github/workflows/weekly-digest.yml runs every Monday.
   To test right away, go to the Actions tab -> Weekly Fintech Digest -> Run workflow.

### Changing the schedule
The schedule is UTC. Default `0 11 * * 1` = Monday 11:00 UTC, i.e. 7:00am ET (EDT) /
6:00am ET (EST). Edit the cron line in the workflow to change the day or time. The
last field is day-of-week (0=Sunday .. 6=Saturday). GitHub cron does not observe
daylight saving, so ET time drifts by an hour twice a year.

---

## Run it locally (optional)

```bash
pip install -r requirements.txt

# Preview the digest in your console without posting:
python digest.py --dry-run

# Real run (posts to Slack):
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
python digest.py
```

---

## Customizing coverage — edit config.yaml only

- sections — the buckets and their display order. Rename or reorder freely.
- google_news_queries — the main coverage engine. Each entry is a Google News search
  tagged with a section. The code auto-limits each to the lookback window. Add gl codes
  (GB, SG, IN, BR, AE, ...) to widen international reach. This is the easiest lever for
  breadth. Keep each query's section matching a name in sections.
- rss_feeds — trusted primary outlets, sorted by the keyword rules. Any feed that fails
  to load is skipped silently, so a broken URL never breaks the run.
- section_keywords / section_priority — how general RSS stories are sorted, and the
  tie-break order when a story matches more than one lane (funding wins, so a
  "raises $X for AI" story lands in Deals rather than AI).
- settings — lookback_days (default 7), max_stories_per_section, highlights_count (the
  "top reads" block; set 0 to disable), header text, timezone.

### Want it daily instead?
Set lookback_days: 1 in config.yaml and change the workflow cron to run every weekday,
e.g. `0 11 * * 1-5`.

---

## Notes

- $0 to run. RSS + Google News are free, Slack webhooks are free, and GitHub Actions'
  scheduled minutes are free for this workload.
- Google News links are redirect URLs that resolve to the publisher when clicked. Fine
  in Slack, just not always a pretty link preview. Direct RSS feeds give cleaner links.
- The bot posts nothing if the lookback window is empty, rather than posting an empty digest.
- If you ever want the AI-written "why it matters" takeaways back, that's a drop-in
  curation step we can add later (some providers even have free tiers), but the bot is
  intentionally fully API-free as shipped.

## Files

| File | Purpose |
|---|---|
| digest.py | The pipeline (fetch -> sort -> de-dupe -> post). No API. |
| config.yaml | All tuning: sources, queries, sections, keywords, settings. |
| .github/workflows/weekly-digest.yml | The weekly schedule. |
| requirements.txt | Python deps (feedparser, requests, PyYAML). |
| .env.example | Template for the one local env var. |
