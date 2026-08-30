// Recipe 01 — FAN-OUT
// Run this via Claude Code's Workflow tool (not `node`): ask "run recipe 01 from the cookbook".
//
// Pattern: one task -> N independent agents, all at once -> collect results.
// Here: risk-classify 5 contract clauses in parallel instead of one-by-one.

export const meta = {
  name: 'cookbook-01-fan-out',
  description: 'Fan-out: classify the risk of each mock contract clause, all in parallel',
  phases: [{ title: 'Classify', detail: 'one agent per clause, running at once' }],
}

// The "material": 5 tiny mock clauses bundled with the cookbook.
const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const CLAUSES = [
  '01-liability.txt',
  '02-governing-law.txt',
  '03-auto-renewal.txt',
  '04-notices.txt',
  '05-termination.txt',
]

// Forcing structured output means each agent returns clean data, not prose we'd have to parse.
const SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    title: { type: 'string', description: 'short human title for the clause' },
    risk: { type: 'string', enum: ['LOW', 'MEDIUM', 'HIGH'] },
    reason: { type: 'string', description: 'one sentence: why this risk level' },
  },
  required: ['file', 'title', 'risk', 'reason'],
}

phase('Classify')

// THE FAN-OUT: parallel() takes a list of thunks (functions) and runs them concurrently.
// One agent per clause. All 5 start at roughly the same moment.
// Note `() => agent(...)` — we pass FUNCTIONS, not already-started promises, so parallel()
// controls when each one launches.
const results = await parallel(CLAUSES.map(name => () =>
  agent(
    `Read the file ${DIR}/${name}. It contains a single contract clause.\n` +
    `Assess how risky this clause is FROM THE CUSTOMER'S perspective:\n` +
    `  LOW = standard / balanced / market\n` +
    `  MEDIUM = somewhat unfavorable to the customer\n` +
    `  HIGH = clearly one-sided, uncapped, or dangerous to the customer\n` +
    `Return file="${name}", a short title, the risk level, and a one-sentence reason.`,
    { label: `classify:${name}`, phase: 'Classify', schema: SCHEMA }
  )
))

// parallel() is a BARRIER: this line runs only after ALL 5 agents have finished.
// A thunk that errors resolves to null, so filter before using the results.
const clean = results.filter(Boolean)
const high = clean.filter(r => r.risk === 'HIGH').length
log(`Classified ${clean.length} clauses — ${high} flagged HIGH risk`)

return { results: clean, highRiskCount: high }
