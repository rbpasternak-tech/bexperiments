---
paths:
  - "**/*.js"
  - "**/*.html"
  - "**/*.css"
  - "**/*.py"
---

# Code Style

## JavaScript
- ES6 modules with `export function` (named exports, not default)
- 2-space indentation
- kebab-case filenames (e.g., `daily-view.js`)
- camelCase for variables and functions
- Always escape user/dynamic content before DOM insertion

## Python
- PEP 8, 4-space indentation
- snake_case filenames and functions
- Module-level docstring on every file
- Docstrings with Args/Returns/Raises on all functions

## General
- No build tools — code runs as-is
- Each sub-project is self-contained, no cross-project imports
- Keep functions focused and under ~50 lines where possible
