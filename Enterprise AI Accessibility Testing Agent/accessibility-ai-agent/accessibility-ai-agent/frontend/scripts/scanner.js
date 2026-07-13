/* ===========================
   AccessAI — scanner.js
   Client-side filter & search
   =========================== */
const Scanner = {
  violations: [],
  aiAnalyses: [],
  activeSeverities: new Set(['critical','high','medium','low']),

  setData(violations, analyses) {
    this.violations = (violations || []).map((v, index) => ({...v, _sourceIndex: index}));
    this.aiAnalyses = analyses || [];
  },

  resetFilters() {
    this.activeSeverities = new Set(['critical','high','medium','low']);
  },

  getFiltered(searchText = '') {
    return this.violations.filter(v => {
      const matchSev = this.activeSeverities.has(v.severity);
      if (!matchSev) return false;
      if (!searchText) return true;
      const q = searchText.toLowerCase();
      return (
        v.description?.toLowerCase().includes(q) ||
        v.help?.toLowerCase().includes(q) ||
        v.wcag_reference?.toLowerCase().includes(q) ||
        v.tags?.some(t => t.toLowerCase().includes(q))
      );
    });
  },

  toggleSeverity(severity) {
    if (this.activeSeverities.has(severity)) {
      this.activeSeverities.delete(severity);
    } else {
      this.activeSeverities.add(severity);
    }
  },

  setSeverity(severity, enabled) {
    if (enabled) {
      this.activeSeverities.add(severity);
    } else {
      this.activeSeverities.delete(severity);
    }
  },

  getAiForViolation(index) {
    return this.aiAnalyses[index] || null;
  }
};
