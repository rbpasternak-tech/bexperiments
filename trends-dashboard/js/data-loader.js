/**
 * data-loader.js
 * Fetches the digest index and all individual digest JSON files,
 * then aggregates them into the shape expected by every dashboard section.
 */

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * Load everything the dashboard needs in one call.
 *
 * @param {string} [dataBasePath='data'] — relative path to the data directory
 * @returns {Promise<DashboardData>}
 *
 * @typedef {Object} DashboardData
 * @property {Object}   index               — contents of data/index.json
 * @property {Object[]} digests             — raw array of parsed digest objects
 * @property {Object}   latest              — the most-recent digest
 * @property {Object[]} topicTimeSeries     — [{topic, series: [{date, count}]}]
 * @property {Object[]} aggregatedEconomy   — merged ai_economy_events
 * @property {Object[]} aggregatedRegulatory— merged regulatory_events
 * @property {Object[]} aggregatedLegalTech — merged legal_tech_signals
 * @property {Object[]} aggregatedSources   — merged source_contributions
 * @property {Object}   trendAnalysis       — {emerging: [], fading: []}
 */
export async function loadAllData(dataBasePath = 'data') {
  /* ---- 1. Fetch the index ---- */
  const indexUrl = `${dataBasePath}/index.json`;
  let index;
  try {
    const res = await fetch(indexUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    index = await res.json();
  } catch (err) {
    console.error('Failed to load index.json:', err);
    return emptyResult();
  }

  /* ---- 2. Determine digest files to fetch ---- */
  const digestFiles = (index.digests || index.files || []).slice(0, 24);
  if (digestFiles.length === 0) {
    console.warn('Index contains no digest file entries.');
    return emptyResult(index);
  }

  /* ---- 3. Fetch all digests in parallel ---- */
  const digestPromises = digestFiles.map(async (entry) => {
    const file = typeof entry === 'string' ? entry : entry.file;
    const url = `${dataBasePath}/${file}`;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      return await res.json();
    } catch (err) {
      console.warn(`Skipping digest ${file}:`, err);
      return null;
    }
  });

  const rawDigests = (await Promise.all(digestPromises)).filter(Boolean);
  if (rawDigests.length === 0) {
    console.warn('No digest files loaded successfully.');
    return emptyResult(index);
  }

  /* ---- 4. Sort by date descending ---- */
  const digests = rawDigests.sort((a, b) => {
    const da = digestDate(a);
    const db = digestDate(b);
    return db.localeCompare(da);
  });

  const latest = digests[0];

  /* ---- 5. Aggregate ---- */
  const topicTimeSeries      = buildTopicTimeSeries(digests);
  const aggregatedEconomy    = mergeArrays(digests, 'ai_economy_events');
  const aggregatedRegulatory = mergeArrays(digests, 'regulatory_events');
  const aggregatedLegalTech  = mergeArrays(digests, 'legal_tech_signals');
  const aggregatedSources    = mergeArrays(digests, 'source_contributions');
  const trendAnalysis        = computeTrends(digests);

  return {
    index,
    digests,
    latest,
    topicTimeSeries,
    aggregatedEconomy,
    aggregatedRegulatory,
    aggregatedLegalTech,
    aggregatedSources,
    trendAnalysis,
  };
}

/* ------------------------------------------------------------------ */
/*  Time-Series Builder                                                */
/* ------------------------------------------------------------------ */

/**
 * Collect every unique topic name across all digests and build a
 * time-series of mention counts.
 *
 * @param {Object[]} digests
 * @returns {{topic: string, series: {date: string, count: number}[]}[]}
 */
export function buildTopicTimeSeries(digests) {
  // Map: topicName -> Map<date, count>
  const topicMap = new Map();

  // Iterate oldest-first so series are chronological
  const sorted = [...digests].sort((a, b) =>
    digestDate(a).localeCompare(digestDate(b))
  );

  for (const d of sorted) {
    const date = digestDate(d);
    const topics = d.topics || [];
    for (const t of topics) {
      const name = normalizeTopic(t.name || t.topic || 'Unknown');
      if (!topicMap.has(name)) topicMap.set(name, new Map());
      const prev = topicMap.get(name).get(date) || 0;
      topicMap.get(name).set(date, prev + (t.mention_count ?? t.count ?? 1));
    }
  }

  // Build result array
  const result = [];
  for (const [topic, dateMap] of topicMap) {
    const series = [];
    for (const [date, count] of dateMap) {
      series.push({ date, count });
    }
    result.push({ topic, series });
  }

  return result;
}

/* ------------------------------------------------------------------ */
/*  Trend Computation                                                  */
/* ------------------------------------------------------------------ */

/**
 * Identify emerging and fading topics by comparing rolling 4-week averages.
 * Emerging: >30% rise in recent average vs. prior average.
 * Fading:   >30% decline.
 *
 * @param {Object[]} digests — sorted newest-first
 * @returns {{emerging: string[], fading: string[]}}
 */
export function computeTrends(digests) {
  if (digests.length < 2) return { emerging: [], fading: [] };

  // Sort oldest-first for window slicing
  const sorted = [...digests].sort((a, b) =>
    digestDate(a).localeCompare(digestDate(b))
  );

  const windowSize = Math.min(4, Math.floor(sorted.length / 2));
  if (windowSize === 0) return { emerging: [], fading: [] };

  const recent = sorted.slice(-windowSize);
  const prior  = sorted.slice(-(windowSize * 2), -windowSize);

  if (prior.length === 0) return { emerging: [], fading: [] };

  const recentCounts = aggregateTopicCounts(recent);
  const priorCounts  = aggregateTopicCounts(prior);

  const allTopics = new Set([
    ...Object.keys(recentCounts),
    ...Object.keys(priorCounts),
  ]);

  const emerging = [];
  const fading   = [];

  for (const topic of allTopics) {
    const rc = recentCounts[topic] || 0;
    const pc = priorCounts[topic]  || 0;
    if (pc === 0 && rc > 0) {
      emerging.push(topic);
      continue;
    }
    if (pc === 0) continue;

    const change = (rc - pc) / pc;
    if (change > 0.3) emerging.push(topic);
    else if (change < -0.3) fading.push(topic);
  }

  return { emerging, fading };
}

/* ------------------------------------------------------------------ */
/*  Merge Arrays                                                       */
/* ------------------------------------------------------------------ */

/**
 * Concatenate arrays from every digest under the given key.
 * Each item is decorated with _digestDate for chronological context.
 *
 * @param {Object[]} digests
 * @param {string}   key
 * @returns {Object[]}
 */
export function mergeArrays(digests, key) {
  const result = [];
  for (const d of digests) {
    const arr = d[key];
    if (!Array.isArray(arr)) continue;
    const date = digestDate(d);
    for (const item of arr) {
      result.push({ ...item, _digestDate: date });
    }
  }
  return result;
}

/* ------------------------------------------------------------------ */
/*  Topic Name Normalization                                           */
/* ------------------------------------------------------------------ */

const TOPIC_ALIASES = {
  'AI Coding Agents': 'AI Agents',
  'AI Coding Tools': 'AI Agents',
  'Claude Code': 'AI Agents',
  'Claude Code AI': 'AI Agents',
  'Claude Computer Use': 'AI Agents',
  'Claude Computer Control': 'AI Agents',
  'Computer Use': 'AI Agents',
  'Expert Digital Twins': 'AI Agents',
  'GPT-5.4 Release': 'Large Language Models',
  'OpenAI GPT Models': 'Large Language Models',
  'OpenAI Product Changes': 'Large Language Models',
  'Perplexity Personal Computer': 'Large Language Models',
  'Machine Learning': 'Large Language Models',
  'AI Search Evolution': 'Large Language Models',
  'Claude/Anthropic': 'Large Language Models',
  'Thomson Reuters LLM': 'Legal AI Adoption',
  'Legal Tech Adoption': 'Legal AI Adoption',
  'Legal AI Growth': 'Legal AI Adoption',
  'Legal AI Tools': 'Legal AI Adoption',
  'Claude Cowork Legal Plugin': 'Legal AI Adoption',
  'AI Governance': 'AI Regulation',
  'EU AI Act': 'AI Regulation',
  'Government AI Regulation': 'AI Regulation',
  "Children's Online Safety": 'AI Regulation',
  'AI Safety Ethics': 'AI Safety & Ethics',
  'AI Sanctions & Ethics': 'AI Safety & Ethics',
  'Privacy Regulation': 'Data Privacy',
  'Legal Tech Partnerships': 'Law Firm Technology',
  'Women in Law Tech': 'Legal Practice Innovation',
  'Legal Innovation Events': 'Legal Practice Innovation',
  'Legal Innovation Hiring': 'Workforce & Jobs',
  'Legal Tech Jobs': 'Workforce & Jobs',
  'Block Layoffs': 'Workforce & Jobs',
  'Legal Tech IPOs': 'Legal Tech Funding',
  'Document Analysis AI': 'Contract Analysis AI',
  'Anthropic Pentagon Dispute': 'Enterprise AI',
  'OpenAI Pentagon Deal': 'Enterprise AI',
  'Pentagon AI Contract': 'Enterprise AI',
  'Enterprise AI Solutions': 'Enterprise AI',
  'Software Factory': 'Enterprise AI',
  'AI Computing Hardware': 'AI Infrastructure',
};

function normalizeTopic(name) {
  return TOPIC_ALIASES[name] || name;
}

/* ------------------------------------------------------------------ */
/*  Internal Helpers                                                   */
/* ------------------------------------------------------------------ */

function digestDate(d) {
  return (
    d?.meta?.date_range_end ||
    d?.meta?.date ||
    d?.meta?.week_ending ||
    d?.meta?.run_date?.slice(0, 10) ||
    d?.date ||
    'unknown'
  );
}

function aggregateTopicCounts(digests) {
  const counts = {};
  for (const d of digests) {
    for (const t of d.topics || []) {
      const name = normalizeTopic(t.name || t.topic || 'Unknown');
      counts[name] = (counts[name] || 0) + (t.mention_count ?? t.count ?? 1);
    }
  }
  return counts;
}

function emptyResult(index = {}) {
  return {
    index,
    digests: [],
    latest: null,
    topicTimeSeries: [],
    aggregatedEconomy: [],
    aggregatedRegulatory: [],
    aggregatedLegalTech: [],
    aggregatedSources: [],
    trendAnalysis: { emerging: [], fading: [] },
  };
}
