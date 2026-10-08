const app = document.querySelector('#app');
const toastRegion = document.querySelector('#toast-region');
const state = {
  token: localStorage.getItem('legalease-token') || '',
  user: null,
  dashboard: null,
  activeDocument: null,
  view: 'dashboard',
  authMode: 'login',
};

const icon = (name, size = 18) => {
  const icons = {
    shield: '<path d="M12 3 4.7 6v5.1c0 4.5 3 8.6 7.3 9.9 4.3-1.3 7.3-5.4 7.3-9.9V6L12 3Z"/><path d="m8.8 12 2.1 2.1 4.4-4.5"/>',
    grid: '<rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1"/><rect x="14" y="3.5" width="6.5" height="6.5" rx="1"/><rect x="3.5" y="14" width="6.5" height="6.5" rx="1"/><rect x="14" y="14" width="6.5" height="6.5" rx="1"/>',
    home: '<path d="m3.8 10.8 8.2-7 8.2 7v8.4a1.8 1.8 0 0 1-1.8 1.8H5.6a1.8 1.8 0 0 1-1.8-1.8v-8.4Z"/><path d="M9.4 21v-5.8h5.2V21"/>',
    book: '<path d="M4.5 5.3A2.3 2.3 0 0 1 6.8 3H12v16H6.8a2.3 2.3 0 0 0-2.3 2.3V5.3ZM19.5 5.3A2.3 2.3 0 0 0 17.2 3H12v16h5.2a2.3 2.3 0 0 1 2.3 2.3V5.3Z"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .35 1.88l.06.06-2.04 2.04-.06-.06a1.7 1.7 0 0 0-1.88-.35 1.7 1.7 0 0 0-1.03 1.56v.1h-2.88v-.1a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.35l-.06.06-2.04-2.04.06-.06A1.7 1.7 0 0 0 7.36 15a1.7 1.7 0 0 0-1.56-1.03h-.1v-2.88h.1a1.7 1.7 0 0 0 1.56-1.03 1.7 1.7 0 0 0-.35-1.88l-.06-.06L8.99 6.1l.06.06a1.7 1.7 0 0 0 1.88.35 1.7 1.7 0 0 0 1.03-1.56v-.1h2.88v.1a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.35l.06-.06 2.04 2.04-.06.06a1.7 1.7 0 0 0-.35 1.88 1.7 1.7 0 0 0 1.56 1.03h.1v2.88h-.1A1.7 1.7 0 0 0 19.4 15Z"/>',
    file: '<path d="M14 2.8H6.6a2 2 0 0 0-2 2v14.4a2 2 0 0 0 2 2h10.8a2 2 0 0 0 2-2V8.4L14 2.8Z"/><path d="M14 2.8v5.6h5.4M8 13h8M8 16.5h6"/>',
    upload: '<path d="M12 16V3.8M7.4 8.4 12 3.8l4.6 4.6M4 15.5v3.8a1.8 1.8 0 0 0 1.8 1.8h12.4a1.8 1.8 0 0 0 1.8-1.8v-3.8"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    download: '<path d="M12 3v12M7.5 10.5 12 15l4.5-4.5M4 20.5h16"/>',
    sparkles: '<path d="m12 3 1.55 5.45L19 10l-5.45 1.55L12 17l-1.55-5.45L5 10l5.45-1.55L12 3Z"/><path d="m19 16 .65 2.35L22 19l-2.35.65L19 22l-.65-2.35L16 19l2.35-.65L19 16Z"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7.2A4 4 0 0 1 12 3a4 4 0 0 1 4 4.2V10M12 14v3"/>',
    check: '<path d="m5 12.5 4.3 4.2L19 7"/>',
    chevron: '<path d="m9 18 6-6-6-6"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 10.8v5M12 7.5h.01"/>',
    clock: '<circle cx="12" cy="12" r="8.8"/><path d="M12 7v5l3.5 2"/>',
    logout: '<path d="M10 5H5.5A1.5 1.5 0 0 0 4 6.5v11A1.5 1.5 0 0 0 5.5 19H10M14.5 8.5 18 12l-3.5 3.5M18 12H9"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  };
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || ''}</svg>`;
};

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function prettyDate(value) {
  if (!value) return 'Just now';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value));
}

function setToken(token) {
  state.token = token || '';
  if (token) localStorage.setItem('legalease-token', token);
  else localStorage.removeItem('legalease-token');
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && state.token) {
    setToken('');
    state.user = null;
    renderAuth();
    throw new Error('Your session has ended. Please sign in again.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Something went wrong.' }));
    throw new Error(error.hint ? `${error.error} ${error.hint}` : error.error || 'Something went wrong.');
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response;
}

function toast(message, kind = 'success') {
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.innerHTML = `${kind === 'error' ? icon('info', 17) : icon('check', 17)}<span>${escapeHtml(message)}</span>`;
  toastRegion.append(node);
  window.setTimeout(() => node.remove(), 4500);
}

function authShell(content) {
  return `<main class="auth-page">
    <div class="ambient ambient-one"></div><div class="ambient ambient-two"></div>
    <section class="auth-intro">
      <a class="brand" href="#" aria-label="LegalEase home"><span class="brand-mark">${icon('shield', 21)}</span><span>Legal<span>Ease</span></span></a>
      <div class="auth-copy">
        <p class="eyebrow">CLEARER CONTRACTS. CALMER DECISIONS.</p>
        <h1>Understand before<br />you sign.</h1>
        <p>LegalEase turns complex legal language into a focused, visual review - so you know what deserves a closer look.</p>
      </div>
      <div class="trust-row"><span>${icon('lock', 16)} Privacy-first workspace</span><span>${icon('check', 16)} Informational, not legal advice</span></div>
    </section>
    <section class="auth-card-wrap">${content}</section>
  </main>`;
}

function renderAuth() {
  const isRegister = state.authMode === 'register';
  app.innerHTML = authShell(`<div class="auth-card">
    <div class="auth-card-top"><span class="mini-shield">${icon('shield', 18)}</span><span>SECURE LEGAL REVIEW</span></div>
    <h2>${isRegister ? 'Create your workspace' : 'Welcome back'}</h2>
    <p class="muted">${isRegister ? 'Set up a private place for your document reviews.' : 'Sign in to continue your document review.'}</p>
    <button class="demo-button" id="demo-access" type="button"><span class="demo-star">${icon('sparkles', 17)}</span><span><strong>Try the live demo</strong><small>Explore a complete sample analysis</small></span>${icon('arrow', 18)}</button>
    <div class="or"><span></span><em>or continue with email</em><span></span></div>
    <form id="auth-form" class="auth-form">
      ${isRegister ? '<label>Full name<input name="name" autocomplete="name" placeholder="Your name" required minlength="2" /></label>' : ''}
      <label>Email address<input name="email" autocomplete="email" type="email" placeholder="you@example.com" required /></label>
      <label>Password<input name="password" autocomplete="current-password" type="password" placeholder="${isRegister ? 'At least 8 characters' : 'Your password'}" required minlength="8" /></label>
      <button class="primary-button full" type="submit"><span>${isRegister ? 'Create account' : 'Sign in'}</span>${icon('arrow', 17)}</button>
    </form>
    <p class="auth-switch">${isRegister ? 'Already have an account?' : 'New to LegalEase?'} <button class="link-button" id="auth-switch" type="button">${isRegister ? 'Sign in' : 'Create an account'}</button></p>
    <p class="fine-print">By continuing, you agree to use this student-project demonstration only for informational review.</p>
  </div>`);
  document.querySelector('#demo-access').addEventListener('click', startDemo);
  document.querySelector('#auth-switch').addEventListener('click', () => { state.authMode = isRegister ? 'login' : 'register'; renderAuth(); });
  document.querySelector('#auth-form').addEventListener('submit', submitAuth);
}

async function submitAuth(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true, state.authMode === 'register' ? 'Creating workspace...' : 'Signing in...');
  try {
    const body = Object.fromEntries(new FormData(form));
    const result = await api(`/api/auth/${state.authMode === 'register' ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(body) });
    setToken(result.token);
    state.user = result.user;
    await loadDashboard();
    toast(state.authMode === 'register' ? 'Your workspace is ready.' : 'Welcome back.');
  } catch (error) {
    toast(error.message, 'error');
    setButtonLoading(button, false);
  }
}

async function startDemo() {
  const button = document.querySelector('#demo-access');
  setButtonLoading(button, true, 'Opening demo...');
  try {
    const result = await api('/api/auth/demo', { method: 'POST', body: '{}' });
    setToken(result.token);
    state.user = result.user;
    await loadDashboard();
    toast('Demo workspace ready - sample agreement loaded.');
  } catch (error) {
    toast(error.message, 'error');
    setButtonLoading(button, false);
  }
}

function setButtonLoading(button, loading, label = 'Loading...') {
  if (!button) return;
  if (loading) {
    button.dataset.label = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span><span>${escapeHtml(label)}</span>`;
  } else {
    button.disabled = false;
    if (button.dataset.label) button.innerHTML = button.dataset.label;
  }
}

async function loadDashboard() {
  try {
    const result = await api('/api/dashboard');
    state.user = result.user;
    state.dashboard = result;
    state.view = 'dashboard';
    state.activeDocument = null;
    renderWorkspace();
  } catch (error) { toast(error.message, 'error'); }
}

function navItem(view, label, iconName, badge = '') {
  return `<button class="nav-item ${state.view === view ? 'selected' : ''}" data-view="${view}" type="button">${icon(iconName, 18)}<span>${label}</span>${badge ? `<b>${badge}</b>` : ''}</button>`;
}

function workspaceShell(mainContent) {
  const initials = (state.user?.name || 'LE').split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase();
  return `<div class="workspace-shell reference-shell">
    <header class="top-nav">
      <a class="brand top-brand" href="#" aria-label="LegalEase home"><span class="brand-mark">${icon('shield', 21)}</span><span>Legal<span>Ease</span></span></a>
      <nav class="top-actions" aria-label="Workspace navigation">
        <button class="nav-orb ${state.view === 'dashboard' ? 'selected' : ''}" data-view="dashboard" type="button" title="Overview">${icon('home', 18)}</button>
        <button class="nav-orb ${state.view === 'documents' ? 'selected' : ''}" data-view="documents" type="button" title="My documents">${icon('file', 18)}</button>
        <button class="nav-orb" data-action="guide" type="button" title="How LegalEase works">${icon('book', 18)}</button>
        <button class="nav-orb" data-action="settings" type="button" title="Workspace settings">${icon('settings', 18)}</button>
        <span class="nav-divider"></span>
        <button id="logout" class="profile-menu" type="button" title="Sign out"><span class="avatar">${escapeHtml(initials)}</span><span class="profile-name">${escapeHtml(state.user?.name || '')}</span>${icon('chevron', 15)}</button>
      </nav>
    </header>
    <main class="app-main">${mainContent}</main>
  </div>`;
}

function documentCard(document, compact = false) {
  const analysis = document.analysis;
  const counts = analysis.counts;
  return `<button type="button" class="document-card ${compact ? 'compact' : ''}" data-open-document="${document.id}">
    <span class="document-icon">${icon('file', 21)}</span><span class="document-copy"><strong>${escapeHtml(document.filename)}</strong><small>${prettyDate(document.created_at)} <i></i> ${analysis.clauses.length} review items</small></span>
    <span class="doc-risk ${counts.high ? 'high' : counts.medium ? 'medium' : 'low'}">${counts.high ? `${counts.high} high priority` : counts.medium ? `${counts.medium} review items` : 'Low priority'}</span>${icon('chevron', 18)}
  </button>`;
}

function uploadPanel() {
  return `<section class="upload-panel" id="upload-panel">
    <label class="drop-zone" id="drop-zone"><input id="file-input" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" /><span class="drop-icon">${icon('upload', 29)}</span><span class="drop-copy"><strong>Drop your document here</strong><small>or <em>browse files</em> from your computer</small></span><span class="file-limits">${icon('file', 15)} PDF or DOCX <i></i> Maximum file size: 10 MB</span></label>
    <div class="upload-foot"><span>${icon('lock', 15)} Your document stays in your private workspace</span><button class="text-action" id="sample-analysis" type="button">Use our sample agreement ${icon('arrow', 15)}</button></div>
  </section>`;
}

function dashboardView() {
  const documents = state.dashboard?.documents || [];
  const stats = state.dashboard?.stats || { documents: 0, high: 0, clauses: 0 };
  const firstName = (state.user?.name || 'there').split(' ')[0];
  const recent = documents.length ? `<button class="recent-document" data-open-document="${documents[0].id}" type="button">${escapeHtml(documents[0].filename)} ${icon('arrow', 17)}</button>` : `<span class="recent-document empty">No documents yet ${icon('arrow', 17)}</span>`;
  return `<div class="page-content dashboard-page">
    <section class="reference-hero"><p class="eyebrow teal">WELCOME BACK, ${escapeHtml(firstName).toUpperCase()}</p><h1>Understand your legal documents<br /><span>with confidence.</span></h1><p>Upload a PDF or DOCX and LegalEase will break down complex legal language, identify important clauses, highlight potential concerns, and explain what they mean in plain language.</p></section>
    ${uploadPanel()}
    <section class="activity-strip"><div class="recent-activity"><p class="eyebrow">YOUR RECENT ACTIVITY</p>${recent}</div><div class="activity-metrics"><div>${icon('file', 18)}<span><b>${stats.documents}</b><small>Documents reviewed</small></span></div><div>${icon('info', 18)}<span><b>${stats.high}</b><small>High-risk items</small></span></div><div>${icon('sparkles', 18)}<span><b>${stats.clauses}</b><small>Clauses explained</small></span></div></div></section>
    ${documents.length ? `<section class="recent-section"><div class="section-heading"><div><p class="eyebrow teal">READY WHEN YOU ARE</p><h3>Continue a review</h3></div><button class="text-action" data-view="documents" type="button">View all documents ${icon('arrow', 15)}</button></div><div class="documents-list">${documents.slice(0, 2).map((document) => documentCard(document)).join('')}</div></section>` : ''}
    <footer class="workspace-footer">By using LegalEase, you agree that AI can make mistakes. LegalEase provides informational support and is not a replacement for professional legal advice.</footer>
  </div>`;
}

function documentsView() {
  const documents = state.dashboard?.documents || [];
  return `<div class="page-content documents-page"><div class="list-title"><div><p class="eyebrow teal">YOUR PRIVATE WORKSPACE</p><h1>Documents, made clearer.</h1><p>Each analysis stays connected to the original text and visible only within its owner’s workspace.</p></div><button class="primary-button" id="library-upload" type="button">${icon('upload', 17)} Upload document</button></div>
    <section class="library-panel">${documents.length ? documents.map((document) => documentCard(document)).join('') : '<div class="empty-state">Your library is empty.</div>'}</section></div>`;
}

function severityClass(risk) { return String(risk || '').toLowerCase(); }

function highlightedText(text, clauses) {
  const highlights = clauses.filter((clause) => Number.isInteger(clause.source_start) && Number.isInteger(clause.source_end)).sort((a, b) => a.source_start - b.source_start);
  let cursor = 0;
  let html = '';
  highlights.forEach((clause) => {
    if (clause.source_start < cursor) return;
    html += escapeHtml(text.slice(cursor, clause.source_start));
    html += `<mark class="text-highlight ${severityClass(clause.risk)}" data-highlight="${escapeHtml(clause.id)}"><span class="highlight-label">${escapeHtml(clause.risk)} · ${escapeHtml(clause.title)}</span>${escapeHtml(text.slice(clause.source_start, clause.source_end))}</mark>`;
    cursor = clause.source_end;
  });
  return html + escapeHtml(text.slice(cursor));
}

function clauseCard(clause, index) {
  return `<button class="clause-card ${severityClass(clause.risk)}" data-clause="${escapeHtml(clause.id)}" type="button"><span class="clause-rank">${String(index + 1).padStart(2, '0')}</span><span class="clause-card-main"><span class="risk-line"><b>${escapeHtml(clause.risk)} PRIORITY</b>${clause.missing ? '<em>NOT DETECTED</em>' : `<small>Risk signal ${clause.score}/100</small>`}</span><strong>${escapeHtml(clause.title)}</strong><span>${escapeHtml(clause.plain_english)}</span></span>${icon('chevron', 18)}</button>`;
}

function documentView(document) {
  const analysis = document.analysis;
  const high = analysis.counts.high;
  return `<div class="analysis-page"><div class="analysis-topbar"><button class="back-button" data-view="documents" type="button">← Back to documents</button><div class="top-actions"><span class="engine-label">${icon('sparkles', 14)} ${escapeHtml(document.engine)}</span><button class="secondary-button" id="download-report" type="button">${icon('download', 16)} Download report</button></div></div>
    <section class="analysis-title"><div><p class="eyebrow teal">ANALYSIS COMPLETE</p><h1>${escapeHtml(document.filename)}</h1><p>${escapeHtml(document.summary)}</p></div><div class="score-orb"><strong>${analysis.score}</strong><span>review score</span></div></section>
    <div class="analysis-metrics"><span><b>${analysis.clauses.length}</b> items found</span><span class="dot-divider"></span><span class="high-text"><b>${high}</b> high priority</span><span class="dot-divider"></span><span>Processed ${prettyDate(document.created_at)}</span></div>
    <section class="analysis-grid"><article class="original-pane"><div class="pane-heading"><div><p>ORIGINAL DOCUMENT</p><span>Highlighted where LegalEase found key language</span></div><span class="file-pill">${icon('file', 14)} ${document.mime_type === 'text/plain' ? 'Sample agreement' : 'Uploaded file'}</span></div><div class="document-text" id="document-text">${highlightedText(document.text, analysis.clauses)}</div></article>
      <aside class="review-pane"><div class="pane-heading"><div><p>YOUR REVIEW</p><span>Plain-language explanations</span></div><span class="priority-badge">${high} HIGH</span></div><div class="review-callout">${icon('info', 16)} Select a review item to jump to its source text.</div><div class="clause-list">${analysis.clauses.map(clauseCard).join('')}</div></aside></section>
    <section class="analysis-disclaimer">${icon('shield', 17)} <span><strong>Keep the decision yours.</strong> These results are generated for informational purposes and may miss context. Ask a qualified legal professional for advice tailored to your situation.</span></section>
  </div>`;
}

function renderWorkspace() {
  let view = '';
  if (state.view === 'documents') view = documentsView();
  else if (state.view === 'document' && state.activeDocument) view = documentView(state.activeDocument);
  else view = dashboardView();
  app.innerHTML = workspaceShell(view);
  bindWorkspaceEvents();
}

function renderLoadingDocument() {
  app.innerHTML = workspaceShell(`<div class="loading-view"><span class="large-spinner"></span><h3>Preparing your review</h3><p>Loading the original document and clause explanations…</p></div>`);
  bindWorkspaceEvents();
}

function bindWorkspaceEvents() {
  document.querySelectorAll('[data-view]').forEach((node) => node.addEventListener('click', (event) => {
    const view = event.currentTarget.dataset.view;
    if (view === 'document') return;
    state.view = view;
    renderWorkspace();
  }));
  document.querySelectorAll('[data-open-document]').forEach((node) => node.addEventListener('click', () => openDocument(node.dataset.openDocument)));
  document.querySelector('#logout')?.addEventListener('click', logout);
  document.querySelector('[data-action="guide"]')?.addEventListener('click', () => toast('Upload a PDF or DOCX, select a clause, then download your plain-language report.'));
  document.querySelector('[data-action="settings"]')?.addEventListener('click', () => toast('Your workspace is private by default. Account settings are available in a production deployment.'));
  document.querySelector('#file-input')?.addEventListener('change', (event) => uploadFile(event.target.files?.[0]));
  document.querySelector('#sample-analysis')?.addEventListener('click', makeDemoDocument);
  document.querySelector('#library-upload')?.addEventListener('click', () => {
    state.view = 'dashboard'; renderWorkspace(); window.setTimeout(() => document.querySelector('#file-input')?.click(), 100);
  });
  document.querySelector('#download-report')?.addEventListener('click', downloadReport);
  document.querySelectorAll('[data-clause]').forEach((node) => node.addEventListener('click', () => focusClause(node.dataset.clause)));
  enableDropZone();
}

function enableDropZone() {
  const zone = document.querySelector('#drop-zone');
  if (!zone) return;
  ['dragenter', 'dragover'].forEach((eventName) => zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach((eventName) => zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.remove('dragging'); }));
  zone.addEventListener('drop', (event) => uploadFile(event.dataTransfer.files?.[0]));
}

async function uploadFile(file) {
  if (!file) return;
  const panel = document.querySelector('#upload-panel');
  if (panel) panel.classList.add('uploading');
  if (panel) panel.querySelector('.drop-zone').innerHTML = `<span class="spinner"></span><span><strong>Reviewing ${escapeHtml(file.name)}…</strong><small>Checking file safety, extracting text and mapping key clauses</small></span>`;
  try {
    const form = new FormData(); form.append('document', file);
    const result = await api('/api/documents', { method: 'POST', body: form });
    state.dashboard.documents.unshift(result.document);
    state.dashboard.stats.documents += 1;
    state.dashboard.stats.high += result.document.analysis.counts.high;
    state.dashboard.stats.clauses += result.document.analysis.clauses.length;
    toast('Analysis complete. Your review is ready.');
    state.activeDocument = result.document;
    state.view = 'document';
    renderWorkspace();
  } catch (error) {
    toast(error.message, 'error');
    if (state.view === 'dashboard') renderWorkspace();
  }
}

async function makeDemoDocument() {
  const button = document.querySelector('#sample-analysis');
  setButtonLoading(button, true, 'Preparing sample...');
  try {
    const result = await api('/api/documents/demo', { method: 'POST', body: '{}' });
    state.dashboard.documents.unshift(result.document);
    state.dashboard.stats.documents += 1;
    state.dashboard.stats.high += result.document.analysis.counts.high;
    state.dashboard.stats.clauses += result.document.analysis.clauses.length;
    state.activeDocument = result.document;
    state.view = 'document';
    renderWorkspace();
  } catch (error) { toast(error.message, 'error'); setButtonLoading(button, false); }
}

async function openDocument(id) {
  renderLoadingDocument();
  try {
    const result = await api(`/api/documents/${id}`);
    state.activeDocument = result.document;
    state.view = 'document';
    renderWorkspace();
  } catch (error) { toast(error.message, 'error'); state.view = 'documents'; renderWorkspace(); }
}

function focusClause(id) {
  const target = document.querySelector(`[data-highlight="${id}"]`);
  document.querySelectorAll('.clause-card').forEach((card) => card.classList.toggle('active', card.dataset.clause === id));
  document.querySelectorAll('.text-highlight').forEach((mark) => mark.classList.toggle('selected', mark.dataset.highlight === id));
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  else toast('This is a missing-clause check, so there is no source text to highlight.', 'error');
}

async function downloadReport() {
  const button = document.querySelector('#download-report');
  if (!state.activeDocument) return;
  setButtonLoading(button, true, 'Preparing PDF...');
  try {
    const response = await api(`/api/documents/${state.activeDocument.id}/report`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `LegalEase-${state.activeDocument.filename.replace(/[^a-z0-9]/gi, '-').replace(/-+/g, '-')}-report.pdf`;
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    toast('Your LegalEase report is downloading.');
  } catch (error) { toast(error.message, 'error'); }
  setButtonLoading(button, false);
}

async function logout() {
  try { await api('/api/auth/logout', { method: 'POST', body: '{}' }); } catch (_) { /* local cleanup still applies */ }
  setToken(''); state.user = null; state.dashboard = null; state.activeDocument = null; state.authMode = 'login'; renderAuth();
}

async function bootstrap() {
  if (!state.token) return renderAuth();
  try { await loadDashboard(); } catch (_) { renderAuth(); }
}

bootstrap();
