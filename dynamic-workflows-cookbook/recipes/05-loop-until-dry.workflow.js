// Recipe 05 — LOOP-UNTIL-DRY
// Run via Claude Code's Workflow tool: ask "run recipe 05 from the cookbook".
//
// Pattern: when you don't know how much there is to find, keep spawning finders until
// K rounds in a row turn up nothing new. Each round is told what's already been found.
// Always cap the rounds — if you hit the cap, you may not be fully drained.

export const meta = {
  name: 'cookbook-05-loop-until-dry',
  description: 'Loop-until-dry: keep finding new issues until rounds stop turning up anything new',
  phases: [{ title: 'Discover', detail: 'finder rounds until 2 dry in a row' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const CLAUSES = [
  '01-liability.txt',
  '02-governing-law.txt',
  '03-auto-renewal.txt',
  '04-notices.txt',
  '05-termination.txt',
]

const ISSUE_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          clause: { type: 'string', description: 'which clause file' },
          issue: { type: 'string', description: 'one specific problematic provision for the customer' },
        },
        required: ['clause', 'issue'],
      },
    },
  },
  required: ['issues'],
}

// State we carry across rounds — the loop is the whole point.
const seen = new Set()
const allIssues = []
let dry = 0          // consecutive rounds that found nothing new
let round = 0
const MAX_ROUNDS = 5 // cost backstop — log if we hit it

// LOOP-UNTIL-DRY: stop after 2 consecutive empty rounds (or the safety cap).
while (dry < 2 && round < MAX_ROUNDS) {
  round++
  phase(`Round ${round}`)

  // Tell the finder what's already been found so it only surfaces NEW issues.
  const exclude = allIssues.length
    ? allIssues.map(i => `- [${i.clause}] ${i.issue}`).join('\n')
    : '(nothing found yet)'

  const res = await agent(
    `Read each of these clause files in ${DIR}: ${CLAUSES.join(', ')}.\n` +
    `Find specific provisions that are problematic FOR THE CUSTOMER. ` +
    `These issues have ALREADY been found — do NOT repeat them:\n${exclude}\n\n` +
    `Return ONLY genuinely new issues not already in that list. ` +
    `If you can find no new issues, return an empty array.`,
    { label: `find:round${round}`, phase: `Round ${round}`, schema: ISSUE_SCHEMA }
  )

  // Dedup as a backstop (the exclude-list does the primary work).
  const fresh = (res?.issues || []).filter(i => {
    const key = `${i.clause}::${i.issue}`.toLowerCase().slice(0, 80)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  if (fresh.length === 0) {
    dry++
    log(`Round ${round}: nothing new (dry ${dry}/2)`)
  } else {
    dry = 0
    allIssues.push(...fresh)
    log(`Round ${round}: +${fresh.length} new (total ${allIssues.length})`)
  }
}

if (round >= MAX_ROUNDS && dry < 2) {
  log(`Stopped at safety cap of ${MAX_ROUNDS} rounds — may not be fully drained`)
}

return { totalIssues: allIssues.length, rounds: round, hitCap: round >= MAX_ROUNDS && dry < 2, issues: allIssues }