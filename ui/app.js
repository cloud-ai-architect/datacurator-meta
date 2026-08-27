/**
 * DataCurator KB UI - rich client
 * - Search with filters
 * - Bulk feedback selection
 * - Live analytics
 * - Toast notifications
 */

(function () {
  'use strict';

  // --- Config (set by Terraform) ---
  const config = {
    apiUrl: window.DATACURATOR_API_URL || 'https://api.example.com',
    region: 'ap-south-1',
    environment: 'dev',
  };

  // Detect environment from URL
  if (window.location.hostname.includes('staging')) config.environment = 'staging';
  if (window.location.hostname.includes('prod')) config.environment = 'prod';
  document.getElementById('env-badge').textContent = config.environment;

  // --- State ---
  const state = {
    results: [],
    selected: new Set(),
    searchesToday: 0,
    feedbackSubmitted: 0,
    totalDuration: 0,
  };

  // --- DOM helpers ---
  const $ = (id) => document.getElementById(id);
  const showToast = (msg, type = 'success') => {
    const t = $('toast');
    t.textContent = msg;
    t.className = `toast show ${type}`;
    setTimeout(() => t.className = 'toast', 2500);
  };

  // --- AWS SigV4 signing ---
  // In production, use AWS SDK; here we assume a proxy or local dev
  async function signAndFetch(method, path, body) {
    const url = new URL(config.apiUrl + path);
    const headers = { 'Content-Type': 'application/json' };
    if (body) headers['Content-Type'] = 'application/json';
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const response = await fetch(url, opts);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'UNKNOWN', message: response.statusText }));
      throw new Error(`${err.error}: ${err.message}`);
    }
    return response.json();
  }

  // --- Search ---
  async function performSearch() {
    const q = $('search-input').value.trim();
    if (!q) {
      showToast('Enter a search query', 'error');
      return;
    }

    const topK = parseInt($('top-k').value, 10) || 10;
    const params = new URLSearchParams({ q, top_k: topK });
    const source = $('filter-source').value.trim();
    const format = $('filter-format').value;
    const minScore = parseFloat($('min-score').value);
    if (source) params.set('source', source);
    if (format) params.set('format', format);
    if (minScore > 0) params.set('min_score', minScore);

    $('search-btn').disabled = true;
    $('search-btn').textContent = 'Searching...';

    try {
      const data = await signAndFetch('GET', `/search?${params.toString()}`);
      state.results = data.results || [];
      state.searchesToday++;
      state.totalDuration += data.query_duration_ms || 0;
      renderResults(data);
      updateStats(data);
    } catch (err) {
      showToast(`Search failed: ${err.message}`, 'error');
    } finally {
      $('search-btn').disabled = false;
      $('search-btn').textContent = 'Search';
    }
  }

  function renderResults(data) {
    const container = $('results');
    if (data.results.length === 0) {
      container.innerHTML = `<div class="empty-state"><h2>No results</h2><p>Try a different query or relax filters.</p></div>`;
      return;
    }
    container.innerHTML = data.results.map((r) => `
      <article class="result-card" data-chunk-id="${r.chunk_id}">
        <div class="result-header">
          <div class="result-meta">
            <span class="score-pill">${r.score.toFixed(3)}</span>
            <span class="tag">${r.format}</span>
            ${r.category ? `<span class="tag">${r.category}</span>` : ''}
            ${(r.tags || []).slice(0, 3).map((t) => `<span class="tag">${t}</span>`).join('')}
          </div>
          <div>
            <button class="action-btn select-btn" data-chunk-id="${r.chunk_id}">Select</button>
          </div>
        </div>
        <div class="result-text">${escapeHtml(r.text_preview || '(no preview)')}</div>
        <div class="result-source">${escapeHtml(r.source_key || '')}</div>
        <div class="result-actions">
          <button class="action-btn good feedback-good" data-chunk-id="${r.chunk_id}">✓ Good</button>
          <button class="action-btn bad feedback-bad" data-chunk-id="${r.chunk_id}">✗ Misclassified</button>
          <button class="action-btn feedback-route" data-chunk-id="${r.chunk_id}">↻ Misrouted</button>
        </div>
      </article>
    `).join('');

    // Wire up event listeners
    container.querySelectorAll('.feedback-good').forEach((btn) => {
      btn.addEventListener('click', () => submitFeedback(btn.dataset.chunkId, 'good'));
    });
    container.querySelectorAll('.feedback-bad').forEach((btn) => {
      btn.addEventListener('click', () => submitFeedback(btn.dataset.chunkId, 'misclassified'));
    });
    container.querySelectorAll('.feedback-route').forEach((btn) => {
      btn.addEventListener('click', () => submitFeedback(btn.dataset.chunkId, 'misrouted'));
    });
    container.querySelectorAll('.select-btn').forEach((btn) => {
      btn.addEventListener('click', () => toggleSelect(btn.dataset.chunkId));
    });
  }

  function updateStats(data) {
    $('stat-results').textContent = `${data.total_results} results`;
    $('stat-duration').textContent = `${data.query_duration_ms}ms`;
    $('metric-searches').textContent = state.searchesToday;
    const avg = state.searchesToday > 0 ? Math.round(state.totalDuration / state.searchesToday) : 0;
    $('metric-avg-duration').textContent = `${avg}ms`;
    $('metric-feedback').textContent = state.feedbackSubmitted;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // --- Feedback ---
  async function submitFeedback(chunkId, label, suggestedClass) {
    try {
      await signAndFetch('POST', '/feedback', {
        chunk_id: chunkId,
        label,
        suggested_class: suggestedClass,
      });
      state.feedbackSubmitted++;
      updateStats({});
      showToast(`Feedback recorded: ${label}`);
    } catch (err) {
      showToast(`Feedback failed: ${err.message}`, 'error');
    }
  }

  // --- Bulk selection ---
  function toggleSelect(chunkId) {
    if (state.selected.has(chunkId)) {
      state.selected.delete(chunkId);
    } else {
      state.selected.add(chunkId);
    }
    updateSelectionUI();
  }

  function updateSelectionUI() {
    document.querySelectorAll('.result-card').forEach((card) => {
      const id = card.dataset.chunkId;
      if (state.selected.has(id)) {
        card.classList.add('selected');
        card.querySelector('.select-btn').classList.add('selected');
      } else {
        card.classList.remove('selected');
        card.querySelector('.select-btn').classList.remove('selected');
      }
    });
    $('bulk-good').disabled = state.selected.size === 0;
    $('bulk-misclass').disabled = state.selected.size === 0;
  }

  $('select-all')?.addEventListener('click', () => {
    if (state.selected.size === state.results.length) {
      state.selected.clear();
    } else {
      state.results.forEach((r) => state.selected.add(r.chunk_id));
    }
    updateSelectionUI();
  });

  $('bulk-good')?.addEventListener('click', async () => {
    for (const id of state.selected) {
      await submitFeedback(id, 'good');
    }
    state.selected.clear();
    updateSelectionUI();
  });

  $('bulk-misclass')?.addEventListener('click', async () => {
    for (const id of state.selected) {
      await submitFeedback(id, 'misclassified');
    }
    state.selected.clear();
    updateSelectionUI();
  });

  // --- Wire up ---

  $('search-btn').addEventListener('click', performSearch);
  $('search-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  $('min-score').addEventListener('input', (e) => {
    $('min-score-value').textContent = parseFloat(e.target.value).toFixed(2);
  });

  $('reset-filters').addEventListener('click', () => {
    $('filter-source').value = '';
    $('filter-format').value = '';
    $('min-score').value = '0';
    $('min-score-value').textContent = '0.00';
  });

  $('refresh-metrics')?.addEventListener('click', updateStats);
})();
