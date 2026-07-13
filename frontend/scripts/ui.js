/* ===========================
   AccessAI — ui.js  (updated)
   =========================== */
const UI = {

  toast(msg, type='info', duration=3500) {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${{success:'✓',error:'✕',info:'ℹ'}[type]}</span><span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transition='opacity .3s'; setTimeout(()=>t.remove(),300); }, duration);
  },

  showWelcome()  { document.getElementById('welcomeState').style.display=''; document.getElementById('scanProgressState').style.display='none'; document.getElementById('resultsState').style.display='none'; },
  showProgress() { document.getElementById('welcomeState').style.display='none'; document.getElementById('scanProgressState').style.display=''; document.getElementById('resultsState').style.display='none'; this.resetProgressSteps(); },
  showResults()  { document.getElementById('welcomeState').style.display='none'; document.getElementById('scanProgressState').style.display='none'; document.getElementById('resultsState').style.display=''; },

  STEPS: ['browser','navigate','axe','scan','ai','report'],
  resetProgressSteps() {
    this.STEPS.forEach(s => { const el=document.getElementById(`step-${s}`); if(el) el.classList.remove('active','done'); });
    document.getElementById('progressBar').style.width='0%';
    document.getElementById('progressTitle').textContent='Initializing scan...';
  },
  updateProgress(status) {
    const map = { browser:{step:0,label:'Launching browser...'},navigate:{step:1,label:'Navigating to URL...'},axe_inject:{step:2,label:'Injecting axe-core...'},scanning:{step:3,label:'Running accessibility scan...'},ai_analysis:{step:4,label:'AI analyzing violations...'},reporting:{step:5,label:'Generating report...'},completed:{step:6,label:'Scan complete!'} };
    const cur = map[status.step] || {step:0,label:status.message||'Processing...'};
    document.getElementById('progressBar').style.width = Math.round((cur.step/6)*100)+'%';
    document.getElementById('progressTitle').textContent = cur.label;
    this.STEPS.forEach((s,i) => { const el=document.getElementById(`step-${s}`); if(!el) return; el.classList.remove('active','done'); if(i<cur.step) el.classList.add('done'); else if(i===cur.step) el.classList.add('active'); });
  },

  renderScore(score, metrics={}) {
    const ring=document.getElementById('scoreRing'), num=document.getElementById('scoreNumber'), grade=document.getElementById('scoreGrade');
    ring.style.strokeDashoffset = 264 - (score/100)*264;
    let g,cls;
    if(score>=90){g='A';cls='grade-a';}else if(score>=75){g='B';cls='grade-b';}else if(score>=60){g='C';cls='grade-c';}else if(score>=40){g='D';cls='grade-d';}else{g='F';cls='grade-f';}
    ring.className=`score-ring ${cls}`; num.textContent=score; grade.textContent=g; grade.className=`score-grade text-${cls.replace('grade-','')}`;
    const formula = document.getElementById('scoreFormula');
    if (formula) {
      const penalty = (metrics.critical||0)*10 + (metrics.high||0)*5 + (metrics.medium||0)*2 + (metrics.low||0);
      formula.textContent = `${metrics.passed||0} axe passes / (${metrics.passed||0} passes + ${penalty} weighted issue points)`;
    }
  },

  renderMetrics({critical=0,high=0,medium=0,low=0,passed=0}) {
    document.getElementById('metricCritical').textContent=critical;
    document.getElementById('metricHigh').textContent=high;
    document.getElementById('metricMedium').textContent=medium;
    document.getElementById('metricLow').textContent=low;
    document.getElementById('metricPassed').textContent=passed;
  },

  showScanQualityWarning(url, score, violations, metrics={}) {
    const el = document.getElementById('scanQualityNotice');
    const txt = document.getElementById('scanQualityText');
    const quality = metrics?.quality || {};
    const warnings = Array.isArray(quality.warnings) ? quality.warnings : [];
    const counts = quality.element_counts || {};
    const passed = metrics.passed || quality.pass_rule_count || 0;
    const links = counts.links || 0;
    const inputs = counts.inputs || 0;
    const images = counts.images || 0;
    const headings = counts.headings || 0;
    const isLowSignal = passed < 40 && violations.length === 0;
    const isBlocked = quality.likely_blocked || quality.suspicious;
    const shouldWarn = isBlocked || (score >= 95 && violations.length === 0);

    if (shouldWarn) {
      // Determine the likely reason
      let reason = '';
      let actionItems = [];

      if (passed < 15) {
        reason = `<strong>⚠ Very low page content detected (${passed} axe checks, ${links} links, ${inputs} inputs, ${images} images).</strong> 
          Primark and similar large retail sites use bot-detection that serves a minimal page to automated browsers.
          The scanner saw only a partial page — not the full interactive site.`;
        actionItems = [
          'Try scanning a <strong>product category page</strong> like <code>https://www.primark.com/en-gb/c/womens</code> instead',
          'Try scanning <strong>3 or 5 pages</strong> (scan depth) — deeper crawls sometimes bypass initial bot checks',
          'Check the <strong>Screenshots tab</strong> to see what the scanner actually saw',
          'The <strong>Rule Evidence tab</strong> runs a second browser scan that may get further into the page',
          'For Primark specifically: use <a href="https://wave.webaim.org/report#/https://www.primark.com/en-gb" target="_blank" style="color:var(--accent)">WAVE WebAIM ↗</a> or <a href="https://www.accessibilitychecker.org" target="_blank" style="color:var(--accent)">AccessibilityChecker ↗</a> as a cross-check',
        ];
      } else if (violations.length === 0 && passed < 80) {
        reason = `<strong>Zero violations found with ${passed} axe checks.</strong> 
          This is a low check count for a large retail site. The page may have loaded but without full dynamic content.`;
        actionItems = [
          'Check the <strong>Screenshots tab</strong> to confirm the full page was rendered',
          'Use the <strong>Rule Evidence tab</strong> for 24 additional manual-style checks',
          'Automated tools detect ~30-40% of WCAG issues — always supplement with manual testing',
        ];
      } else {
        reason = `<strong>Zero axe violations found.</strong> The site rendered with ${passed} passed axe checks, ${links} links, and ${images} images detected.`;
        actionItems = [
          'Review the <strong>Rule Evidence tab</strong> for issues axe-core does not cover',
          'Check the <strong>Screenshots tab</strong> to confirm full page render',
          'axe-core covers ~30-40% of WCAG 2.1 — manual testing is always required for compliance',
        ];
      }

      const warningList = warnings.length
        ? `<ul style="margin:6px 0 0 16px;padding:0;font-size:12px;color:var(--text-muted)">${warnings.map(w => `<li style="margin-bottom:3px">${this.esc(w)}</li>`).join('')}</ul>`
        : '';

      const actionList = `<ul style="margin:8px 0 0 16px;padding:0">${actionItems.map(a => `<li style="margin-bottom:4px;font-size:13px">${a}</li>`).join('')}</ul>`;

      const evidence = `<div style="margin-top:10px;background:var(--bg-elevated);border-radius:6px;padding:8px 12px;font-size:12px;color:var(--text-muted)">
        <strong style="color:var(--text-secondary)">Scan evidence:</strong>
        ${quality.pages_scanned || 1} page(s) scanned &nbsp;·&nbsp;
        ${passed} axe rules passed &nbsp;·&nbsp;
        ${links} links &nbsp;·&nbsp;
        ${inputs} inputs &nbsp;·&nbsp;
        ${images} images &nbsp;·&nbsp;
        ${headings} headings &nbsp;·&nbsp;
        body text: ${counts.body_text_length || 0} chars
      </div>`;

      txt.innerHTML = `${reason}${warningList}
        <div style="margin-top:8px"><strong>What to do:</strong>${actionList}</div>
        ${evidence}`;
      el.style.display='flex';
    } else {
      el.style.display='none';
    }
  },

  renderViolationsTable(violations) {
    const tbody=document.getElementById('violationsTableBody'), count=document.getElementById('resultCount');
    count.textContent=`${violations.length} issue${violations.length!==1?'s':''}`;
    if(!violations.length) { tbody.innerHTML=`<tr><td colspan="5"><div class="empty-state"><div class="empty-state-icon">✓</div>No violations found!</div></td></tr>`; return; }
    tbody.innerHTML=violations.map((v,i)=>`
      <tr data-severity="${v.severity}" data-index="${v._sourceIndex ?? i}">
        <td><span class="badge badge-${v.severity}">${v.severity}</span></td>
        <td><div class="violation-title">${this.esc(v.description)}</div><div class="violation-desc">${this.esc(v.help||'')}</div></td>
        <td><span class="wcag-tag">${this.esc(v.wcag_reference||v.tags?.[0]||'—')}</span></td>
        <td>${v.nodes?.length||1} element${(v.nodes?.length||1)!==1?'s':''}</td>
        <td><button class="btn-detail" data-index="${v._sourceIndex ?? i}">Details</button></td>
      </tr>`).join('');
  },

  /* ── RULE EVIDENCE (new) ───────────────────────────── */
  renderRuleEvidence(results, loading=false) {
    const el = document.getElementById('ruleEvidenceContent');
    if (loading) {
      el.innerHTML='<div class="ai-loading"><div class="ai-loading-dot"></div><div class="ai-loading-dot"></div><div class="ai-loading-dot"></div><span style="margin-left:8px">Running 24 guideline rules…</span></div>'; return;
    }
    if (!results || !results.length) {
      el.innerHTML='<div class="empty-state"><div class="empty-state-icon">⚙</div>No guideline results available.</div>'; return;
    }
    const passed=results.filter(r=>r.status==='pass').length, failed=results.filter(r=>r.status==='fail').length;
    const customScore = results.length ? Math.round((passed / results.length) * 1000) / 10 : 0;
    const summary=`<div style="display:flex;gap:14px;margin-bottom:14px;font-size:13px">
      <span style="color:var(--low)">✓ ${passed} rules passed</span>
      <span style="color:var(--critical)">✕ ${failed} rules failed</span>
      <span style="color:var(--text-muted)">${results.length} total rules checked</span>
      <span style="color:var(--text-muted)">Custom rule score: ${customScore}%</span>
    </div>`;
    const rows=results.map(r=>{
      const evidenceText = r.evidence && r.evidence.length
        ? r.evidence.slice(0,3).map(e=>typeof e === 'string' ? this.esc(e) : `${this.esc(e.selector||'')}: ${this.esc(e.message||'')}`).join(' | ')
        : r.status==='pass' ? (r.description||'All checks passed') : '—';
      const wcagValues = Array.isArray(r.wcag) ? r.wcag.map(w=>`WCAG 2.1 SC ${w}`) : String(r.wcag_ref||r.wcag||'').split(',');
      const wcagLinks = wcagValues.map(w=>String(w).trim()).filter(Boolean).map(w=>{
        const id=w.match(/(\d+\.\d+\.\d+)/)?.[1];
        return id ? `<a href="https://www.w3.org/WAI/WCAG21/Understanding/${this._wcagSlug(id)}" target="_blank" class="wcag-link">${w}</a>` : this.esc(w);
      }).join(', ');
      const ruleName = r.rule_name || r.name || r.rule_id;
      return `<tr>
        <td><span class="status-${r.status}">${r.status.toUpperCase()}</span>${r.status==='fail'?`<br><span style="font-size:10px;color:var(--text-muted)">${(r.evidence||[]).length} item(s)</span>`:''}</td>
        <td><div class="rule-name">${this.esc(ruleName)}</div><div class="rule-cat">${this.esc(r.category||'')} - ${this.esc(r.message||'').slice(0,90)}</div></td>
        <td><div class="passed-wcag">${wcagLinks||'—'}</div></td>
        <td><div class="evidence-text">${evidenceText.slice(0,220)}</div></td>
      </tr>`;
    }).join('');
    el.innerHTML=summary+`<div class="violations-table-wrapper"><table class="rule-evidence-table">
      <thead><tr><th>Status</th><th>Rule</th><th>WCAG</th><th>Evidence</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  },

  /* ── PASSED CHECKS (new) ────────────────────────────── */
  renderPassedChecks(passedData) {
    const el = document.getElementById('passedChecksContent');
    if (!passedData || !passedData.length) {
      el.innerHTML='<div class="empty-state"><div class="empty-state-icon">✓</div>No passed check data available.</div>'; return;
    }
    // Complete axe-core rule → WCAG 2.1 mapping
    const WCAG_MAP = {
      // Perceivable (1.x)
      'image-alt':'1.1.1','input-image-alt':'1.1.1','object-alt':'1.1.1',
      'image-redundant-alt':'1.1.1','svg-img-alt':'1.1.1',
      'audio-caption':'1.2.1','video-caption':'1.2.2','video-description':'1.2.3',
      'color-contrast':'1.4.3','color-contrast-enhanced':'1.4.6',
      'meta-refresh':'2.2.1','blink':'2.2.2','marquee':'2.2.2',
      'label':'1.3.1','label-content-name-mismatch':'2.5.3',
      'definition-list':'1.3.1','dlitem':'1.3.1','list':'1.3.1','listitem':'1.3.1',
      'table-duplicate-name':'1.3.1','table-fake-caption':'1.3.1',
      'td-headers-attr':'1.3.1','th-has-data-cells':'1.3.1',
      'heading-order':'1.3.1','empty-heading':'1.3.1',
      'identical-links-same-purpose':'1.3.1',
      'landmark-banner-is-top-level':'1.3.1',
      'landmark-complementary-is-top-level':'1.3.1',
      'landmark-contentinfo-is-top-level':'1.3.1',
      'landmark-main-is-top-level':'1.3.1',
      'landmark-no-duplicate-banner':'1.3.1',
      'landmark-no-duplicate-contentinfo':'1.3.1',
      'landmark-no-duplicate-main':'1.3.1',
      'landmark-one-main':'1.3.1',
      'landmark-unique':'1.3.1',
      'css-orientation-lock':'1.3.4',
      'autocomplete-valid':'1.3.5',
      'link-in-text-block':'1.4.1',
      'meta-viewport-large':'1.4.4',
      'meta-viewport':'1.4.4',
      'text-spacing':'1.4.12',
      // Operable (2.x)
      'accesskeys':'2.1.4',
      'bypass':'2.4.1','skip-link':'2.4.1',
      'document-title':'2.4.2',
      'focus-order-semantics':'2.4.3','tabindex':'2.4.3',
      'link-name':'2.4.4','duplicate-link':'2.4.4',
      'page-has-heading-one':'2.4.6',
      'scrollable-region-focusable':'2.1.1',
      'frame-focusable-content':'2.1.1',
      // Robust (4.x)
      'duplicate-id':'4.1.1','duplicate-id-active':'4.1.1','duplicate-id-aria':'4.1.1',
      'aria-allowed-attr':'4.1.2','aria-conditional-attr':'4.1.2',
      'aria-deprecated-role':'4.1.2','aria-hidden-body':'4.1.2',
      'aria-hidden-focus':'4.1.2','aria-prohibited-attr':'4.1.2',
      'aria-required-attr':'4.1.2','aria-required-children':'4.1.2',
      'aria-required-parent':'4.1.2','aria-roledescription':'4.1.2',
      'aria-roles':'4.1.2','aria-tooltip-name':'4.1.2',
      'aria-valid-attr':'4.1.2','aria-valid-attr-value':'4.1.2',
      'button-name':'4.1.2','combobox-name':'4.1.2',
      'frame-title':'4.1.2','frame-title-unique':'4.1.2',
      'input-button-name':'4.1.2','input-image-alt':'4.1.2',
      'role-img-alt':'4.1.2','select-name':'4.1.2',
      'server-side-image-map':'4.1.2',
      'aria-live-region-clipping':'4.1.3',
      // Understandable (3.x)
      'html-has-lang':'3.1.1','html-lang-valid':'3.1.1',
      'html-xml-lang-mismatch':'3.1.1','valid-lang':'3.1.2',
    };
    const rows = passedData.map(p => {
      const ruleId = p.id || p.rule_id || '';
      const wcagId = WCAG_MAP[ruleId] || '';
      const wcagLink = wcagId
        ? `<a href="https://www.w3.org/WAI/WCAG21/Understanding/${this._wcagSlug(wcagId)}" target="_blank" class="wcag-link">WCAG ${wcagId} ↗</a>`
        : '—';
      // nodes is stored as a count integer from axe_scanner
      const nodeCount = typeof p.nodes === 'number' ? p.nodes : (p.nodes?.length || p.element_count || 0);
      return `<tr>
        <td><span class="pass-badge">PASS</span></td>
        <td><div class="passed-rule-id">${this.esc(ruleId)}</div></td>
        <td><div class="passed-rule-help">${this.esc(p.description||p.help||'')}</div></td>
        <td>${wcagLink}</td>
        <td style="color:var(--low);font-weight:600">${nodeCount>0?nodeCount+' element'+(nodeCount!==1?'s':''):'—'}</td>
      </tr>`;
    }).join('');
    el.innerHTML=`<div class="violations-table-wrapper"><table class="passed-table">
      <thead><tr><th>Status</th><th>Rule ID</th><th>What was checked</th><th>WCAG Criterion</th><th>Elements checked</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  },

  /* ── SCENARIOS (new) ───────────────────────────────── */
  renderScenarios(scenarios, loading=false) {
    const el = document.getElementById('scenariosContent');
    if (loading) {
      el.innerHTML='<div class="ai-loading"><div class="ai-loading-dot"></div><div class="ai-loading-dot"></div><div class="ai-loading-dot"></div><span style="margin-left:8px">AI generating test scenarios for 7 user groups…</span></div>'; return;
    }
    if (!scenarios || !scenarios.length) {
      el.innerHTML='<div class="empty-state"><div class="empty-state-icon">🤖</div>No scenarios generated.</div>'; return;
    }
    const auto=scenarios.filter(s=>s.automation_feasibility==='automated').length;
    const partial=scenarios.filter(s=>s.automation_feasibility==='semi-automated').length;
    const manual=scenarios.filter(s=>s.automation_feasibility==='manual').length;
    const summary=`<div style="display:flex;gap:14px;margin-bottom:14px;font-size:13px;flex-wrap:wrap">
      <span style="color:var(--low)">✓ ${auto} automatable</span>
      <span style="color:var(--medium)">${partial} semi-automated</span>
      <span style="color:var(--high)">${manual} manual only</span>
      <span style="color:var(--text-muted)">${scenarios.length} total scenarios</span>
    </div>`;
    const rows=scenarios.map(s=>{
      const autoClass={'automated':'auto-yes','semi-automated':'auto-partial','manual':'auto-manual'}[s.automation_feasibility]||'auto-manual';
      const autoLabel={'automated':'automatable','semi-automated':'semi-automated','manual':'manual'}[s.automation_feasibility]||s.automation_feasibility;
      const catSlug = (s.category||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
      return `<tr>
        <td><div class="test-id">${this.esc(s.test_case_id||'')}</div></td>
        <td><span class="cat-badge">${this.esc(catSlug)}</span></td>
        <td>
          <div class="scenario-title">${this.esc(s.category||'Accessibility scenario')}
            ${s.edge_case?'<span class="edge-flag">EDGE</span>':''}
            ${s.negative_test?'<span class="neg-flag">NEG</span>':''}
          </div>
          <div class="scenario-desc">${this.esc(s.scenario_description||'')}</div>
        </td>
        <td><div class="passed-wcag">${this.esc(Array.isArray(s.wcag_mapping) ? s.wcag_mapping.join(', ') : (s.wcag_mapping||''))}</div></td>
        <td><span class="badge badge-${s.severity||'low'}">${s.severity||'—'}</span></td>
        <td><span class="auto-badge ${autoClass}">${autoLabel}</span></td>
      </tr>`;
    }).join('');
    el.innerHTML=summary+`<div class="violations-table-wrapper"><table class="scenarios-table">
      <thead><tr><th>ID</th><th>Category</th><th>Scenario</th><th>WCAG</th><th>Severity</th><th>Automation</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  },

  /* ── SCREENSHOTS (multiple) ─────────────────────────── */
  renderScreenshots(screenshots) {
    const grid = document.getElementById('screenshotsGrid');
    const placeholder = document.getElementById('screenshotPlaceholder');
    if (!screenshots || !screenshots.length) {
      if(placeholder) placeholder.style.display='';
      return;
    }
    if(placeholder) placeholder.style.display='none';
    grid.innerHTML = screenshots.map((s,i) => `
      <div class="screenshot-card">
        <div class="screenshot-card-header">
          <span class="screenshot-card-url">📸 ${s.label||'Page '+(i+1)} — ${this.esc(s.url||'')}</span>
          <span class="screenshot-card-time">${s.captured_at||''}</span>
        </div>
        <img src="${s.src}" alt="Screenshot of ${this.esc(s.url||'page')}" loading="lazy" />
      </div>`).join('');
  },

  renderAiAnalysis(analyses) {
    const list=document.getElementById('aiAnalysisList');
    if(!analyses?.length){list.innerHTML=`<div class="empty-state"><div class="empty-state-icon">🤖</div>No AI analysis available — no violations to analyze.</div>`;return;}
    list.innerHTML=analyses.map(a=>`
      <div class="ai-card">
        <div class="ai-card-header">
          <div>
            <div class="ai-card-title">${this.esc(a.issue_title||a.description)}</div>
            <div class="impact-row">
              <span class="badge badge-${a.severity}">${a.severity}</span>
              <span class="wcag-tag">${this.esc(a.wcag_reference||'')}</span>
              <span class="priority-badge priority-p${a.priority==='P1'?'1':a.priority==='P2'?'2':'3'}">${a.priority}</span>
            </div>
          </div>
        </div>
        <div class="ai-card-body">
          <div class="ai-section"><div class="ai-section-label">Business impact</div><div class="ai-section-content">${this.esc(a.business_impact||'—')}</div></div>
          <div class="ai-section"><div class="ai-section-label">Affected users</div><div class="ai-section-content">${this.esc(a.affected_users||'—')}</div></div>
          <div class="ai-section"><div class="ai-section-label">Technical explanation</div><div class="ai-section-content">${this.esc(a.technical_explanation||'—')}</div></div>
          <div class="ai-section"><div class="ai-section-label">Recommended fix</div><div class="ai-section-content">${this.esc(a.recommended_fix||'—')}</div></div>
          ${a.sample_code_fix?`<div class="ai-section"><div class="ai-section-label">Code fix example</div><div class="ai-code-fix">${this.esc(a.sample_code_fix)}</div></div>`:''}
        </div>
      </div>`).join('');
  },

  renderExecutiveSummary(data) {
    const el=document.getElementById('executiveSummary');
    if(!data){el.innerHTML='<div class="empty-state">No summary generated.</div>';return;}
    el.innerHTML=`
      <div class="exec-section"><div class="exec-title">Overview</div><div class="exec-body">${this.esc(data.overview||'')}</div></div>
      <div class="exec-section"><div class="exec-title">Key Findings</div><div class="exec-body">${this.esc(data.key_findings||'')}</div></div>
      <div class="exec-section"><div class="exec-title">Top Recommendations</div>
        <ul class="exec-recommendations">
          ${(data.recommendations||[]).map((r,i)=>`<li class="exec-rec-item"><div class="exec-rec-num">${i+1}</div><div>${this.esc(r)}</div></li>`).join('')}
        </ul>
      </div>
      ${data.compliance_status?`<div class="exec-section"><div class="exec-title">Compliance Status</div><div class="exec-body">${this.esc(data.compliance_status)}</div></div>`:''}`;
  },

  showViolationModal(violation, aiData) {
    document.getElementById('modalTitle').textContent=violation.description;
    const body=document.getElementById('modalBody');
    body.innerHTML=`
      <div class="modal-section"><div class="modal-section-label">Severity</div><div class="modal-section-content"><span class="badge badge-${violation.severity}">${violation.severity}</span></div></div>
      <div class="modal-section"><div class="modal-section-label">WCAG Reference</div><div class="modal-section-content"><span class="wcag-tag">${this.esc(violation.wcag_reference||'—')}</span></div></div>
      <div class="modal-section"><div class="modal-section-label">Description</div><div class="modal-section-content">${this.esc(violation.help||violation.description)}</div></div>
      ${violation.helpUrl?`<div class="modal-section"><div class="modal-section-label">More info</div><div class="modal-section-content"><a href="${violation.helpUrl}" target="_blank" style="color:var(--accent)">${violation.helpUrl}</a></div></div>`:''}
      ${violation.nodes?.[0]?.html?`<div class="modal-section"><div class="modal-section-label">Failing HTML</div><div class="code-block">${this.esc(violation.nodes[0].html)}</div></div>`:''}
      ${aiData?`<hr class="divider">
        <div class="modal-section"><div class="modal-section-label">AI: Business impact</div><div class="modal-section-content">${this.esc(aiData.business_impact||'')}</div></div>
        <div class="modal-section"><div class="modal-section-label">AI: Recommended fix</div><div class="modal-section-content">${this.esc(aiData.recommended_fix||'')}</div></div>
        ${aiData.sample_code_fix?`<div class="modal-section"><div class="modal-section-label">AI: Code fix</div><div class="code-block">${this.esc(aiData.sample_code_fix)}</div></div>`:''}`:''}`;
    document.getElementById('violationModal').style.display='flex';
  },
  hideModal() { document.getElementById('violationModal').style.display='none'; },

  renderHistory(scans) {
    const el=document.getElementById('scanHistory');
    if(!scans?.length){el.innerHTML='<div class="history-empty">No previous scans</div>';return;}
    el.innerHTML=scans.slice(0,10).map(s=>`
      <div class="history-item" data-scan-id="${s.id}">
        <div class="history-url">${this.esc(s.url)}</div>
        <div style="display:flex;justify-content:space-between;margin-top:3px">
          <span style="font-size:11px;color:var(--text-muted)">${new Date(s.created_at).toLocaleDateString()}</span>
          <span class="history-score">${s.score}/100</span>
        </div>
      </div>`).join('');
  },

  esc(str) {
    if(!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },

  _wcagSlug(id) {
    const slugs = {'1.1.1':'non-text-content','1.3.1':'info-and-relationships','1.4.3':'contrast-minimum','1.4.4':'resize-text','1.4.10':'reflow','2.1.1':'keyboard','2.1.2':'no-keyboard-trap','2.4.1':'bypass-blocks','2.4.2':'page-titled','2.4.3':'focus-order','2.4.4':'link-purpose-in-context','2.4.6':'headings-and-labels','2.4.7':'focus-visible','3.1.1':'language-of-page','3.3.1':'error-identification','3.3.2':'labels-or-instructions','4.1.1':'parsing','4.1.2':'name-role-value','4.1.3':'status-messages'};
    return slugs[id] || id.replace(/\./g,'-');
  }
};
