/* ===========================
   AccessAI — api.js
   Backend API client
   =========================== */
const API_BASE = 'http://localhost:8000';

const Api = {
  async checkHealth() {
    try {
      const r = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
      return r.ok;
    } catch { return false; }
  },

  async startScan({ url, model, depth, wcagLevel }) {
    const r = await fetch(`${API_BASE}/api/scan/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, model, depth: parseInt(depth), wcag_level: wcagLevel })
    });
    if (!r.ok) throw new Error(`Scan start failed: ${r.status}`);
    return r.json();
  },

  async getScanStatus(scanId) {
    const r = await fetch(`${API_BASE}/api/scan/${scanId}/status`);
    if (!r.ok) throw new Error(`Status check failed: ${r.status}`);
    return r.json();
  },

  async getScanResults(scanId) {
    const r = await fetch(`${API_BASE}/api/scan/${scanId}/results`);
    if (!r.ok) throw new Error(`Results fetch failed: ${r.status}`);
    return r.json();
  },

  async downloadReport(scanId, format = 'html') {
    const r = await fetch(`${API_BASE}/api/report/${scanId}?format=${format}`);
    if (!r.ok) throw new Error(`Report download failed: ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `accessibility-report-${scanId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },

  async downloadComplianceReport(scanId, type = 'vpat', format = 'html') {
    const r = await fetch(`${API_BASE}/api/report/${scanId}?type=${type}&format=${format}`);
    if (!r.ok) throw new Error(`Compliance report download failed: ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}-${scanId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },

  async getScanHistory() {
    try {
      const r = await fetch(`${API_BASE}/api/scans/history`);
      return r.ok ? r.json() : { scans: [] };
    } catch { return { scans: [] }; }
  },

  async getScreenshot(scanId) {
    return `${API_BASE}/api/scan/${scanId}/screenshot`;
  },

  // Poll until done or error
  async pollScan(scanId, onProgress) {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const status = await this.getScanStatus(scanId);
          onProgress(status);
          if (status.status === 'completed') {
            clearInterval(interval);
            const results = await this.getScanResults(scanId);
            resolve(results);
          } else if (status.status === 'failed') {
            clearInterval(interval);
            reject(new Error(status.error || 'Scan failed'));
          }
        } catch (err) {
          clearInterval(interval);
          reject(err);
        }
      }, 1500);
    });
  }
};
