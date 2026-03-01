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

### 5. Cron Job (Automated Schedule)

To run automatically on Wednesdays and Fridays at 8am:

```bash
crontab -e
```

Add this line:

```
0 8 * * 3,5 cd /Users/rebeccapasternak/bexperiments/newsletter-digest && /Users/rebeccapasternak/bexperiments/newsletter-digest/venv/bin/python main.py >> /tmp/newsletter-digest.log 2>&1
```

Make sure your `ANTHROPIC_API_KEY` is available to cron. You can add it to the crontab:

```
ANTHROPIC_API_KEY=your-key-here
0 8 * * 3,5 cd /Users/rebeccapasternak/bexperiments/newsletter-digest && /Users/rebeccapasternak/bexperiments/newsletter-digest/venv/bin/python main.py >> /tmp/newsletter-digest.log 2>&1
```

## Usage

```bash
# Full run — fetches, summarizes, sends email
python main.py

# Dry run — prints digest to terminal, no email sent
python main.py --dry-run

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
