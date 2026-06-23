let lastLog = null;
let sampleInbox = [];

const ICONS = { complaint: '😠', question: '❓', urgent_business: '🚨', spam: '🗑️', compliment: '💚' };

async function loadInboxPreview() {
  try {
    const r = await fetch('/api/inbox');
    const data = await r.json();
    sampleInbox = data.inbox;
    document.getElementById('inboxPreview').innerHTML = sampleInbox.map(m => `
      <div class="inbox-row">
        <div class="inbox-icon">📧</div>
        <div class="inbox-meta">
          <div class="inbox-subject">${escapeHtml(m.subject)}</div>
          <div class="inbox-from">${escapeHtml(m.from)}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Failed to load inbox preview', e);
  }
}

function switchTab(tab) {
  document.getElementById('tabSample').classList.toggle('active', tab === 'sample');
  document.getElementById('tabCustom').classList.toggle('active', tab === 'custom');
  document.getElementById('panelSample').classList.toggle('active', tab === 'sample');
  document.getElementById('panelCustom').classList.toggle('active', tab === 'custom');
  resetForm();
}

function resetForm() {
  document.getElementById('feedSection').classList.remove('show');
  document.getElementById('errorBox').classList.remove('show');
  document.getElementById('summaryCard').classList.remove('show');
}

function showError(msg) {
  const box = document.getElementById('errorBox');
  box.innerHTML = '<span style="font-size:18px">⚠️</span><span>' + msg + '</span>';
  box.classList.add('show');
  document.getElementById('statusDot').classList.remove('running');
  document.getElementById('runBtn').disabled = false;
  document.getElementById('runCustomBtn').disabled = false;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function startFeed() {
  document.getElementById('errorBox').classList.remove('show');
  document.getElementById('summaryCard').classList.remove('show');
  document.getElementById('msgResults').innerHTML = '';
  document.getElementById('feedSection').classList.add('show');
  document.getElementById('feedTitle').textContent = 'Agent working...';
  document.getElementById('statusDot').classList.add('running');
}

function createMsgCard(id, from, subject) {
  const card = document.createElement('div');
  card.className = 'msg-card';
  card.id = 'msg-' + id;
  card.innerHTML = `
    <div class="msg-card-header">
      <div>
        <div class="msg-subject">${escapeHtml(subject)}</div>
        <div class="msg-from">${escapeHtml(from)}</div>
      </div>
      <div class="cat-badge" id="cat-${id}" style="background:var(--surface2);color:var(--text-muted)">Analyzing...</div>
    </div>
    <div id="decision-${id}"></div>
    <div id="response-${id}"></div>
  `;
  document.getElementById('msgResults').appendChild(card);
}

function updateClassification(id, category, urgency, reasoning) {
  const badge = document.getElementById('cat-' + id);
  badge.className = 'cat-badge cat-' + category;
  badge.textContent = (ICONS[category] || '📨') + ' ' + category.replace('_', ' ');

  const dots = Array.from({length: 5}, (_, i) =>
    `<div class="urgency-dot ${i < urgency ? 'filled' : ''}"></div>`
  ).join('');

  document.getElementById('decision-' + id).innerHTML = `
    <div class="decision-row">
      <span>Urgency:</span>
      <div class="urgency-meter">${dots}</div>
      <span style="color:var(--text-muted)">— ${escapeHtml(reasoning)}</span>
    </div>
  `;
}

function updateDecision(id, actionLabel) {
  document.getElementById('decision-' + id).innerHTML += `
    <div class="action-tag">⚡ <strong>${escapeHtml(actionLabel)}</strong></div>
  `;
}

function updateResponse(id, response) {
  document.getElementById('response-' + id).innerHTML = `
    <div class="response-box">
      <div class="response-box-label">Agent's Response / Routing Note</div>
      ${escapeHtml(response)}
    </div>
  `;
}

function listenToStream(es) {
  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case 'status':
        break;
      case 'processing':
        createMsgCard(data.id, data.from, data.subject);
        break;
      case 'classified':
        updateClassification(data.id, data.category, data.urgency, data.reasoning);
        break;
      case 'decided':
        updateDecision(data.id, data.action_label);
        break;
      case 'responded':
        updateResponse(data.id, data.response);
        break;
      case 'error':
        showError(data.message);
        break;
      case 'done':
        lastLog = data.log;
        document.getElementById('feedTitle').textContent = 'Agent finished ✓';
        document.getElementById('statusDot').classList.remove('running');
        document.getElementById('runBtn').disabled = false;
        document.getElementById('runCustomBtn').disabled = false;
        showSummary(data.log);
        es.close();
        break;
    }
  };

  es.onerror = () => {
    showError('Connection to agent lost. Make sure the Flask server is running and GROQ_API_KEY is set.');
    es.close();
  };
}

function runTriage() {
  startFeed();
  document.getElementById('runBtn').disabled = true;
  const es = new EventSource('/api/triage');
  listenToStream(es);
}

async function runCustomTriage() {
  const from = document.getElementById('customFrom').value.trim() || 'unknown@example.com';
  const subject = document.getElementById('customSubject').value.trim() || '(no subject)';
  const body = document.getElementById('customBody').value.trim();

  if (!body) { showError('Please write a message body to triage.'); return; }

  startFeed();
  document.getElementById('runCustomBtn').disabled = true;

  try {
    const resp = await fetch('/api/triage-custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, subject, body })
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'Server error');
    }

    // Manually consume the SSE stream from a POST response
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop();
      for (const evt of events) {
        if (evt.startsWith('data: ')) {
          const data = JSON.parse(evt.slice(6));
          handleStreamEvent(data);
        }
      }
    }
  } catch (e) {
    showError(e.message);
    document.getElementById('runCustomBtn').disabled = false;
  }
}

function handleStreamEvent(data) {
  switch (data.type) {
    case 'processing':
      createMsgCard(data.id, data.from, data.subject);
      break;
    case 'classified':
      updateClassification(data.id, data.category, data.urgency, data.reasoning);
      break;
    case 'decided':
      updateDecision(data.id, data.action_label);
      break;
    case 'responded':
      updateResponse(data.id, data.response);
      break;
    case 'error':
      showError(data.message);
      break;
    case 'done':
      lastLog = data.log;
      document.getElementById('feedTitle').textContent = 'Agent finished ✓';
      document.getElementById('statusDot').classList.remove('running');
      document.getElementById('runCustomBtn').disabled = false;
      showSummary(data.log);
      break;
  }
}

function showSummary(log) {
  const counts = {};
  log.forEach(entry => {
    counts[entry.action_label] = (counts[entry.action_label] || 0) + 1;
  });
  document.getElementById('summaryGrid').innerHTML = Object.entries(counts).map(([label, count]) => `
    <div class="summary-stat">
      <div class="summary-num">${count}</div>
      <div class="summary-label">${escapeHtml(label)}</div>
    </div>
  `).join('');
  document.getElementById('summaryCard').classList.add('show');
}

function downloadLog() {
  if (!lastLog) return;
  const blob = new Blob([JSON.stringify(lastLog, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'triage_audit_log.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function checkHealth() {
  try {
    const r = await fetch('/api/health');
    const data = await r.json();
    if (!data.api_key_set) document.getElementById('setupAlert').classList.add('show');
  } catch (e) {}
}

checkHealth();
loadInboxPreview();
