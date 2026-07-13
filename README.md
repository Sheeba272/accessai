# accessai
AI-powered accessibility testing — WCAG 2.1, axe-core, Playwright, VPAT/ACR reports
# AccessAI — AI-Powered Accessibility Testing Platform

An enterprise web accessibility testing platform that combines automated WCAG 2.1 scanning with AI-guided analysis and remediation — producing developer-friendly findings and audit-ready VPAT/ACR reports.

> ⚠️ Portfolio/demo project. Uses public demo sites and sample data only — no client data or credentials.

## ✨ Features

- 🔍 **WCAG 2.1 automated scanning** powered by axe-core, executed on real rendered pages via Playwright
- 📋 **Guideline validator** — rule-based checks across WCAG success criteria beyond the axe defaults
- 🕷️ **Multi-page smart crawl** — scan an entire site section, not just a single URL
- 🤖 **AI remediation guidance** — LLM-generated explanations and fix suggestions for each violation
- 🧪 **AI test scenario generator** — accessibility test cases generated from scan context
- 📄 **VPAT / ACR report generation** — compliance-ready output for audits and procurement
- 💾 **Scan history** persisted in SQLite

## 🏗️ Architecture

```
Browser (Web UI)
      │
  FastAPI backend
      │
 ┌────┼────────────────────────┐
 │    │                        │
Playwright            Guideline validator
(page rendering)      (WCAG rule engine)
 │
axe-core (violation scanning)
 │
LLM layer — Ollama (local)   →   remediation guidance & test scenarios
 │
SQLite (scan history)   →   VPAT / ACR report generator
```

## 🛠️ Tech Stack

Python 3.11 · FastAPI · Playwright · axe-core · Ollama · SQLite · HTML/JS frontend

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running (optional — needed for AI guidance features)

### Setup

```bash
git clone https://github.com/Sheeba272/accessai.git
cd accessai
pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
uvicorn main:app --reload
```

Open `http://localhost:8000`, enter a URL (e.g. a public demo site), and start a scan.

## 📸 Screenshots

<!-- Drag & drop screenshots here while editing on GitHub: dashboard, scan results, VPAT report -->

## 📄 Disclaimer

Automated scanning covers a subset of WCAG success criteria; manual accessibility review is still recommended for full compliance. Built for demonstration and learning purposes.
