# Technology Stack

**Analysis Date:** 2026-03-21

## Languages

**Primary:**
- JavaScript (ES6+ with modules) - Habit Tracker frontend (`js/*.js`), Trends Dashboard frontend (`trends-dashboard/js/*.js`)
- Python 3 - Newsletter digest backend (`newsletter-digest/*.py`)

**Secondary:**
- HTML5 - Web UI structure
- CSS3 - Styling

## Runtime

**Environment:**
- Web browsers (client-side JavaScript with Service Worker support)
- Python 3 (server-side for newsletter digest and trend extraction)

**Package Manager:**
- pip (Python) - for `newsletter-digest/requirements.txt`
- No Node.js/npm detected - JavaScript is vanilla/module-based

**Lockfile:**
- No lockfile for Python; `requirements.txt` uses unpinned versions

## Frameworks

**Core:**
- Web Components & DOM API - Habit Tracker frontend (no framework, vanilla JS)
- Service Workers - Offline-first caching and PWA support (`service-worker.js`)
- Chart.js v4 - Trends Dashboard data visualization (loaded from CDN via `<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js">`)

**Testing:**
- None detected

**Build/Dev:**
- No build tooling detected (vanilla HTML/CSS/JS, direct module imports)

## Key Dependencies

**Critical (Python):**
- `anthropic` - Claude API client for content summarization and trend extraction (`summarizer.py`, `trend_extractor.py`)
- `google-api-python-client` - Gmail API for email fetching and sending (`gmail_client.py`)
- `google-auth-oauthlib` - OAuth2 authentication for Gmail API
- `google-auth-httplib2` - HTTP transport for Google Auth
- `feedparser` - RSS feed parsing (`rss_fetcher.py`)
- `beautifulsoup4` - HTML parsing for RSS summary extraction (`rss_fetcher.py`)
- `pyyaml` - Configuration file parsing (`config_loader.py`)
- `python-dateutil` - Flexible date parsing for RSS entries (`rss_fetcher.py`)

**Infrastructure:**
- No external infrastructure libraries detected

## Configuration

**Environment:**
- Python: `config.yaml` (YAML format) at `newsletter-digest/config.yaml`
  - Gmail configuration (recipient, lookback days, max emails)
  - Newsletter detection filters (sender whitelist, keyword lists)
  - RSS feed configurations (9 feeds: TechCrunch, Ars Technica, The Verge, Hacker News, Artificial Lawyer, Above the Law, LawSites, One Useful Thing, How to AI)
  - Summarizer model and max tokens
  - Email digest subject prefix
- JavaScript: Minimal configuration
  - PWA manifest at `manifest.json` (hardcoded app metadata)
  - localStorage for local data persistence
  - Service Worker cache name hardcoded as `'habit-tracker-v2'`

**Build:**
- No build configuration detected
- Direct HTML/CSS/JS served as static files

## Platform Requirements

**Development:**
- Python 3 with pip
- Google OAuth credentials for Gmail API (`newsletter-digest/credentials.json` and `newsletter-digest/token.json`)
- Modern web browser with ES6 module support, Service Worker support, and localStorage
- Optional: Local development server for Python (uses local port 8090 for OAuth flow)

**Production:**
- Static file hosting for Habit Tracker and Trends Dashboard (GitHub Pages or similar)
- Python runtime environment for newsletter digest automation (likely scheduled via cron or GitHub Actions)
- Gmail API credentials with OAuth token
- Anthropic API key (via `ANTHROPIC_API_KEY` environment variable)

---

*Stack analysis: 2026-03-21*
