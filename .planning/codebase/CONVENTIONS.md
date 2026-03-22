# Coding Conventions

**Analysis Date:** 2026-03-21

## Naming Patterns

**Files:**
- JavaScript modules: `kebab-case.js` (e.g., `daily-view.js`, `habit-editor.js`, `grid-view.js`)
- Python modules: `snake_case.py` (e.g., `config_loader.py`, `newsletter_detector.py`, `email_parser.py`)

**Functions:**
- JavaScript: `camelCase` for functions and methods
  - Examples: `renderDailyView()`, `escapeHtml()`, `generateId()`, `formatMonthLabel()`
  - Private helper functions use same camelCase with leading underscore pattern optional
- Python: `snake_case` for functions and methods
  - Examples: `load_config()`, `detect_newsletters()`, `extract_text()`, `_parse_message()`
  - Private/internal functions prefixed with underscore: `_is_newsletter()`, `_matches_topic()`, `_extract_body()`

**Variables:**
- JavaScript: `camelCase` for variables, state keys, and object properties
  - Examples: `currentMonthKey`, `currentView`, `habitId`, `checkedCount`
  - Constants: `UPPER_SNAKE_CASE` (e.g., `MONTH_PREFIX`, `CONFIG_KEY`, `SCOPES`)
- Python: `snake_case` for variables and parameters
  - Constants: `UPPER_SNAKE_CASE` (e.g., `SYSTEM_PROMPT`, `TOKEN_PATH`, `EXTRACTION_PROMPT`)

**Types/Classes:**
- JavaScript: No class declarations in this codebase; uses functions and objects
- Python: `PascalCase` for dataclasses and exceptions
  - Example: `RSSArticle` (dataclass in `rss_fetcher.py`)

## Code Style

**Formatting:**
- JavaScript: ES6 modules with standard indentation (2 spaces observed)
- Python: PEP 8 style, 4-space indentation
- No detected linting configuration files (`.eslintrc`, `.prettierrc`, etc.)

**Linting:**
- No explicit linter configuration detected
- JavaScript code follows standard Node/browser module patterns
- Python code follows PEP 8 conventions implicitly

## Import Organization

**JavaScript:**
- Standard ES6 module imports
- Grouped logically: imports from other local modules, then from the same directory
- Order: utility imports → view/component imports → state-related imports
- Example from `app.js`:
  ```javascript
  import { getOrCreateMonth, getConfig, saveConfig, todayInfo, formatMonthLabel, offsetMonth } from './data.js';
  import { renderDailyView } from './daily-view.js';
  import { renderGridView } from './grid-view.js';
  import { openHabitEditor } from './habit-editor.js';
  ```

**Python:**
- Standard imports first (built-in stdlib)
- Third-party imports second
- Local imports third
- Example from `main.py`:
  ```python
  import argparse
  import os
  import subprocess
  import sys
  from datetime import datetime, timedelta

  from config_loader import load_config
  from gmail_client import fetch_emails, send_email
  from newsletter_detector import detect_newsletters
  ```

**Path Aliases:**
- Not used. Local imports use relative paths like `from ./data.js`

## Error Handling

**Patterns:**
- JavaScript: Minimal error handling; relies on DOM element existence checks with `?.` optional chaining and `if (!element) return;`
  - Example in `app.js`: `document.addEventListener('DOMContentLoaded', init);` followed by safe queries
  - HTML escape functions prevent XSS: `escapeHtml()` and `escapeAttr()` used when rendering user input

- Python: Explicit try-catch blocks for known failure points
  - Example in `rss_fetcher.py`:
    ```python
    try:
        feed_articles = _fetch_single_feed(name, url, cutoff)
        articles.extend(feed_articles)
    except Exception as e:
        print(f"  Warning: Failed to fetch {name}: {e}")
    ```
  - Example in `gmail_client.py`:
    ```python
    try:
        creds.refresh(Request())
    except FileNotFoundError:
        raise FileNotFoundError(f"Missing {CREDENTIALS_PATH}...")
    ```

- Validation: Python modules validate config early (e.g., `config_loader.py` validates required sections and fields)
- Logging: Used for progress reporting (print statements) rather than structured logging

## Logging

**Framework:** `print()` statements (no formal logging library)

**Patterns:**
- Progress indicators: `print(f"Loading configuration...")`
- Info messages: `print(f"  Found {len(emails)} total emails")`
- Warnings: `print(f"  Warning: failed to push dashboard data: {e}")`
- JavaScript: Minimal logging; no console output in production code
- Python: Informational output to stdout via print; errors printed to stdout with context

## Comments

**When to Comment:**
- File-level docstrings present: Every Python module has a module-level docstring (first string literal)
  - Example from `config_loader.py`: `"""Load and validate the config.yaml configuration file."""`
- Function docstrings: All Python functions have docstrings with Args, Returns, Raises sections
- JavaScript: Minimal comments; uses comment blocks to section code logically
  - Example from `app.js`: `// ===== Month Key Helpers =====` (section headers)

**JSDoc/TSDoc:**
- Not used consistently in JavaScript files
- Python uses standard docstring format (not explicit JSDoc style)

## Function Design

**Size:** Functions are kept small and focused
- JavaScript examples:
  - `escapeHtml()`: 3 lines
  - `navigateDay()`: ~25 lines with clear logic branches
  - `renderDailyView()`: ~40 lines (includes rendering + event binding)

- Python examples:
  - `load_config()`: ~20 lines with validation
  - `_is_newsletter()`: ~15 lines with multiple heuristics
  - `extract_text()`: ~8 lines (delegates to helpers)

**Parameters:**
- JavaScript: Typically 2-4 parameters per function
  - Callbacks passed as parameters for view communication: `renderDailyView(container, monthKey, day, onNavigate)`
  - Objects for configuration data

- Python: 1-4 parameters typically
  - Configuration passed as dictionaries: `detect_newsletters(emails, sender_whitelist, keywords)`
  - Clear separation of data parameters and options

**Return Values:**
- JavaScript:
  - Render functions: `void` (modify DOM directly)
  - Data functions: Return objects or primitives (e.g., `generateId()` returns string)
  - Toggle functions: Return boolean `toggleCheck()` returns true/false for UI state

- Python:
  - Data functions: Return dicts or lists (e.g., `load_config()` returns dict, `fetch_emails()` returns list)
  - Boolean checks return True/False
  - None for side-effect functions where appropriate

## Module Design

**Exports:**
- JavaScript: Named exports via `export function name() {}`
  - Example: `export function renderDailyView(container, monthKey, day, onNavigate) {}`
  - All public functions exported, private helpers not exported

- Python: Implicit exports (any non-private function/class can be imported)
  - Private functions prefixed with underscore: `_extract_body()`, `_parse_date()`

**Barrel Files:**
- Not used. Each module handles its own scope
- Trends dashboard modules each have single responsibility: `weekly-snapshot.js`, `topic-heatmap.js`, etc.

## Global State Patterns

**JavaScript:**
- Module-level state objects for view state:
  - `app.js`: `const state = { currentMonthKey, currentDay, currentView }`
  - `habit-editor.js`: `let currentOnSave = null` (module-scope callback)
  - `app.js`: Render functions called to sync DOM with state

- No global window object manipulation except strategic exposes:
  - `window.filterByTopic = filterByTopic` in trends-dashboard `app.js` for click handlers

**Python:**
- No global state; functions are pure or use passed-in config
- Configuration loaded once at startup via `load_config()`
- Service objects created fresh on demand: `_get_service()` in gmail_client

## Security Patterns

**XSS Prevention:**
- JavaScript: HTML escaping functions used before inserting user/newsletter content:
  - `escapeHtml(habit.name)` when rendering habit names
  - `escapeAttr(habit.name)` when inserting into attributes
  - Uses DOM `textContent` instead of innerHTML where possible

**Data Validation:**
- Python config validation early: `config_loader.py` checks required sections and fields
- Newsletter detection uses keyword matching and header inspection
- Email body parsing strips script/style tags via BeautifulSoup

## Testing and Quality Practices

**Type Safety:**
- JavaScript: No TypeScript; relies on runtime checks and naming conventions
- Python: No type hints; relies on docstrings for parameter/return documentation

**Code Organization:**
- Separation of concerns: data layer (`data.js`), view layers (`daily-view.js`, `grid-view.js`), UI interactions
- Python: Clear module responsibilities (fetching, parsing, formatting, API calls)
