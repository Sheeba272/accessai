# ♿ AccessAI — Enterprise AI Accessibility Testing Agent

> AI-powered WCAG 2.1 accessibility scanner using local LLMs (Ollama), Playwright, axe-core, FastAPI, and a professional dashboard UI.

---

## 🏗️ Architecture

```
Browser (Vanilla JS) → FastAPI Backend → Playwright + axe-core → Ollama LLMs
                                      ↓
                              SQLite (scan history)
                                      ↓
                              HTML/JSON Reports
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Vanilla JS |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Browser Automation | Playwright (Chromium) |
| Accessibility Engine | axe-core 4.9 |
| AI Runtime | Ollama (local) |
| AI Models | llama3, deepseek-r1, qwen2.5, mistral |
| Database | SQLite (aiosqlite) |
| Containerization | Docker + docker-compose |

---

## ⚡ Quick Start (Local)

### Prerequisites
- Python 3.11+
- Node.js (optional — only if you want to serve frontend via npm)
- [Ollama](https://ollama.ai) installed

### 1. Clone and install
```bash
git clone <repo>
cd accessibility-ai-agent

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Start Ollama + pull a model
```bash
# Terminal 1 — start Ollama
ollama serve

# Terminal 2 — pull your model (choose one)
ollama pull llama3          # ~4GB — recommended for most machines
ollama pull qwen2.5         # ~4GB — great quality
ollama pull mistral         # ~4GB — fast
ollama pull deepseek-r1     # ~7GB — best analysis quality
```

### 3. Set up environment
```bash
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### 4. Start the backend
```bash
# From project root
python main.py
# or:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the frontend
```bash
# Option A: just open the file
open frontend/index.html

# Option B: serve with Python
python -m http.server 3000 --directory frontend
# Then visit http://localhost:3000
```

### 6. Start scanning!
- Enter a URL (e.g., `https://www.w3schools.com`)
- Select your AI model
- Click **Start AI Scan**
- Watch the real-time progress
- Explore violations, AI analysis, and download the report

---

## 🐳 Docker Deployment

```bash
cd docker
docker-compose up --build

# Pull a model into the Ollama container
docker exec accessai-ollama ollama pull llama3

# Open the app
open http://localhost
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check |
| `GET`  | `/health/ollama` | Ollama + available models |
| `POST` | `/api/scan/start` | Start a new scan |
| `GET`  | `/api/scan/{id}/status` | Poll scan progress |
| `GET`  | `/api/scan/{id}/results` | Get full results |
| `GET`  | `/api/scan/{id}/screenshot` | Get page screenshot |
| `GET`  | `/api/scans/history` | Scan history |
| `GET`  | `/api/report/{id}?format=html` | Download HTML report |
| `GET`  | `/api/report/{id}?format=json` | Download JSON report |
| `GET`  | `/docs` | Swagger UI |

### POST /api/scan/start
```json
{
  "url":        "https://example.com",
  "model":      "llama3",
  "depth":      1,
  "wcag_level": "AA"
}
```

### AI Analysis JSON Output
```json
{
  "issue_title": "Image missing alternative text",
  "severity": "critical",
  "wcag_reference": "WCAG 2.1 SC 1.1.1 — Non-text Content (Level A)",
  "business_impact": "Excludes 2.2 billion visually impaired users...",
  "affected_users": "Blind and low-vision users using screen readers",
  "technical_explanation": "The <img> element has no alt attribute...",
  "recommended_fix": "Add descriptive alt text to all images...",
  "sample_code_fix": "<img src='logo.png' alt='Company logo'>",
  "priority": "P1"
}
```

---

## 📁 Project Structure

```
accessibility-ai-agent/
├── frontend/
│   ├── index.html              ← Main dashboard UI
│   ├── styles/
│   │   ├── main.css            ← Base styles, theme, layout
│   │   ├── dashboard.css       ← Components, score, table, AI cards
│   │   └── components.css      ← Utilities, responsive
│   └── scripts/
│       ├── api.js              ← Backend API client
│       ├── ui.js               ← Rendering helpers
│       ├── scanner.js          ← Client filter/search
│       └── app.js              ← Main controller
│
├── backend/
│   ├── api/routes/
│   │   ├── scan.py             ← Scan endpoints
│   │   ├── report.py           ← Report generation
│   │   └── health.py           ← Health checks
│   ├── services/
│   │   └── scan_service.py     ← Scan orchestration
│   ├── scanner/
│   │   └── axe_scanner.py      ← Playwright + axe-core
│   ├── ai_engine/
│   │   └── ollama_service.py   ← Ollama client, prompts, analysis
│   ├── models/
│   │   └── schemas.py          ← Pydantic models
│   └── utils/
│       ├── config.py           ← Settings management
│       ├── database.py         ← SQLite async
│       ├── logger.py           ← Logging setup
│       └── validators.py       ← URL sanitization
│
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── nginx.conf
│
├── tests/
│   └── test_main.py
│
├── main.py                     ← FastAPI app entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v --asyncio-mode=auto

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=backend --cov-report=html
```

---

## 🔧 CI/CD (GitHub Actions)

See `.github/workflows/ci.yml`:
- Lint with `ruff`
- Unit tests with `pytest`
- Automated accessibility scan on main branch push
- Docker image build

Add to repository secrets/variables:
- `SCAN_TARGET_URL` — URL to scan in CI

---

## 🚀 Advanced Features (Architecture)

### Scheduled Scans
```python
# Use APScheduler (pip install apscheduler)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(run_scheduled_scan, 'cron', hour=2, args=[target_url])
scheduler.start()
```

### Jira Integration
```python
# pip install jira
from jira import JIRA
jira = JIRA(server='https://yourorg.atlassian.net', basic_auth=('email', 'token'))
issue = jira.create_issue(project='ACCESS', summary=violation['description'], issuetype={'name': 'Bug'})
```

### PDF Export
```python
# pip install weasyprint
from weasyprint import HTML
HTML(string=html_content).write_pdf('report.pdf')
```

### Kubernetes Deployment
```yaml
# Deploy backend as a Deployment + Service
# Use a ConfigMap for environment variables
# Mount Ollama as a sidecar or separate Deployment with PVC for model storage
```

---

## 🔒 Security Notes

- All URLs are validated and sanitized before scanning
- No external API calls — fully air-gapped operation
- SQLite data stored locally in `data/`
- Add authentication middleware for multi-user deployments
- For production: add JWT auth, rate limiting (`slowapi`), HTTPS

---

## 📋 Resume-Ready Project Description

> **AccessAI — Enterprise AI Accessibility Testing Agent**
> 
> Architected and built a production-grade automated accessibility testing platform using Python (FastAPI), Playwright browser automation, axe-core WCAG 2.1 engine, and locally-hosted LLMs via Ollama. The system performs real-time WCAG 2.1 scanning, classifies violations by severity (Critical/High/Medium/Low), and uses AI prompt engineering to generate human-readable explanations, business impact assessments, and code-level remediation guidance. Features a professional enterprise dashboard with real-time progress, interactive violation explorer, AI analysis cards, and downloadable HTML/JSON reports. Deployed with Docker Compose; CI/CD via GitHub Actions with automated accessibility regression testing.
> 
> **Stack:** Python · FastAPI · Playwright · axe-core · Ollama (llama3/deepseek-r1/qwen2.5/mistral) · SQLite · Docker · HTML/CSS/JS

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Ollama offline" (red dot) | Run `ollama serve` in a terminal |
| Model not found | Run `ollama pull llama3` |
| Browser launch fails | Run `playwright install chromium` |
| CORS error | Make sure backend is on port 8000 |
| Scan times out | Increase `SCAN_TIMEOUT` in `.env` |
| No AI analysis | Ollama is unreachable or model too slow — try `mistral` |
