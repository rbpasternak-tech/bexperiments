# Testing Patterns

**Analysis Date:** 2026-03-21

## Test Framework

**No formal test framework detected.**

- No Jest, Vitest, pytest, or unittest configurations found
- No test files (*.test.js, *.spec.js, *.test.py, test_*.py) in the codebase
- No test runner scripts in package.json or pyproject.toml
- Testing is manual/ad-hoc

**Run Commands:**
- JavaScript: No automated test command (would need `npm test` or similar)
- Python: No automated test command (would need `pytest` or `python -m unittest`)

## Test File Organization

**Current State:**
- No test directories detected
- All code is in source directories without parallel test structure
- No `tests/`, `test/`, `__tests__/`, or `spec/` directories

**If Tests Were to Be Added:**
- JavaScript: Follow pattern of co-locating tests with source files or creating `tests/` at project root
  - Recommended for `js/` and `trends-dashboard/js/` modules
- Python: Create `tests/` directory at newsletter-digest root with `test_*.py` files parallel to source

## Testing Approach (Current State)

**Manual Testing Observed:**

1. **JavaScript (Browser-based):**
   - `js/app.js` initializes on `DOMContentLoaded` event
   - View functions (`renderDailyView`, `renderGridView`) are tested by running app in browser
   - Event handlers wired in-module and tested interactively
   - localStorage persistence tested by opening app multiple times
   - No automated assertions

2. **Python (CLI-based):**
   - Main entry point: `newsletter-digest/main.py` with `--dry-run` flag for testing
   - Dry-run mode prints digest to terminal instead of sending email
   - Testing flow:
     ```bash
     python main.py --dry-run              # Verify digest output
     python main.py --trends-only          # Test trend extraction
     python main.py --skip-trends          # Skip dashboard data
     ```
   - No unit tests for individual modules (config_loader, email_parser, etc.)

## Code Organization Patterns (for Testability)

**JavaScript Module Structure:**
- Pure functions: `data.js` contains utility functions that could be unit tested
  - `toMonthKey(year, month)` - Pure, deterministic
  - `parseMonthKey(monthKey)` - Pure, deterministic
  - `offsetMonth(monthKey, delta)` - Pure function with date logic
  - `daysInMonth(year, month)` - Pure utility
  - `formatMonthLabel(monthKey)` - Pure, deterministic

- Impure functions: Tied to localStorage and DOM
  - `getMonthData(monthKey)` - Accesses localStorage
  - `toggleCheck(monthKey, habitId, day)` - Mutates localStorage
  - Render functions - Mutate DOM directly

- Could be testable if refactored:
  - Move pure date logic to separate module
  - Inject localStorage operations as dependency
  - Separate render logic from event binding

**Python Module Structure:**
- Testable architecture with dependency injection:
  - `config_loader.load_config(config_path=None)` - Takes optional path parameter
  - `gmail_client.fetch_emails(lookback_days, max_emails)` - Takes parameters, returns data
  - `newsletter_detector.detect_newsletters(emails, sender_whitelist, keywords)` - Pure transformation
  - `rss_fetcher.fetch_feeds(feed_configs, lookback_days)` - Data fetching with error handling
  - `summarizer.summarize(newsletters, rss_articles, model, max_tokens)` - Pure content transformation

- All functions accept parameters; no hardcoded dependencies (except service creation in gmail_client)
- Could be unit tested with mocks for external APIs (Gmail, Claude, RSS feeds)

## Error Handling (Testing Perspective)

**JavaScript:**
- Silent failures: Many DOM queries don't check for null
  - `document.getElementById('app-content')` assumes element exists
  - Could throw runtime errors if HTML structure changes
  - No try-catch blocks in event handlers

- Design could be tested by:
  - Creating minimal HTML fixtures in tests
  - Verifying DOM mutations
  - Checking state consistency

**Python:**
- Explicit error handling with exception messages
  - `config_loader.py`: Raises ValueError for missing config sections
  - `gmail_client.py`: Raises FileNotFoundError with helpful message
  - `rss_fetcher.py`: Catches exceptions and logs warnings, continues processing
  - `main.py`: Handles subprocess errors gracefully

- Testable error cases:
  - Missing config file
  - Invalid YAML
  - Missing OAuth credentials
  - Network failures in feed fetching

## Code That Would Benefit from Testing

**JavaScript:**

1. **Pure Logic in `data.js` (High Value):**
   ```javascript
   // Tests should verify:
   // - toMonthKey(2026, 3) === "2026-03"
   // - parseMonthKey("2026-03") === { year: 2026, month: 3 }
   // - offsetMonth("2026-03", 1) === "2026-04"
   // - offsetMonth("2026-12", 1) === "2027-01" (year wrap)
   // - offsetMonth("2026-01", -1) === "2025-12" (year wrap)
   // - daysInMonth(2026, 2) === 28 (non-leap)
   // - daysInMonth(2024, 2) === 29 (leap)
   ```

2. **Habit Toggle Logic (High Value):**
   ```javascript
   // toggleCheck() should:
   // - Add day to unchecked array
   // - Remove day from checked array
   // - Return true when checking, false when unchecking
   // - Maintain sorted array
   ```

3. **Render Functions (Medium Value, Integration-style):**
   ```javascript
   // Should verify DOM structure and classes are set correctly
   // Should verify event listeners are attached
   // Could use jsdom or browser testing library
   ```

**Python:**

1. **Newsletter Detection Logic (High Value):**
   ```python
   # Tests should verify:
   # - _is_newsletter() correctly identifies mailing list headers
   # - _matches_topic() finds keywords case-insensitively
   # - Word boundaries work correctly in keyword matching
   # - Whitelisted senders are matched
   ```

2. **Config Validation (High Value):**
   ```python
   # Should test:
   # - Missing required sections raise ValueError
   # - Defaults are applied correctly
   # - Invalid YAML raises appropriate error
   ```

3. **Email Parsing (Medium Value):**
   ```python
   # Should verify:
   # - HTML to text conversion works
   # - Script/style tags removed
   # - Whitespace normalized
   # - Content truncation works
   ```

4. **Trend Extraction JSON (Medium Value):**
   ```python
   # Should verify:
   # - Claude response is valid JSON
   # - Required fields present
   # - Digest ID format correct
   # - Index.json updated properly
   ```

## If Testing Framework Were Added

**Recommended Setup for JavaScript:**
```bash
npm install --save-dev vitest jsdom @testing-library/dom
```

Example test file location: `js/__tests__/data.test.js`

```javascript
import { describe, it, expect } from 'vitest';
import { toMonthKey, parseMonthKey, offsetMonth } from '../data.js';

describe('data.js', () => {
  describe('toMonthKey', () => {
    it('formats year and month as YYYY-MM', () => {
      expect(toMonthKey(2026, 3)).toBe('2026-03');
      expect(toMonthKey(2026, 12)).toBe('2026-12');
      expect(toMonthKey(2025, 1)).toBe('2025-01');
    });
  });

  describe('offsetMonth', () => {
    it('moves forward correctly', () => {
      expect(offsetMonth('2026-03', 1)).toBe('2026-04');
      expect(offsetMonth('2026-12', 1)).toBe('2027-01');
    });

    it('moves backward correctly', () => {
      expect(offsetMonth('2026-03', -1)).toBe('2026-02');
      expect(offsetMonth('2026-01', -1)).toBe('2025-12');
    });
  });
});
```

**Recommended Setup for Python:**
```bash
pip install pytest pytest-cov pytest-mock
```

Example test file location: `newsletter-digest/tests/test_newsletter_detector.py`

```python
import pytest
from newsletter_detector import _is_newsletter, _matches_topic

class TestIsNewsletter:
    def test_list_unsubscribe_header(self):
        email = {'headers': {'list-unsubscribe': '<mailto:...>'}}
        assert _is_newsletter(email) is True

    def test_substack_sender(self):
        email = {'sender': 'newsletter@substack.com', 'headers': {}}
        assert _is_newsletter(email) is True

    def test_regular_email(self):
        email = {'sender': 'person@gmail.com', 'headers': {}}
        assert _is_newsletter(email) is False

class TestMatchesTopic:
    def test_whitelist_match(self):
        result = _matches_topic(
            {'sender': 'news@example.com', 'subject': '', 'body_text': ''},
            ['example.com'],
            []
        )
        assert result is True

    def test_keyword_match_in_subject(self):
        result = _matches_topic(
            {'sender': 'a@b.com', 'subject': 'AI breakthroughs', 'body_text': ''},
            [],
            ['AI']
        )
        assert result is True
```

## Coverage Gaps (Current State)

**Critical Untested Areas:**

1. **User Interaction Flows:**
   - Monthly navigation (prev/next buttons)
   - Habit creation/editing/deletion
   - Daily/grid view toggle
   - Drag-to-reorder in habit editor
   - Touch/swipe support

2. **Data Persistence:**
   - localStorage read/write correctness
   - Data migration between months
   - Habit carryover from previous months
   - Loss of data scenarios

3. **External API Integration:**
   - Gmail authentication flow
   - OAuth token refresh
   - API error handling (network timeouts, rate limits)
   - RSS feed failures
   - Claude API failures and fallbacks

4. **Dashboard Data:**
   - JSON validation from trend extraction
   - Week selector filtering
   - Topic filtering logic
   - Multi-digest aggregation

5. **Edge Cases:**
   - Empty habit lists
   - Leap year handling
   - Very long newsletter/article content
   - Special characters in habit names
   - Concurrent edits (if applicable)

## Manual Testing Evidence

**JavaScript:**
- Observing view transitions and DOM updates
- Verifying localStorage persists across page reloads
- Testing month navigation wraps years correctly
- Validating habit addition/removal

**Python:**
- `--dry-run` flag used to verify digest output before sending
- Print statements show progress through pipeline
- Error messages guide debugging when APIs fail
- Dashboard data files manually inspected as JSON

## Recommendations for Adding Tests

1. **Start with pure functions** in `data.js` and `newsletter_detector.py` (high ROI)
2. **Add integration tests** for main workflows (e.g., "create habit → check it → view daily progress")
3. **Mock external APIs** (Gmail, Claude, RSS) to test offline
4. **Use snapshot testing** for digest formatting (verify HTML structure doesn't change)
5. **Add E2E tests** using Playwright/Selenium for browser workflows if needed
