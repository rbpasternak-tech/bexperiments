// Recipe 02 — PIPELINE
// Run via Claude Code's Workflow tool: ask "run recipe 02 from the cookbook".
//
// Pattern: each item flows through ordered stages (step 2 needs step 1), and items move
// independently — no barrier between stages.
// Here: per clause, analyze the problem -> draft a fix for THAT problem.

export const meta = {
  name: 'cookbook-02-pipeline',
  description: 'Pipeline: per clause, analyze the problem then draft a fix — stages chained, items flow independently',
  phases: [{ title: 'Analyze' }, { title: 'Draft fix' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'
const CLAUSES = [
  '01-liability.txt',
  '02-governing-law.txt',
  '03-auto-renewal.txt',
  '04-notices.txt',
  '05-termination.txt',
]

// Stage 1 output shape: what's the problem with this clause?
const ANALYZE_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    title: { type: 'string', description: 'short human title' },
    risk: { type: 'string', enum: ['LOW', 'MEDIUM', 'HIGH'] },
    problem: { type: 'string', description: 'the single biggest issue for the customer, or "none" if balanced' },
  },
  required: ['file', 'title', 'risk', 'problem'],
}

// Stage 2 output shape: the drafted fix (which NEEDS stage 1's "problem").
const FIX_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    risk: { type: 'string' },
    changeNeeded: { type: 'boolean' },
    suggestedFix: { type: 'string', description: 'balanced replacement language, or "no change needed"' },
  },
  required: ['file', 'risk', 'changeNeeded', 'suggestedFix'],
}

// THE PIPELINE: each clause flows stage1 -> stage2 on its own.
// No barrier between stages: clause A can be in "Draft fix" while clause B is still in "Analyze".
const results = await pipeline(
  CLAUSES,

  // STAGE 1 — analyze. Receives the clause filename.
  (name) => agent(
    `Read ${DIR}/${name}. It is a single contract clause.\n` +
    `From the CUSTOMER'S perspective, identify the single biggest problem with this clause ` +
    `(or "none" if it is balanced/standard). Assign risk LOW/MEDIUM/HIGH.\n` +
    `Return file="${name}", a short title, the risk, and the problem.`,
    { label: `analyze:${name}`, phase: 'Analyze', schema: ANALYZE_SCHEMA }
  ),

  // STAGE 2 — draft a fix. Receives STAGE 1's result. This is the dependency:
  // the fix can't be written without knowing the problem stage 1 found.
  (analysis) => agent(
    `A contract clause (${analysis.file}) was analyzed.\n` +
    `Risk: ${analysis.risk}. Problem found: "${analysis.problem}".\n` +
    `If risk is LOW, return changeNeeded=false and suggestedFix="no change needed".\n` +
    `Otherwise draft balanced, market-standard replacement language that fixes the problem ` +
    `while preserving the clause's legitimate purpose. Return file, risk, changeNeeded, suggestedFix.`,
    { label: `fix:${analysis.file}`, phase: 'Draft fix', schema: FIX_SCHEMA }
  )
)

const clean = results.filter(Boolean)
const fixed = clean.filter(r => r.changeNeeded).length
log(`Pipelined ${clean.length} clauses — drafted ${fixed} fixes, ${clean.length - fixed} needed no change`)

return { results: clean, fixesDrafted: fixed }
