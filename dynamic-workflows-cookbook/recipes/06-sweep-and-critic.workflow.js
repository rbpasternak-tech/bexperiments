// Recipe 06 — MULTI-MODAL SWEEP + COMPLETENESS CRITIC
// Run via Claude Code's Workflow tool: ask "run recipe 06 from the cookbook".
//
// Pattern: search several DIFFERENT ways at once (each finder blind to the others), then a
// critic reads everything found and hunts for what fell between the searches.
// Buys COVERAGE + a self-check against blind spots.

export const meta = {
  name: 'cookbook-06-sweep-and-critic',
  description: 'Multi-modal sweep + completeness critic: 3 different-lens finders, then an agent that asks what was missed',
  phases: [{ title: 'Sweep' }, { title: 'Critic' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const CLAUSES = [
  '01-liability.txt',
  '02-governing-law.txt',
  '03-auto-renewal.txt',
  '04-notices.txt',
  '05-termination.txt',
]
const FILES = CLAUSES.join(', ')

// Three DIFFERENT lenses. Each finder is blind to the others — that's the point.
const LENSES = [
  { key: 'money',   desc: 'FINANCIAL & LIABILITY risk only: fees, price increases, liability caps (or lack of), indemnification scope, damages exposure.' },
  { key: 'exit',    desc: 'EXIT & LOCK-IN risk only: termination rights, auto-renewal, non-renewal windows, transition/wind-down, data return on exit.' },
  { key: 'process', desc: 'PROCESS & ENFORCEABILITY risk only: notice mechanics, governing law / jurisdiction, indemnity procedure, and drafting traps (override clauses, deeming rules, timing interactions).' },
]

const ISSUE_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          clause: { type: 'string' },
          issue: { type: 'string', description: 'one specific problem, seen through this lens' },
        },
        required: ['clause', 'issue'],
      },
    },
  },
  required: ['issues'],
}

const CRITIC_SCHEMA = {
  type: 'object',
  properties: {
    missed: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          clause: { type: 'string' },
          issue: { type: 'string', description: 'a real problem none of the three lenses surfaced' },
          whyMissed: { type: 'string', description: 'why it fell between the lenses' },
        },
        required: ['clause', 'issue', 'whyMissed'],
      },
    },
    coverageNote: { type: 'string', description: 'one line: overall, how complete was the sweep?' },
  },
  required: ['missed', 'coverageNote'],
}

// SWEEP: 3 lenses at once, each blind to the others.
phase('Sweep')
const swept = await parallel(LENSES.map(L => () =>
  agent(
    `Read each of these clause files in ${DIR}: ${FILES}.\n` +
    `Look ONLY through this lens — ${L.desc}\n` +
    `Ignore problems outside this lens. Return the issues you find through it.`,
    { label: `lens:${L.key}`, phase: 'Sweep', schema: ISSUE_SCHEMA }
  )
))

// Flatten everything the lenses found into one list for the critic to inspect.
const found = LENSES.map((L, i) => ({ lens: L.key, issues: (swept[i]?.issues) || [] }))
const foundList = found
  .flatMap(f => f.issues.map(x => `- [${f.lens}] (${x.clause}) ${x.issue}`))
  .join('\n')

// CRITIC: read the clauses + everything found, then hunt for what fell between the lenses.
phase('Critic')
const critique = await agent(
  `Three reviewers each examined these clause files (${DIR}: ${FILES}) through a different ` +
  `single lens (money, exit, process). Here is EVERYTHING they collectively found:\n\n${foundList}\n\n` +
  `Read the actual clauses yourself. Your job is COMPLETENESS: identify real problems that ` +
  `NONE of the three lenses surfaced — especially issues that fall BETWEEN the lenses or that ` +
  `a single-lens reviewer would naturally overlook. For each, say why it was missed. ` +
  `Then give a one-line note on how complete the sweep was overall.`,
  { label: 'critic', phase: 'Critic', schema: CRITIC_SCHEMA }
)

const totalFound = found.reduce((n, f) => n + f.issues.length, 0)
log(`Sweep found ${totalFound} issues across 3 lenses; critic surfaced ${critique.missed.length} more that were missed`)

return { found, totalFound, critique }