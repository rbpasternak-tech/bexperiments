// GRAPH — dependency-graph ("graph engineering") over the cookbook clause corpus.
// Run via Claude Code's Workflow tool: ask "run the graph workflow in loop-graph-workflows".
//
// Pattern: agents are NODES, promises are EDGES. Each node starts the moment ITS
// parents finish — there is no global barrier, no artificial phase ordering. This is
// the step past fan-out (no deps) and pipeline (linear deps): an arbitrary DAG where
// one node's output can feed several downstream nodes, and joins wait only on the
// parents they actually need.
//
//   read:liability ──┐
//   read:termination ─┼──▶ join:risk ─────┐
//                     │                   │
//   read:renewal ─────┼──▶ join:timeline ─┼──▶ memo
//   read:notices ─────┘                   │
//   read:law ────────────▶ check:law ─────┘
//
// (termination feeds BOTH risk and timeline — that shared edge is what makes this a
// graph, not a pipeline.)

export const meta = {
  name: 'my-graph',
  description: 'Dependency DAG: 5 clause readers feed 3 mid-level joins feed 1 final memo',
  phases: [
    { title: 'Read', detail: 'one leaf node per clause file' },
    { title: 'Join', detail: 'mid-level nodes fire as their parents finish' },
    { title: 'Memo', detail: 'final node joins everything' },
  ],
}

const DIR = '/Users/rebeccapasternak/bexperiments/dynamic-workflows-cookbook/corpus/clauses'

const FACTS_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    keyFacts: { type: 'array', items: { type: 'string' } },
    redFlags: { type: 'array', items: { type: 'string' }, description: 'customer-hostile terms' },
  },
  required: ['file', 'keyFacts', 'redFlags'],
}

// A node: logs when it fires (so the DAG scheduling is visible), then runs one agent.
const node = (label, phaseTitle, prompt, schema) => {
  log(`node fired: ${label}`)
  return agent(prompt, { label, phase: phaseTitle, schema })
}

const readNode = (file) =>
  node(`read:${file}`, 'Read',
    `Read ${DIR}/${file}. Extract the key facts and any customer-hostile red flags. ` +
    `Set "file" to "${file}". Be terse — bullets, not prose.`,
    FACTS_SCHEMA)

const facts = (arr) => arr.map(f => `From ${f.file}:\n- ${f.keyFacts.join('\n- ')}\nRed flags: ${f.redFlags.join('; ') || 'none'}`).join('\n\n')

// ---- LEAF NODES — no parents, all start immediately -------------------------------
const liability   = readNode('01-liability.txt')
const law         = readNode('02-governing-law.txt')
const renewal     = readNode('03-auto-renewal.txt')
const notices     = readNode('04-notices.txt')
const termination = readNode('05-termination.txt')

// ---- MID NODES — each awaits ONLY its own parents ---------------------------------
// risk needs liability + termination. It does NOT wait for renewal/notices/law.
const risk = Promise.all([liability, termination]).then(([l, t]) =>
  node('join:risk', 'Join',
    `You have extracted facts from two contract clauses:\n\n${facts([l, t].filter(Boolean))}\n\n` +
    `Assess the Customer's combined financial-risk exposure (liability + termination together). ` +
    `Return a short assessment: worst-case exposure, and the 2-3 changes that would most reduce it.`))

// timeline needs renewal + notices + termination (termination is SHARED with risk).
const timeline = Promise.all([renewal, notices, termination]).then(([r, n, t]) =>
  node('join:timeline', 'Join',
    `You have extracted facts from three contract clauses:\n\n${facts([r, n, t].filter(Boolean))}\n\n` +
    `Build the Customer's obligations timeline: every deadline, notice window, and renewal date ` +
    `mechanic, in chronological order relative to the contract term. Flag any deadline that is easy to miss.`))

// lawCheck needs only law — this chain runs completely independently of the other two.
const lawCheck = law.then(l =>
  node('check:law', 'Join',
    `Facts extracted from a governing-law clause:\n\n${facts([l].filter(Boolean))}\n\n` +
    `Briefly: what does this venue/law choice mean practically for a small US customer ` +
    `(cost to litigate, jury waiver, unusual terms)?`))

// ---- FINAL NODE — joins the three mid nodes ---------------------------------------
const [riskOut, timelineOut, lawOut] = await Promise.all([risk, timeline, lawCheck])

const memo = await node('memo', 'Memo',
  `Write a one-page executive memo for the Customer's GC combining these three analyses.\n\n` +
  `RISK ASSESSMENT:\n${riskOut}\n\nOBLIGATIONS TIMELINE:\n${timelineOut}\n\n` +
  `GOVERNING LAW:\n${lawOut}\n\n` +
  `Structure: 1) top 3 risks ranked, 2) key dates, 3) recommended redlines. Plain language.`)

return {
  nodes: 9,
  memo,
  midNodeOutputs: { risk: riskOut, timeline: timelineOut, law: lawOut },
}
