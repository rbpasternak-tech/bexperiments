// Recipe 03 — ADVERSARIAL VERIFY
// Run via Claude Code's Workflow tool: ask "run recipe 03 from the cookbook".
//
// Pattern: don't trust one agent's finding. Spawn N independent skeptics whose job is to
// REFUTE it. Keep the finding only if it survives a majority.
// This buys CONFIDENCE, not speed.

export const meta = {
  name: 'cookbook-03-adversarial-verify',
  description: 'Adversarial verify: spawn skeptics to refute each finding; keep only what survives',
  phases: [{ title: 'Verify', detail: '3 independent skeptics per finding' }],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'

// Two candidate findings. One is true; one is a deliberately planted FALSE positive,
// so we can watch verification actually catch a bad finding.
const FINDINGS = [
  {
    id: 'termination-high',
    file: '05-termination.txt',
    claim: 'HIGH risk: the provider may terminate at will with no liability while the customer cannot exit under any circumstances and owes all remaining fees.',
  },
  {
    id: 'notices-high',
    file: '04-notices.txt',
    claim: 'HIGH risk: this notices clause is dangerously one-sided against the customer.',
  },
]

const VOTE_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true if the claim is wrong or overstated; false if it holds up' },
    reason: { type: 'string', description: 'one sentence justifying the vote' },
  },
  required: ['refuted', 'reason'],
}

phase('Verify')

// For each finding, fan out 3 skeptics. Each reads the real clause and tries to REFUTE.
// majority of 3 = 2 votes. A finding "survives" only if fewer than 2 skeptics refute it.
const verified = await parallel(FINDINGS.map(f => () =>
  parallel([1, 2, 3].map(i => () =>
    agent(
      `Read the file ${DIR}/${f.file}. A reviewer made this claim about it:\n` +
      `"${f.claim}"\n\n` +
      `Your job is to REFUTE this claim if you honestly can. Be skeptical and independent. ` +
      `Set refuted=true if the claim is wrong or overstated given the actual clause text; ` +
      `set refuted=false only if the claim genuinely holds up. Give a one-sentence reason.`,
      { label: `verify:${f.id}#${i}`, phase: 'Verify', schema: VOTE_SCHEMA }
    )
  )).then(votes => {
    const v = votes.filter(Boolean)
    const refutes = v.filter(x => x.refuted).length
    return { id: f.id, file: f.file, claim: f.claim, refutes, votes: v.length, survives: refutes < 2 }
  })
))

const survivors = verified.filter(r => r.survives)
const killed = verified.filter(r => !r.survives)
log(`Verified ${verified.length} findings — ${survivors.length} survived, ${killed.length} refuted and dropped`)

return { verified, survivors: survivors.map(s => s.id), killed: killed.map(k => k.id) }
