# Codebase Concerns

**Analysis Date:** 2026-03-21

## Tech Debt

**Event Listener Proliferation:**
- Issue: Multiple event listeners are bound every render cycle without cleanup, causing memory leaks
- Files: `js/app.js`, `js/daily-view.js`, `js/grid-view.js`, `js/habit-editor.js`
- Impact: Each render adds new listeners instead of reusing existing ones. Navigating between months repeatedly creates hundreds of dangling listeners. Dragging habits or switching views multiplies memory usage.
- Fix approach: Implement a proper event delegation pattern or use a state management system that manages listener lifecycle. Consider using element.replaceChildren() instead of innerHTML, or implement a view controller that unmounts listeners before re-rendering.

**Silent Service Worker Failure:**
- Issue: Service worker registration failures are silently swallowed with empty catch block
- Files: `js/app.js` line 30
- Impact: If service worker fails to register (network error, invalid path, browser issue), user gets no offline capability or cache updates without any feedback. Progressive degradation is lost.
- Fix approach: Log to console at minimum; consider exposing registration status to UI for debugging. Implement retry logic or health check.

**Fragile localStorage JSON Parsing:**
- Issue: JSON.parse() calls have no error handling; corrupt data crashes the app
- Files: `data.js` lines 58, 67
- Impact: If localStorage is manually edited, corrupted by browser extensions, or quota exceeded, the app fails silently with unhandled promise rejections. Users lose access to all features.
- Fix approach: Wrap all JSON.parse calls in try-catch. Return sensible defaults on parse failure. Implement data validation schema.

**Unvalidated User Input in Modal:**
- Issue: Habit names are escaped for HTML but not validated for length/character constraints before storage
- Files: `js/habit-editor.js` line 107, 114
- Impact: While XSS is prevented by escaping, no actual validation occurs. Maxlength attribute is client-side only and can be bypassed. Empty habit names are skipped (line 76) but there's no feedback to user that a habit was ignored.
- Fix approach: Implement server-side or localStorage-side validation. Add user feedback for skipped empty habits. Enforce minimum length > 0.

**Hard-coded Maximum Habit Limit:**
- Issue: 15 habit limit is enforced with alert() only, no graceful handling
- Files: `js/habit-editor.js` lines 40-42
- Impact: User sees popup but can't add more habits. No feedback about why limit exists or option to continue. Limits aren't scalable.
- Fix approach: Remove or make configurable. If kept, show limit in UI before user tries to add. Consider archiving old habits instead of hard limit.

**Lost Habit Check Data on Edit:**
- Issue: When habits are edited and reordered, check history must be manually remapped; reordering doesn't preserve check data correctly
- Files: `js/habit-editor.js` lines 69-92, `data.js` lines 145-155
- Impact: Deleting a habit loses its entire check history. Reordering habits could cause data loss if IDs aren't preserved during drag reorder. No confirmation before destructive action.
- Fix approach: Implement soft deletes (archive flag). Add confirmation dialog before deleting habits. Ensure habit IDs are immutable during reorder.

**No Undo/Redo Mechanism:**
- Issue: Deleting habits or clearing months is permanent with no recovery
- Files: `js/habit-editor.js`, `js/data.js`
- Impact: User can accidentally delete a month's work with no way to recover. One tap removes all data.
- Fix approach: Implement soft delete with recovery period. Add confirmation before destructive actions. Consider maintaining a trash/archive.

**Inadequate Error Messages:**
- Issue: Duplicate habit detection shows alert; users don't understand why their input was rejected
- Files: `js/habit-editor.js` lines 81-87
- Impact: Alert appears with error but form is still open. User must figure out which habit is a duplicate. No way to proceed except manually fix.
- Fix approach: Show inline error next to duplicate field. Highlight conflicting habit names. Allow user to resolve without closing modal.

## Known Bugs

**Touch Drag Reordering Snap Position:**
- Symptoms: When dragging habits in modal, sometimes snap position is off by one item after fast drag
- Files: `js/habit-editor.js` lines 135-153
- Trigger: Drag a habit more than one position in rapid motion (especially on slow devices)
- Cause: Using itemHeight / 2 threshold with dynamic element heights can miss position during reorder. Transform translate doesn't always sync with DOM position.
- Workaround: Drag slowly or drag one position at a time. None permanent.

**Grid View Stats Column Desync:**
- Symptoms: Stats counter (e.g., "5/15") sometimes shows wrong count after checking multiple cells quickly
- Files: `js/grid-view.js` lines 83-95
- Trigger: Rapidly click multiple cells in same row before previous event finishes
- Cause: Each click recalculates stats without debouncing. Race condition between DOM update and stat recalc.
- Workaround: Click one cell and wait for animation to finish before next click.

**Month Navigation Boundary Glitch:**
- Symptoms: Switching from Jan to Dec (previous year) sometimes shows wrong month label briefly
- Files: `js/daily-view.js` lines 107-132, `js/app.js` lines 86-91
- Trigger: Click previous month button while on January 1st
- Cause: Month key is calculated in navigateDay() but app.js also updates state separately. Double render causes flicker.
- Workaround: Click once and wait for full render.

**Empty Month Data Structure Corruption:**
- Symptoms: Switching to future months then back creates inconsistent check data structure
- Files: `data.js` lines 89-118
- Trigger: Navigate to future month, add habits, go back to past month with different habits, return to future month
- Cause: getOrCreateMonth() copies habits from prior month but doesn't properly inherit all check arrays. Structure mismatch causes undefined access.
- Workaround: Manually clear localStorage and reinitialize.

## Security Considerations

**XSS via Habit Names (Low Risk - Mitigated):**
- Risk: Habit names stored in localStorage and rendered in DOM. Could execute JS if not escaped.
- Files: `js/daily-view.js` line 47, `js/grid-view.js` line 36, 42
- Current mitigation: escapeHtml() function wraps text in div and reads .innerHTML, properly escaping. escapeAttr() used for attribute values.
- Recommendations: Use textContent assignment instead of innerHTML escape (simpler and more explicit). Add CSP header to prevent inline scripts even if XSS occurs.

**localStorage is Readable by Any Page on Same Domain:**
- Risk: If site hosts other user code or allows third-party scripts, habit data is exposed
- Files: All data access in `data.js`
- Current mitigation: None. All data is plaintext in localStorage.
- Recommendations: Only sensitive if habits contain personal information. If needed, implement client-side encryption with libsodium/tweetnacl. Use sessionStorage for temporary data.

**No CSRF Protection (PWA Context):**
- Risk: If PWA loads external data URLs, could be subject to CSRF if not properly validated
- Files: `trends-dashboard/js/data-loader.js` lines 30-66
- Current mitigation: Using fetch() with default same-origin policy. No external API calls in habit tracker itself.
- Recommendations: Trends dashboard fetches data from relative paths which is safe. If ever added external API: implement CORS validation, signature verification, or same-site cookie flags.

**Service Worker Cache Poisoning:**
- Risk: If attacker can modify files, service worker will cache malicious versions indefinitely
- Files: `service-worker.js` lines 17-23
- Current mitigation: Cache only local assets. No cache versioning strategy beyond cache name.
- Recommendations: Implement subresource integrity (SRI) for any external dependencies. Use cache busting strategy (hash filenames). Implement cache max-age headers.

## Performance Bottlenecks

**Full Re-render on Every State Change:**
- Problem: Switching views or days forces complete DOM recreation instead of partial updates
- Files: `js/app.js` lines 34-64, all render functions
- Cause: Using innerHTML = `` recreates entire subtree. No virtual DOM or differential patching.
- Impact: Noticeable lag on low-end devices with 50+ habits. Scrolling grid view is jank due to layout thrashing.
- Improvement path: Implement view state management that preserves scroll position. Use appendChild() and class toggling instead of innerHTML replacement. Consider using a lightweight framework or just update changed elements.

**O(n²) Habit Filtering in Trends Dashboard:**
- Problem: Merging and filtering arrays on every state change is inefficient
- Files: `trends-dashboard/js/data-loader.js` lines 210-220
- Cause: Building new arrays for every filter operation instead of maintaining index
- Impact: With 100+ digests and 50+ topics, filter operations take 200ms+
- Improvement path: Build indices (topic -> digest map) once during load. Cache aggregation results. Memoize filter functions.

**No Debouncing on Resize/Scroll:**
- Problem: Grid auto-scroll calculates position on every render
- Files: `js/grid-view.js` lines 64-71
- Cause: scrollLeft is recalculated even when not needed
- Impact: Minor on modern browsers, but causes reflow on each month switch
- Improvement path: Only recalculate if container width changes. Debounce scroll updates.

**localStorage Iteration Without Index:**
- Problem: getAllMonthKeys() iterates entire localStorage every time (O(n) all keys)
- Files: `data.js` lines 76-85
- Cause: No way to query only habit keys; must scan everything
- Impact: If browser has large localStorage (other sites, extensions), this gets slower. Called on app init.
- Improvement path: Store index of month keys separately. Use IDB for larger datasets.

## Fragile Areas

**Month Navigation Math:**
- Files: `data.js` lines 30-36, `js/daily-view.js` lines 107-132
- Why fragile: Month/year math with wraparound is error-prone. Off-by-one errors on boundaries (Jan/Dec). DST transitions not handled.
- Safe modification: Add comprehensive unit tests for offsetMonth(). Use Date objects consistently. Test leap years.
- Test coverage: No tests exist. Recommend 20+ test cases for boundary conditions.

**Drag Reorder State Machine:**
- Files: `js/habit-editor.js` lines 119-165
- Why fragile: Touch event state (dragItem, startY, currentY) is global in function scope. Rapid events or interrupts can leave state inconsistent.
- Safe modification: Implement proper state machine with clear enter/exit. Test with rapid fires. Consider using pointer events instead of touch.
- Test coverage: No automated tests. Requires manual testing on multiple devices.

**Modal Lifecycle:**
- Files: `js/habit-editor.js` lines 7-96, `js/app.js` lines 58-61
- Why fragile: currentOnSave callback is global module variable. Opening editor twice with different callbacks can call wrong callback.
- Safe modification: Use event emitter pattern or return promise from openHabitEditor. Store callback in modal dataset.
- Test coverage: None. Hard to test modal state programmatically with current architecture.

**Data Structure Invariants:**
- Files: `data.js` lines 89-118
- Why fragile: No validation that checks object has entries for all habits. Accessing data.checks[habitId] can be undefined. No schema enforcement.
- Safe modification: Implement data migration function on load. Add validation helper that ensures invariants. Use TypeScript or JSDoc types.
- Test coverage: None. Recommend integration tests that simulate various data scenarios.

## Scaling Limits

**localStorage Quota:**
- Current capacity: Typically 5-10MB per origin (varies by browser)
- Limit: With ~200 bytes per habit per month, can store ~2,500 habit-months before quota exceeded
- Scaling path: Migrate to IndexedDB for larger storage. Implement data archival (compress old months). Add quota warning when approaching limit.

**Habit Count Per Month:**
- Current capacity: Tested with 15, performance acceptable
- Limit: Grid view becomes slow to render at 100+ habits (full table scan on every update)
- Scaling path: Implement virtual scrolling for grid. Paginate habits. Use IndexedDB with indices.

**Browser Back Button:**
- Current capacity: No history state implemented
- Limit: Users expect back button to work but it's not supported
- Scaling path: Implement History API (pushState/popState) to track month/view changes. Store state in URL.

## Dependencies at Risk

**No External Dependencies:**
- Risk: None explicitly (no npm packages). But service worker assumes cache API available.
- Impact: Service worker doesn't fail gracefully on unsupported browser.
- Migration plan: Implement feature detection. Provide fallback UI if cache API unavailable.

**Static Data Format in Trends Dashboard:**
- Risk: JSON data schema has no versioning. Changes break parsers.
- Impact: If data format changes (e.g., new fields), old code doesn't know how to handle it
- Migration plan: Version data schema. Implement migration layer in data-loader.js. Add schema validation.

## Missing Critical Features

**Data Export/Import:**
- Problem: No way to backup habit data or migrate between devices
- Blocks: Users can't switch devices without losing history. No disaster recovery.
- Fix approach: Implement JSON export endpoint. Add drag-drop import. Consider cloud sync.

**Statistics and Insights:**
- Problem: Only shows raw counts and progress bars
- Blocks: Users can't analyze streaks, trends, or performance over time
- Fix approach: Add streak counter. Show completion rate. Add graphs of habit performance.

**Multi-Device Sync:**
- Problem: Data exists only in localStorage, no cloud sync
- Blocks: Users with multiple devices must manually track on each device
- Fix approach: Implement cloud backend (Firebase/Supabase). Add PWA sync API. Use service workers background sync.

**Dark Mode:**
- Problem: No dark mode option; CSS hardcodes light theme
- Blocks: Users on OLED devices with dark preference see glaring light theme
- Fix approach: Add CSS custom properties for dark mode. Respect prefers-color-scheme. Add manual toggle.

**Habit Templates:**
- Problem: No starter templates for common habits (exercise, meditation, water, etc.)
- Blocks: New users must manually name common habits every month
- Fix approach: Provide quick-add templates. Allow user-created templates.

## Test Coverage Gaps

**No Automated Tests:**
- What's not tested: Month navigation math, data structure invariants, event handling, localStorage integration, service worker lifecycle
- Files: ALL
- Risk: Regression bugs go undetected. Month math errors (Jan/Dec boundaries) are easy to introduce. Event listener memory leaks not caught.
- Priority: HIGH - Add unit tests for data.js first (month math, storage). Then integration tests for views.

**Manual Testing Only:**
- What's not tested: Touch interactions on actual devices, drag reorder on various screen sizes, service worker offline behavior
- Files: `js/habit-editor.js`, `service-worker.js`
- Risk: Touch bugs only found in production. Service worker may not work offline but never verified.
- Priority: HIGH - Set up automated E2E tests with playwright/cypress for touch interactions. Test offline mode.

**No Edge Case Testing:**
- What's not tested: Empty states, very long habit names, rapid navigation, concurrent event handling, leap years
- Risk: Crashes on edge cases users discover in production
- Priority: MEDIUM - Add specific tests for boundary conditions.

**Trends Dashboard Testing:**
- What's not tested: Data aggregation correctness, missing field handling, performance with large datasets
- Files: `trends-dashboard/js/data-loader.js`
- Risk: Trends calculations show wrong results but no one notices until users report
- Priority: MEDIUM - Add snapshot tests for data aggregation. Test with real digest data.

---

*Concerns audit: 2026-03-21*
