# Newsletter Digest

Automated twice-weekly email digest of tech and legal tech content. Pulls from your Gmail newsletters + RSS feeds, summarizes with Claude, and delivers a formatted HTML email.

## Setup

### 1. Google Cloud — Gmail API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API**: APIs & Services > Library > search "Gmail API" > Enable
4. Create OAuth credentials:
   - APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file
5. Rename the downloaded file to `credentials.json` and place it in this directory

### 2. Anthropic API Key

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Add this to your `~/.zshrc` or `~/.bashrc` to persist it.

### 3. Install Dependencies

```bash
cd newsletter-digest
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. First Run (OAuth Consent)

The first time you run the script, it will open a browser window for Gmail OAuth consent. This is a one-time step — the refresh token is saved to `token.json`.

```bash
python main.py --dry-run
```

### 5. Scheduled Runs (launchd)

The digest runs at 8:00 on Wednesdays and Fridays as a macOS launchd user
agent. Install or reinstall it with:

```bash
./install-launchd.sh
```

Why not cron, and why the pieces live where they do: this repo sits in
iCloud-synced `~/Documents` with "Optimize Mac Storage" on, which evicts idle
files to dataless placeholders. A launchd- or cron-spawned process cannot
read those back (`OSError: [Errno 11] Resource deadlock avoided`), so the
installer keeps the venv, the runner script and the log under `~/Library`,
which iCloud does not sync, and the runner calls `brctl download` on the
project before Python starts.

The Anthropic key is read from the login Keychain, never stored in the plist.
Create or rotate it with:

```bash
security add-generic-password -a "$USER" -s newsletter-digest-anthropic \
    -l "newsletter-digest Anthropic API key" -w "<your key>" -U
```

Log: `~/Library/Logs/newsletter-digest/digest.log`. Manual run through the
same wrapper: `~/Library/Application\ Support/newsletter-digest/run.sh --dry-run`.

## Usage

```bash
# Full run — fetches, summarizes, sends email
python main.py

# Dry run — prints digest to terminal, no email sent
python main.py --dry-run

# Backfill a past week's trends (no email sent)
python main.py --backfill 2025-04-15

# Use a custom config file
python main.py --config /path/to/config.yaml
```

## Configuration

Edit `config.yaml` to customize:

- **recipient_email**: Where to send the digest
- **lookback_days**: How many days back to scan (default: 4)
- **sender_whitelist**: Newsletter sender patterns to always include
- **keywords**: Tech/legal-tech keywords to match
- **rss_feeds**: RSS feed URLs to pull from
- **model**: Claude model to use for summarization

## File Overview

| File | Purpose |
|------|---------|
| `main.py` | Entry point — orchestrates the full pipeline |
| `config.yaml` | User configuration |
| `config_loader.py` | Loads and validates config |
| `gmail_client.py` | Gmail API: fetch emails + send digest |
| `newsletter_detector.py` | Identifies newsletters by headers/keywords |
| `email_parser.py` | Extracts clean text from HTML emails |
| `rss_fetcher.py` | Fetches articles from RSS feeds |
| `summarizer.py` | Claude API summarization |
| `digest_formatter.py` | Builds HTML email template |
