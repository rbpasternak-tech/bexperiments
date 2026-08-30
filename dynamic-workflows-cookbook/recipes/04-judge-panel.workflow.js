// Recipe 04 — JUDGE PANEL
// Run via Claude Code's Workflow tool: ask "run recipe 04 from the cookbook".
//
// Pattern: for an OPEN-ENDED task with no single right answer, generate several independent
// attempts from DIFFERENT angles, have a panel of judges pick the best, then synthesize a
// final that grafts in the best ideas from the runners-up.
// This buys QUALITY through divergence + selection.

export const meta = {
  name: 'cookbook-04-judge-panel',
  description: 'Judge panel: draft an open-ended clause from 3 angles, panel picks the best, synthesize a final',
  phases: [{ title: 'Draft candidates' }, { title: 'Judge' }, { title: 'Synthesize' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const FILE = '01-liability.txt'

// Three DIFFERENT angles on the same open-ended task. Diversity is the point — we want the
// solution space explored, not one take repeated three times.
const ANGLES = [
  { id: 'A', name: 'customer-protective', instruction: 'Draft the MOST customer-protective version you reasonably can while staying within market norms.' },
  { id: 'B', name: 'balanced-market',     instruction: 'Draft a BALANCED, market-standard, mutual version that most parties would readily accept.' },
  { id: 'C', name: 'minimal-change',      instruction: 'Make the SMALLEST change that removes the danger — keep the original structure, just cap and mutualize the worst parts.' },
]

const DRAFT_SCHEMA = {
  type: 'object',
  properties: {
    draft: { type: 'string', description: 'the redrafted clause text' },
    rationale: { type: 'string', description: 'one line: the thinking behind this version' },
  },
  required: ['draft', 'rationale'],
}
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    bestId: { type: 'string', enum: ['A', 'B', 'C'] },
    reason: { type: 'string', description: 'one sentence: why this one is best overall' },
  },
  required: ['bestId', 'reason'],
}
const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    finalClause: { type: 'string' },
    grafted: { type: 'string', description: 'brief: what was borrowed from the non-winning candidates' },
  },
  required: ['finalClause', 'grafted'],
}

// STAGE 1 — generate diverse candidates, all at once.
phase('Draft candidates')
const drafts = await parallel(ANGLES.map(a => () =>
  agent(
    `Read ${DIR}/${FILE}. It is a one-sided liability/indemnity clause.\n` +
    `${a.instruction}\nReturn the redrafted clause and a one-line rationale.`,
    { label: `draft:${a.id} (${a.name})`, phase: 'Draft candidates', schema: DRAFT_SCHEMA }
  )
))
const candidates = ANGLES
  .map((a, i) => ({ id: a.id, name: a.name, ...(drafts[i] || {}) }))
  .filter(c => c.draft)

const ballot = candidates.map(c => `### Candidate ${c.id} (${c.name})\n${c.draft}`).join('\n\n')

// STAGE 2 — independent panel. Each judge sees all candidates but not the other judges'
// votes (independence prevents herding toward one early opinion).
phase('Judge')
const judgments = (await parallel([1, 2, 3].map(j => () =>
  agent(
    `Three candidate redrafts of a liability clause are below. Independently decide which is ` +
    `BEST overall, weighing fairness, enforceability, and the likelihood BOTH sides would ` +
    `accept it. Pick exactly one bestId and give a one-sentence reason.\n\n${ballot}`,
    { label: `judge#${j}`, phase: 'Judge', schema: JUDGE_SCHEMA }
  )
))).filter(Boolean)

// Tally the votes -> winner. (Plain code, not an agent — counting is deterministic.)
const tally = { A: 0, B: 0, C: 0 }
judgments.forEach(v => { if (tally[v.bestId] !== undefined) tally[v.bestId]++ })
const winnerId = ['A', 'B', 'C'].sort((x, y) => tally[y] - tally[x])[0]
const winner = candidates.find(c => c.id === winnerId)

// STAGE 3 — synthesize: start from the winner, graft the best of the rest. This is what
// makes the panel beat "just pick one" — the final can exceed every candidate.
phase('Synthesize')
const final = await agent(
  `A judge panel chose Candidate ${winnerId} (${winner.name}) as the best redraft.\n` +
  `Produce a FINAL polished clause based on the winner, grafting in any clearly better ideas ` +
  `from the other candidates. Return the final clause and brief notes on what you grafted.\n\n` +
  `WINNER (${winnerId}):\n${winner.draft}\n\nALL CANDIDATES:\n${ballot}\n\n` +
  `JUDGE REASONS:\n${judgments.map((v, i) => `Judge ${i + 1} chose ${v.bestId}: ${v.reason}`).join('\n')}`,
  { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA }
)

log(`Votes — A:${tally.A} B:${tally.B} C:${tally.C} | winner: ${winnerId} (${winner.name})`)
return { tally, winnerId, winnerName: winner.name, judgments, candidates, final }
