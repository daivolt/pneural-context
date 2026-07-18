# Installation Guide

## Prerequisites

Python 3.11+, PostgreSQL 16+ with pgvector and pg_trgm extensions, ollama (for embeddings)

## Production (mediserv, Linux)

### 1. Clone and venv

```bash
git clone https://github.com/daivolt/pneural-context.git /opt/pneural-context
cd /opt/pneural-context
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 2. Database

```bash
sudo -u postgres psql
CREATE USER pneural WITH PASSWORD 'YOUR_SECRET_PASS';
CREATE DATABASE pneural_context OWNER pneural;
GRANT ALL PRIVILEGES ON DATABASE pneural_context TO pneural;
\c pneural_context
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\q
```

### 3. Systemd Service

Create `/etc/systemd/system/pneural-context.service`:

```ini
[Unit]
Description=Pneural Context
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=daivolt
WorkingDirectory=/opt/pneural-context
Environment=PNEURAL_DATABASE_URL=postgresql://pneural:PASS@localhost:5432/pneural_context
Environment=PNEURAL_PORT=8778
Environment=PNEURAL_HOST=0.0.0.0
Environment=PNEURAL_LLM_URL=http://10.42.0.89:8080/v1
Environment=PNEURAL_EMBED_BACKEND=ollama
ExecStart=/opt/pneural-context/.venv/bin/python3 -m pneural_context.cli serve --host 0.0.0.0 --port 8778
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pneural-context
```

### 4. opencode Plugin

```bash
mkdir -p ~/.config/opencode/plugins/pneural-context-plugin
cp /opt/pneural-context/plugin/index.mjs ~/.config/opencode/plugins/pneural-context-plugin/
cp /opt/pneural-context/plugin/package.json ~/.config/opencode/plugins/pneural-context-plugin/
```

### 5. Project Config

Create `.pneural-context.json` in any project root:

```json
{"project": "my-project"}
```

## Development (desktop-ryzen, Windows)

### 1. Clone and venv

```powershell
git clone https://github.com/daivolt/pneural-context.git C:\pneural-context
cd C:\pneural-context
& "C:\Program Files\Python312\python.exe" -m venv .venv
.venv\Scripts\pip install -e .
```

### 2. Database

```powershell
psql -U postgres -c "CREATE USER pneural WITH PASSWORD 'pctx_SECRET'"
psql -U postgres -c "CREATE DATABASE pneural_test OWNER pneural"
psql -U pneural -d pneural_test -c "CREATE EXTENSION IF NOT EXISTS vector"
psql -U pneural -d pneural_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"
```

### 3. Scheduled Task

Create `PneuralContext` in Task Scheduler:
- Trigger: At startup
- Action: `C:\pneural-context\.venv\Scripts\python.exe -m pneural_context.cli serve --host 0.0.0.0 --port 8779`
- Env: `PNEURAL_DATABASE_URL=postgresql://pneural:pctx_SECRET@localhost:5432/pneural_test`

### 4. opencode Plugin

Copy to `C:\Users\daivolt\.config\opencode\plugins\pneural-context-plugin\`
