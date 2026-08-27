# ⚡ Personal Telemetry & Activity API

A self-hosted, **100% private, zero-leak** personal activity tracker and REST API. It tracks:
- **Active Coding Time & Dwell Time** (via automatic heartbeats)
- **Local Folders & Workspace File Modifications** (via local file watcher daemon)
- **Git Commits & Stats** (via automatic post-commit hook)
- **GitHub Events & PRs** (via secure GitHub REST API sync)
- **Technical Metrics & Languages Breakdown**

---

## 🛡️ Privacy Guarantee (Zero Data Leakage)

1. **Local-First**: All data is stored in your local SQLite database (`data/telemetry.db`). No telemetry ever leaves your PC.
2. **Path Sanitization**: Absolute paths like `C:\Users\YourName\SOURCE CODE\project\src\app.py` are automatically sanitized into `project/src/app.py`.
3. **Sensitive File Blocker**: Sensitive files (`.env`, `*.key`, `*.pem`, `credentials.json`, `id_rsa`) are automatically ignored and never recorded.
4. **No Code Transmitted**: Only file extension and metadata are recorded; code contents are never sent.
5. **Zero-Leak Public API**: The public endpoint (`/api/v1/public/status`) returns only high-level status (coding / idle) and top languages without revealing project names or commit messages.

---

## 🚀 Quick Start

### 1. Start the API Server & Dashboard

```bash
python cli.py server
```
* **Interactive Web Dashboard**: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
* **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 2. Check Real-Time Activity in Terminal

```bash
python cli.py status
```

Output:
```text
==================================================
       ⚡ PERSONAL TELEMETRY & ACTIVITY ⚡
==================================================
 Status:             🟢 ACTIVE (Coding)
 Coding Time Today:  1h 45m
 Commits Today:      3
 Total Events:       42
 Active Projects:    velocity, my-portfolio
 Languages:          python (28), typescript (14)
==================================================
 🌐 Dashboard:       http://127.0.0.1:8000/dashboard
 📖 API Docs:        http://127.0.0.1:8000/docs
==================================================
```

---

### 3. Track Local Workspaces (Folder Watcher)

Start the background daemon to watch a folder or workspace:
```bash
python cli.py watch "D:/SOURCE CODE"
```

---

### 4. Install Git Post-Commit Hook

Attach the automated telemetry hook to any repository:
```bash
python cli.py git-hook "D:/SOURCE CODE/velocity"
```
Every time you `git commit`, commit stats (SHA, message, files changed, insertions/deletions) will automatically be recorded by your API.

---

### 5. Sync GitHub Events

Add your GitHub username and optional Personal Access Token (PAT) in `.env`, then run:
```bash
python cli.py sync-github
```

---

## 📡 API Endpoints Overview

### Ingestion Endpoints (`x-api-key` required)
* `POST /api/v1/ingest/heartbeat` — Record coding presence
* `POST /api/v1/ingest/file-event` — Record sanitized file modification
* `POST /api/v1/ingest/batch-file-events` — Batch file events
* `POST /api/v1/ingest/git-commit` — Record git commit

### Analytics Endpoints (`x-api-key` required)
* `GET /api/v1/stats/today` — Today's dwell time, commits, and active languages
* `GET /api/v1/stats/weekly` — 7-day timeline breakdown
* `GET /api/v1/projects` — Dwell time and event count per project
* `GET /api/v1/activity/recent` — Recent sanitized activity feed

### Public Endpoint (No Auth Required)
* `GET /api/v1/public/status` — Zero-leak high-level status for your personal portfolio / website.

---

## 🧪 Testing

Run the automated test suite:
```bash
python -m pytest tests/test_api.py -v
```
