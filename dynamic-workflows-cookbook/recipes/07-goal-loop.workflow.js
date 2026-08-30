// Recipe 07 — GOAL LOOP (loop engineering)
// Run via Claude Code's Workflow tool: ask "run recipe 07 from the cookbook".
//
// Pattern: the agent loop is the unit of work. Don't hand-craft one perfect prompt —
// write a loop that DOES the work, CHECKS it with a verifier that can say "no", feeds the
// failures back as context, and repeats until the verifier signs off. Three hard stops keep
// it safe: max iterations, no-progress detection, and a token-budget ceiling.
//
// This is the "write loops, not prompts" idea: the loop converges on a verifiable GOAL,
// instead of looping for discovery (that's recipe 05, loop-until-dry).

export const meta = {
  name: 'cookbook-07-goal-loop',
  description: 'Goal loop: draft → verify → feed failures back → repeat until a verifier signs off',
  phases: [{ title: 'Converge', detail: 'draft/verify iterations until the gate passes' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const TARGET = '01-liability.txt' // the unlimited-liability clause — bad for the customer

// The GOAL, stated as checkable acceptance criteria. The verifier holds these; the loop
// stops only when every one is satisfied. A goal you can't check can't anchor a loop.
const CRITERIA = [
  'Customer liability is capped (e.g. to fees paid in the prior 12 months), not unlimited.',
  'Consequential and punitive damages are excluded, not swept in.',
  'Any indemnity is mutual or removed — not a one-sided customer-only obligation.',
  'No "notwithstanding anything to the contrary" clause that overrides the rest of the agreement.',
]

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
    failures: {
      type: 'array',
      items: { type: 'string', description: 'one unmet criterion + why it still fails' },
    },
  },
  required: ['passed', 'failures'],
}

const criteriaList = CRITERIA.map((c, i) => `${i + 1}. ${c}`).join('\n')

// State carried across iterations — the loop is the whole point.
let draft = null            // latest rewrite
let lastFailures = ''       // previous round's failures, to detect no-progress
let iter = 0
let noProgress = 0          // consecutive rounds the verifier returned the SAME failures
let outcome = 'unknown'

const MAX_ITERS = 6                 // hard stop 1: iteration cap
const MIN_BUDGET = 60_000           // hard stop 3: don't start a round we can't afford

// THE LOOP: keep going until the verifier passes, or a guard fires.
while (iter < MAX_ITERS) {
  // Hard stop 3 — budget ceiling. Only meaningful if the user set a token target this turn.
  if (budget.total && budget.remaining() < MIN_BUDGET) {
    outcome = 'budget-ceiling'
    log(`Stopping: ${Math.round(budget.remaining() / 1000)}k tokens left, under the ${MIN_BUDGET / 1000}k floor`)
    break
  }

  iter++
  phase(`Iteration ${iter}`)

  // 1) DRAFT — first round reads the file; later rounds revise given the verifier's failures.
  const draftPrompt = draft
    ? `Revise this clause so it satisfies ALL of these criteria:\n${criteriaList}\n\n` +
      `Current draft:\n"""${draft.clause}"""\n\n` +
      `The verifier REJECTED it for these reasons — fix every one:\n${lastFailures}\n\n` +
      `Return the improved clause.`
    : `Read ${DIR}/${TARGET}. It is a one-sided liability clause that is bad for the Customer.\n` +
      `Rewrite it so it satisfies ALL of these criteria:\n${criteriaList}\n\nReturn the rewritten clause.`

  draft = await agent(draftPrompt, { label: `draft:iter${iter}`, phase: `Iteration ${iter}`, schema: DRAFT_SCHEMA })
  if (!draft) { outcome = 'draft-failed'; log(`Iteration ${iter}: drafter returned nothing`); break }

  // 2) VERIFY — an INDEPENDENT agent that can say "no". This gate is what makes the loop
  //    trustworthy: a loop with nothing to push back is the agent agreeing with itself on repeat.
  const verdict = await agent(
    `You are a strict contract reviewer. Check this clause against EVERY criterion. ` +
    `Pass ONLY if all are satisfied; otherwise list each unmet criterion and why.\n\n` +
    `Criteria:\n${criteriaList}\n\nClause:\n"""${draft.clause}"""`,
    { label: `verify:iter${iter}`, phase: `Iteration ${iter}`, schema: VERDICT_SCHEMA }
  )
  if (!verdict) { outcome = 'verify-failed'; log(`Iteration ${iter}: verifier returned nothing`); break }

  // 3) DECIDE — pass exits; otherwise feed failures forward and watch for stagnation.
  if (verdict.passed) {
    outcome = 'passed'
    log(`Iteration ${iter}: verifier signed off ✓`)
    break
  }

  const failures = verdict.failures.map(f => `- ${f}`).join('\n')
  log(`Iteration ${iter}: rejected (${verdict.failures.length} unmet) — ${draft.note}`)

  // Hard stop 2 — no-progress detection. Same failures twice running = the loop is stuck;
  // burning more iterations won't help.
  if (failures === lastFailures) {
    noProgress++
    if (noProgress >= 2) {
      outcome = 'no-progress'
      log(`Stopping: verifier returned identical failures ${noProgress}x — not converging`)
      break
    }
  } else {
    noProgress = 0
  }
  lastFailures = failures
}

if (iter >= MAX_ITERS && outcome === 'unknown') outcome = 'iter-cap'

return {
  outcome,                 // 'passed' | 'no-progress' | 'iter-cap' | 'budget-ceiling' | *-failed
  iterations: iter,
  signedOff: outcome === 'passed',
  finalClause: draft?.clause ?? null,
  remainingFailures: outcome === 'passed' ? [] : lastFailures.split('\n').filter(Boolean),
}
