# bexperiments

A collection of personal tools and experiments, deployed via GitHub Pages.



---

## Projects

### Habit Tracker
**Live site:** https://rbpasternak-tech.github.io/bexperiments/
[`habit-tracker/`](habit-tracker/) · [Live app](https://rbpasternak-tech.github.io/bexperiments/habit-tracker/)

A progressive web app (PWA) for daily habit tracking, styled as a digital bullet journal. Built with vanilla HTML/CSS/JS and localStorage. Supports daily checklist view, monthly grid view, habit editing with carry-forward between months, and offline use via service worker.

### Newsletter Digest + Trends Dashboard
[`newsletter-digest/`](newsletter-digest/) · [`trends-dashboard/`](trends-dashboard/) · [Live dashboard](https://rbpasternak-tech.github.io/bexperiments/trends-dashboard/)

A two-part pipeline for tracking tech and legal tech trends:

- **Newsletter Digest** — Python tool that fetches Gmail newsletters and RSS feeds (TechCrunch, Ars Technica, Hacker News, Artificial Lawyer, etc.), summarizes with the Claude API, and sends a formatted HTML digest email. Runs automatically via macOS launchd.
- **Trends Dashboard** — Interactive web dashboard built from the digest data. Displays a weekly snapshot, topic heatmap, trend lines, AI economy tracker, regulatory pulse, legal tech signals, and key voices. Uses Chart.js and vanilla JS with ES modules. Data is auto-committed to this repo after each digest run.
