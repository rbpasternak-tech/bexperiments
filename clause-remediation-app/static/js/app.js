/* Dashboard controller — consumes SSE from /api/run */

const btnStart = document.getElementById('btnStart');
const eventLog = document.getElementById('eventLog');
const docGrid = document.getElementById('docGrid');
const docCount = document.getElementById('docCount');
const progressSection = document.getElementById('progressSection');
const progressLabel = document.getElementById('progressLabel');
const progressFill = document.getElementById('progressFill');
const resultsSummary = document.getElementById('resultsSummary');

const agentCards = {
  SEARCH: document.getElementById('agentSearch'),
  LEGAL: document.getElementById('agentLegal'),
  PROCESSING: document.getElementById('agentProcessing'),
};

const agentStatuses = {
  SEARCH: document.getElementById('searchStatus'),
  LEGAL: document.getElementById('legalStatus'),
  PROCESSING: document.getElementById('processingStatus'),
};

const agentStats = {
  SEARCH: document.getElementById('searchStat'),
  LEGAL: document.getElementById('legalStat'),
  PROCESSING: document.getElementById('processingStat'),
};

let docCards = {};
let totalDocs = 0;
let analyzedCount = 0;
let eventSource = null;

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function setAgentActive(agent) {
  Object.values(agentCards).forEach(c => c.classList.remove('active'));
  if (agentCards[agent]) {
    agentCards[agent].classList.add('active');
  }
}

function setAgentStatus(agent, text) {
  if (agentStatuses[agent]) {
    agentStatuses[agent].textContent = text;
  }
}

function setAgentStat(agent, text) {
  if (agentStats[agent]) {
    agentStats[agent].textContent = text;
  }
}

function addLogEntry(agent, message, isPhase) {
  const placeholder = eventLog.querySelector('.event-placeholder');
  if (placeholder) placeholder.remove();

  const entry = document.createElement('div');
  entry.className = 'event-entry' + (isPhase ? ' phase' : '');
  entry.dataset.agent = agent || 'ORCHESTRATOR';

  const tag = agent ? `<span class="agent-tag">[${escapeHtml(agent)}]</span>` : '';
  entry.innerHTML = `${tag}${escapeHtml(message)}`;
  eventLog.appendChild(entry);
  eventLog.scrollTop = eventLog.scrollHeight;
}

function addOrUpdateDocCard(docId, title, badge, detail) {
  if (docCards[docId]) {
    const card = docCards[docId];
    const badgeEl = card.querySelector('.doc-badge');
    badgeEl.className = 'doc-badge ' + badge;
    badgeEl.textContent = badge.replace('-', ' ');
    if (detail) {
      card.querySelector('.doc-detail').textContent = detail;
    }
    card.classList.add('highlight');
    setTimeout(() => card.classList.remove('highlight'), 600);
  } else {
    const card = document.createElement('div');
    card.className = 'doc-card';
    card.innerHTML = `
      <span class="doc-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
      <span class="doc-detail">${escapeHtml(detail || '')}</span>
      <span class="doc-badge ${badge}">${badge.replace('-', ' ')}</span>
    `;
    docGrid.appendChild(card);
    docCards[docId] = card;
  }
  docCount.textContent = `(${Object.keys(docCards).length})`;
}

function setProgress(pct, label) {
  progressSection.style.display = 'block';
  progressFill.style.width = pct + '%';
  if (label) progressLabel.textContent = label;
}

function handleEvent(event) {
  const d = event;

  switch (d.type) {
    case 'init':
      addLogEntry('ORCHESTRATOR', d.message);
      setAgentActive('SEARCH');
      break;

    case 'phase': {
      const phaseAgents = {
        search: 'SEARCH',
        analyze: 'LEGAL',
        draft: 'LEGAL',
        process: 'PROCESSING',
        qa: 'LEGAL',
      };
      const agent = phaseAgents[d.phase] || 'ORCHESTRATOR';
      addLogEntry(agent, d.message, true);
      setAgentActive(agent);
      setAgentStatus(agent, d.message);

      const phasePct = {search: 5, analyze: 10, draft: 55, process: 70, qa: 80};
      setProgress(phasePct[d.phase] || 0, d.message);
      break;
    }

    case 'step':
      addLogEntry(d.agent, d.message);
      setAgentStatus(d.agent, d.message);
      break;

    case 'search_complete':
      addLogEntry('SEARCH', d.message);
      setAgentStat('SEARCH', `${d.fts_count} FTS + ${d.combined_count} combined`);
      totalDocs = d.combined_count;
      break;

    case 'doc_analyze_start':
      addOrUpdateDocCard(d.doc_id, d.title, 'analyzing', d.category || '');
      setAgentStatus('LEGAL', `Analyzing: ${d.title}`);
      analyzedCount++;
      setProgress(
        10 + Math.round((analyzedCount / Math.max(totalDocs, 1)) * 40),
        `Analyzing ${d.progress}...`
      );
      break;

    case 'doc_analyze_result':
      addOrUpdateDocCard(
        d.doc_id,
        d.title,
        d.status === 'no_clause' ? 'no-clause' :
          d.status === 'needs_update' ? 'needs-update' : 'current',
        d.status === 'no_clause'
          ? `No clause (${Math.round((d.confidence || 0) * 100)}%)`
          : d.status === 'needs_update'
            ? `${d.section || '?'} • ${d.risk_level || '?'} risk`
            : `Current • ${d.section || ''}`
      );
      addLogEntry('LEGAL', d.message);
      break;

    case 'doc_draft_start':
      addOrUpdateDocCard(d.doc_id, d.title, 'drafting', 'Drafting...');
      addLogEntry('LEGAL', d.message);
      setAgentStatus('LEGAL', `Drafting: ${d.title}`);
      break;

    case 'doc_draft_result':
      addOrUpdateDocCard(d.doc_id, d.title, 'drafted', d.changes_summary);
      addLogEntry('LEGAL', d.message);
      break;

    case 'doc_process_result':
      if (d.status === 'skipped') {
        addLogEntry('PROCESSING', d.message);
      } else {
        addOrUpdateDocCard(d.doc_id, d.title, 'processed',
          `${d.clean_changes} changes + redline`);
        addLogEntry('PROCESSING', d.message);
      }
      setAgentStatus('PROCESSING', d.message);
      break;

    case 'doc_qa_start':
      addOrUpdateDocCard(d.doc_id, d.title, 'reviewing', 'QA review...');
      addLogEntry('LEGAL', d.message);
      setAgentStatus('LEGAL', `QA: ${d.title}`);
      break;

    case 'doc_qa_result':
      addOrUpdateDocCard(
        d.doc_id,
        d.title,
        d.approved ? 'approved' : 'flagged',
        d.approved ? 'QA Approved' : `Flagged: ${(d.notes || '').slice(0, 60)}...`
      );
      addLogEntry('LEGAL', d.message);
      break;

    case 'complete': {
      const r = d.results;
      setProgress(100, 'Complete');
      Object.values(agentCards).forEach(c => {
        c.classList.remove('active');
        c.classList.add('done');
      });

      document.getElementById('resSearched').textContent = r.searched;
      document.getElementById('resAnalyzed').textContent = r.analyzed;
      document.getElementById('resClauses').textContent = r.clauses_found || 0;
      document.getElementById('resUpdated').textContent = r.updated;
      document.getElementById('resApproved').textContent =
        `${r.qa_approved}/${r.qa_total || r.updated}`;
      document.getElementById('resTime').textContent = `${r.elapsed_seconds}s`;
      resultsSummary.style.display = 'block';
      resultsSummary.scrollIntoView({behavior: 'smooth'});

      setAgentStat('SEARCH', `${r.searched} docs scanned`);
      setAgentStat('LEGAL', `${r.qa_approved}/${r.qa_total || 0} approved`);
      setAgentStat('PROCESSING', `${r.updated} docs updated`);

      btnStart.disabled = false;
      btnStart.classList.remove('running');
      btnStart.textContent = 'Run Again';
      break;
    }

    case 'error':
      addLogEntry('ORCHESTRATOR', `ERROR: ${d.message}`);
      btnStart.disabled = false;
      btnStart.classList.remove('running');
      btnStart.textContent = 'Start Remediation';
      break;
  }
}

function startRemediation() {
  docCards = {};
  analyzedCount = 0;
  totalDocs = 0;
  docGrid.innerHTML = '';
  eventLog.innerHTML = '<div class="event-placeholder">Connecting...</div>';
  resultsSummary.style.display = 'none';
  progressFill.style.width = '0%';
  Object.values(agentCards).forEach(c => c.classList.remove('active', 'done'));
  Object.values(agentStatuses).forEach(s => { s.textContent = 'Idle'; });
  Object.values(agentStats).forEach(s => { s.textContent = ''; });

  btnStart.disabled = true;
  btnStart.classList.add('running');
  btnStart.textContent = 'Running...';

  const params = new URLSearchParams({
    clause_type: document.getElementById('clauseType').value,
    old_standard: document.getElementById('oldStandard').value,
    new_standard: document.getElementById('newStandard').value,
    category_filter: document.getElementById('categoryFilter').value,
  });

  if (eventSource) eventSource.close();
  eventSource = new EventSource('/api/run?' + params.toString());

  eventSource.onmessage = function(e) {
    try {
      const data = JSON.parse(e.data);
      handleEvent(data);
      if (data.type === 'complete' || data.type === 'error') {
        eventSource.close();
      }
    } catch (err) {
      console.error('SSE parse error:', err, e.data);
    }
  };

  eventSource.onerror = function() {
    eventSource.close();
    addLogEntry('ORCHESTRATOR', 'Connection lost. Check the server.');
    btnStart.disabled = false;
    btnStart.classList.remove('running');
    btnStart.textContent = 'Start Remediation';
  };
}

btnStart.addEventListener('click', startRemediation);
