// Named workflow: clause-triage
// Promoted from dynamic-workflows-cookbook/recipes/01-fan-out.workflow.js
//
// HOW TO RUN: in Claude Code, say "run the clause-triage workflow".
//   (You can't run this with `node` — agent()/parallel() only exist inside Claude Code.)
//   Watch it live with /workflows.
//
// What it does: fans out one agent per clause in the cookbook corpus and risk-classifies
// each (LOW/MEDIUM/HIGH) from the customer's perspective, all in parallel.

export const meta = {
  name: 'clause-triage',
  description: 'Fan out and risk-classify every clause in the cookbook corpus, in parallel',
  phases: [{ title: 'Classify', detail: 'one agent per clause, running at once' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const CLAUSES = [
  '01-liability.txt',
  '02-governing-law.txt',
  '03-auto-renewal.txt',
  '04-notices.txt',
  '05-termination.txt',
]

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

const clean = results.filter(Boolean)
const high = clean.filter(r => r.risk === 'HIGH').length
log(`Classified ${clean.length} clauses — ${high} flagged HIGH risk`)

return { results: clean, highRiskCount: high }
