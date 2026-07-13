/* ===========================
   AccessAI — app.js (updated)
   7 tabs, passed checks, multi-screenshot, scan quality warning
   =========================== */
(function () {
  'use strict';

  let currentScanId = null;
  let currentResults = null;

  async function init() {
    bindEvents();
    checkOllamaStatus();
    loadHistory();
    setInterval(checkOllamaStatus, 30000);
  }

  async function checkOllamaStatus() {
    const dot = document.getElementById('ollamaStatus');
    const alive = await Api.checkHealth();
    dot.className = 'status-dot ' + (alive ? 'online' : 'offline');
    dot.title = alive ? 'Ollama: online' : 'Ollama: offline — run: ollama serve';
  }

  async function loadHistory() {
    const { scans } = await Api.getScanHistory();
    UI.renderHistory(scans);
  }

  function bindEvents() {
    document.getElementById('startScanBtn').addEventListener('click', startScan);
    document.getElementById('urlInput').addEventListener('keydown', e => { if(e.key==='Enter') startScan(); });

    document.getElementById('downloadReportBtn').addEventListener('click', () => {
      if(currentScanId) Api.downloadReport(currentScanId, 'html');
    });

    document.getElementById('downloadVpatBtn').addEventListener('click', async () => {
      if(!currentScanId) return;
      try {
        UI.toast('Generating VPAT/ACR report...', 'info');
        await Api.downloadComplianceReport(currentScanId, 'vpat', 'html');
        UI.toast('VPAT/ACR report downloaded!', 'success');
      } catch(e) {
        console.warn('VPAT/ACR download failed:', e);
        UI.toast(`VPAT/ACR download failed: ${e.message}`, 'error');
      }
    });

    document.getElementById('themeToggle').addEventListener('click', () => {
      const isDark = document.body.dataset.theme === 'dark';
      document.body.dataset.theme = isDark ? 'light' : 'dark';
      document.body.className = isDark ? 'light-theme' : 'dark-theme';
      document.getElementById('themeToggle').textContent = isDark ? '☾' : '☀';
    });

    // Tabs
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Modals
    document.getElementById('modalClose').addEventListener('click', UI.hideModal.bind(UI));
    document.getElementById('violationModal').addEventListener('click', e => { if(e.target===e.currentTarget) UI.hideModal(); });

    // Passed card click → switch to passed-checks tab
    document.getElementById('metricPassedCard').addEventListener('click', () => {
      switchTab('passed-checks');
    });

    // Violation detail buttons
    document.getElementById('violationsTableBody').addEventListener('click', e => {
      const btn = e.target.closest('.btn-detail');
      if(!btn) return;
      const idx = parseInt(btn.dataset.index);
      const violation = Scanner.violations[idx];
      const aiData = Scanner.getAiForViolation(idx);
      if(violation) UI.showViolationModal(violation, aiData);
    });

    // Search
    document.getElementById('violationSearch').addEventListener('input', e => {
      UI.renderViolationsTable(Scanner.getFiltered(e.target.value));
    });

    // Severity filters
    document.querySelectorAll('#severityFilters .filter-chip').forEach(chip => {
      chip.addEventListener('click', e => {
        e.preventDefault();
        const input = chip.querySelector('input');
        if (input) input.checked = !input.checked;
        Scanner.setSeverity(chip.dataset.filter, input ? input.checked : !chip.classList.contains('active'));
        chip.classList.toggle('active', input ? input.checked : Scanner.activeSeverities.has(chip.dataset.filter));
        applySeverityFilters();
      });
    });

    // History
    document.getElementById('scanHistory').addEventListener('click', async e => {
      const item = e.target.closest('.history-item');
      if(!item) return;
      try {
        const results = await Api.getScanResults(item.dataset.scanId);
        currentScanId = item.dataset.scanId;
        displayResults(results);
      } catch { UI.toast('Could not load historical scan', 'error'); }
    });
  }

  async function startScan() {
    const url = document.getElementById('urlInput').value.trim();
    if(!url) { UI.toast('Please enter a URL', 'error'); return; }
    if(!url.startsWith('http')) { UI.toast('URL must start with http:// or https://', 'error'); return; }

    const model    = document.getElementById('modelSelect').value;
    const depth    = document.getElementById('scanDepth').value;
    const wcagLevel = document.getElementById('wcagLevel').value;
    const runGuidelines = document.getElementById('runGuidelines').checked;
    const runScenarios  = document.getElementById('runScenarios').checked;

    const btn = document.getElementById('startScanBtn');
    btn.disabled = true; btn.textContent = 'Scanning...';
    document.getElementById('downloadReportBtn').style.display='none';
    document.getElementById('downloadVpatBtn').style.display='none';

    UI.showProgress();

    try {
      const { scan_id } = await Api.startScan({ url, model, depth, wcagLevel });
      currentScanId = scan_id;

      const results = await Api.pollScan(scan_id, status => UI.updateProgress(status));
      displayResults(results);

      // Run guideline validation in parallel (non-blocking)
      if(runGuidelines) {
        UI.renderRuleEvidence([], true);
        runGuidelineValidation(url, scan_id).then(data => {
          if(data) {
            if(currentResults) currentResults.rule_results = data;
            applySeverityFilters();
            // Also update the Rule Evidence tab badge
          }
        });
      }

      // Generate AI scenarios if requested
      if(runScenarios) {
        UI.renderScenarios([], true);
        generateScenarios(scan_id, model).then(data => {
          if(data) {
            if(currentResults) currentResults.generated_scenarios = data.scenarios;
            applySeverityFilters();
          }
        });
      }

      loadHistory();
      UI.toast('Scan complete!', 'success');

    } catch(err) {
      UI.showWelcome();
      UI.toast(`Scan failed: ${err.message}`, 'error');
    } finally {
      btn.disabled=false; btn.innerHTML='<span class="btn-icon-left">▶</span> Start AI Accessibility Scan';
    }
  }

  async function runGuidelineValidation(url, scanId) {
    try {
      const r = await fetch('http://localhost:8000/api/guidelines/run', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ url, scan_id: scanId, enabled_rules: null })
      });
      return r.ok ? r.json() : null;
    } catch(e) { console.warn('Guideline validation failed:', e); return null; }
  }

  async function generateScenarios(scanId, model) {
    try {
      const r = await fetch('http://localhost:8000/api/scenarios/generate', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ scan_id: scanId, model, categories: ['keyboard','screen_reader','low_vision','color_blind','edge_cases'] })
      });
      return r.ok ? r.json() : null;
    } catch(e) { console.warn('Scenario generation failed:', e); return null; }
  }

  function displayResults(results) {
    currentResults = results;
    const violations  = results.violations || [];
    const aiAnalyses  = results.ai_analyses || [];
    const passedChecks = results.passed_checks || [];

    Scanner.setData(violations, aiAnalyses);
    Scanner.resetFilters();
    document.querySelectorAll('#severityFilters .filter-chip').forEach(chip => {
      const input = chip.querySelector('input');
      if (input) input.checked = true;
      chip.classList.add('active');
    });

    UI.showResults();
    UI.renderScore(results.score, results.metrics);
    UI.renderMetrics(results.metrics);
    UI.renderViolationsTable(Scanner.getFiltered());
    UI.renderAiAnalysis(aiAnalyses);
    UI.renderExecutiveSummary(results.executive_summary);
    UI.showScanQualityWarning(results.url, results.score, violations, results.metrics);

    // Passed checks tab
    UI.renderPassedChecks(passedChecks);
    UI.renderRuleEvidence(results.rule_results?.results || []);
    UI.renderScenarios(results.generated_scenarios || []);

    // Screenshots
    buildScreenshots(results);

    document.getElementById('downloadReportBtn').style.display='';
    document.getElementById('downloadVpatBtn').style.display='';
    switchTab('violations');
  }

  function buildScreenshots(results) {
    const screenshots = [];
    if(currentScanId) {
      screenshots.push({
        src: `http://localhost:8000/api/scan/${currentScanId}/screenshot`,
        url: results.url,
        label: 'Initial page load',
        captured_at: results.created_at ? new Date(results.created_at).toLocaleTimeString() : '',
      });
    }
    (results.extra_screenshots || []).forEach((shot, index) => {
      screenshots.push({
        src: `http://localhost:8000/api/scan/${currentScanId}/screenshot/${index + 2}`,
        url: shot.url || results.url,
        label: `Crawled page ${index + 2}`,
        captured_at: shot.captured_at || '',
      });
    });
    UI.renderScreenshots(screenshots);
  }

  function applySeverityFilters() {
    const active = Scanner.activeSeverities;
    UI.renderViolationsTable(Scanner.getFiltered(document.getElementById('violationSearch').value));
    if (currentResults?.rule_results?.results) {
      UI.renderRuleEvidence(currentResults.rule_results.results.filter(r => active.has(r.severity || 'low')));
    }
    if (currentResults?.generated_scenarios) {
      UI.renderScenarios(currentResults.generated_scenarios.filter(s => active.has(s.severity || 'low')));
    }
    if (currentResults?.ai_analyses) {
      UI.renderAiAnalysis(currentResults.ai_analyses.filter(a => active.has(a.severity || 'low')));
    }
  }

  function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab===tabId));
    document.querySelectorAll('.tab-panel').forEach(p => { p.style.display = p.id===`tab-${tabId}` ? '' : 'none'; });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
