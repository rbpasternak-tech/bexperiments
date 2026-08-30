// LOOP — goal loop on the auto-renewal clause.
// Run via Claude Code's Workflow tool: ask "run the loop workflow in loop-graph-workflows".
//
// Pattern (same shape as cookbook recipe 07): draft → independent verify → feed the
// failures back → repeat until the verifier signs off. Guards: iteration cap and
// no-progress detection.

export const meta = {
  name: 'my-loop',
  description: 'Goal loop: fix the auto-renewal clause until a strict verifier passes it',
  phases: [{ title: 'Converge', detail: 'draft/verify iterations until the gate passes' }],
}

const FILE = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses/03-auto-renewal.txt'

// The goal, stated as checkable acceptance criteria the verifier holds.
const CRITERIA = [
  'Non-renewal notice window is 30 days or less (not 90).',
  'Fee increases are capped (e.g. at most 5% or CPI) and require at least 60 days prior written notice.',
  'After a fee-increase notice, Customer may decline renewal without penalty.',
]
const criteriaList = CRITERIA.map((c, i) => `${i + 1}. ${c}`).join('\n')

const DRAFT_SCHEMA = {
  type: 'object',
  properties: {
    clause: { type: 'string', description: 'the rewritten clause text' },
    note: { type: 'string', description: 'one line: what this revision changed vs. the last' },
  },
  required: ['clause', 'note'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    passed: { type: 'boolean', description: 'true only if EVERY criterion is satisfied' },
    failures: { type: 'array', items: { type: 'string' } },
  },
  required: ['passed', 'failures'],
}

let draft = null
let lastFailures = ''
let iter = 0
let noProgress = 0
let outcome = 'unknown'
const MAX_ITERS = 4

while (iter < MAX_ITERS) {
  iter++
  phase(`Iteration ${iter}`)

  const draftPrompt = draft
    ? `Revise this clause so it satisfies ALL of these criteria:\n${criteriaList}\n\n` +
      `Current draft:\n"""${draft.clause}"""\n\n` +
      `The verifier REJECTED it for these reasons — fix every one:\n${lastFailures}`
    : `Read ${FILE}. It is a provider-friendly auto-renewal clause.\n` +
      `Rewrite it so it satisfies ALL of these criteria:\n${criteriaList}`

  draft = await agent(draftPrompt, { label: `draft:iter${iter}`, phase: `Iteration ${iter}`, schema: DRAFT_SCHEMA })
  if (!draft) { outcome = 'draft-failed'; break }

  const verdict = await agent(
    `You are a strict contract reviewer. Check this clause against EVERY criterion. ` +
    `Pass ONLY if all are satisfied; otherwise list each unmet criterion and why.\n\n` +
    `Criteria:\n${criteriaList}\n\nClause:\n"""${draft.clause}"""`,
    { label: `verify:iter${iter}`, phase: `Iteration ${iter}`, schema: VERDICT_SCHEMA }
  )
  if (!verdict) { outcome = 'verify-failed'; break }

  if (verdict.passed) {
    outcome = 'passed'
    log(`Iteration ${iter}: verifier signed off ✓`)
    break
  }

  const failures = verdict.failures.map(f => `- ${f}`).join('\n')
  log(`Iteration ${iter}: rejected (${verdict.failures.length} unmet) — ${draft.note}`)

  if (failures === lastFailures) {
    noProgress++
    if (noProgress >= 2) { outcome = 'no-progress'; break }
  } else {
    noProgress = 0
  }
  lastFailures = failures
}

if (iter >= MAX_ITERS && outcome === 'unknown') outcome = 'iter-cap'

return {
  outcome,
  iterations: iter,
  finalClause: draft?.clause ?? null,
  remainingFailures: outcome === 'passed' ? [] : lastFailures.split('\n').filter(Boolean),
}
