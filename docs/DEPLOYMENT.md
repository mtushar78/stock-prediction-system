# DSE Sniper — Ubuntu Deployment Guide (PM2)

End-to-end guide to deploy the DSE Sniper backend (FastAPI + APScheduler) and
frontend (Next.js) on a fresh Ubuntu server using **PM2** as the process
manager.

> **Database**: this guide uses **PostgreSQL on Neon**
> (`postgresql://...neon.tech/...`). The backend connects to it via
> `DATABASE_URL` in a `.env` file at the project root. There is no local
> database file on the server — all reads and writes go to Neon over TLS.
> Migration from the legacy SQLite file is documented in
> [section 4](#4-database--neon-postgresql).

---

## 0. Prerequisites

- Ubuntu 22.04 / 24.04 LTS
- A non-root sudo user (this guide uses `tushar`)
- A domain (optional, recommended for HTTPS) — e.g.
  `dse-sniper-backend.maksudul.com` (already referenced in
  `frontend/.env.production`)
- A **Neon PostgreSQL project** — create one at https://neon.tech (free
  tier is enough). You'll need the connection string in the form:
  ```
  postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require&channel_binding=require
  ```
- Outbound internet access from the server to:
  - `dsebd.org` (DSE data source)
  - `geo.iproyal.com:12321` (proxy used by `src/dse_scraper.py` and
    `src/fundamentals_scraper.py`)
  - `*.neon.tech:5432` (PostgreSQL)

---

## 1. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  build-essential git curl ufw \
  python3 python3-venv python3-pip python3-dev \
  libpq-dev \
  libxml2-dev libxslt1-dev zlib1g-dev \
  postgresql-client \
  nginx \
  chrony
```

`libpq-dev` is required to build `psycopg2-binary` from source on some
distros; `postgresql-client` gives you `psql` for ad-hoc queries against
Neon (no local server is installed).

Make sure the clock is synced (cron triggers depend on accurate time):

```bash
sudo systemctl enable --now chrony
timedatectl status                      # should say "System clock synchronized: yes"
```

> The OS timezone does **not** need to be Asia/Dhaka — APScheduler triggers
> use `BANGLADESH_TZ` explicitly. UTC is fine.

---

## 2. Install Node.js (via nvm) and PM2

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

nvm install 24
nvm alias default 24

node --version    # v24.x
npm --version

npm install -g pm2
pm2 --version
```

---

## 3. Clone the repo

```bash
mkdir -p ~/dev/dse-sniper && cd ~/dev/dse-sniper
git clone <your-repo-url> stock-prediction-system
cd stock-prediction-system
```

The expected layout (note: **no `data/dse_history.db`** anymore — `data/`
is gitignored and is only used for transient CSV exports by the scraper):

```
~/dev/dse-sniper/stock-prediction-system/
├── .env                       <-- you create this (gitignored)
├── .env.example
├── backend/
│   ├── main.py
│   └── requirements.txt
├── src/
│   ├── db_manager.py          <-- PostgreSQL connector
│   ├── analyzer.py
│   ├── portfolio_manager.py
│   ├── dse_scraper.py
│   └── fundamentals_scraper.py
├── frontend/
│   ├── package.json
│   └── .env.production
├── migrate_sqlite_to_pg.py    <-- one-shot SQLite → Neon migration
├── fill_gap.py                <-- gap-fill utility for stock_data
├── ecosystem.config.js        <-- PM2 config
└── docs/DEPLOYMENT.md
```

---

## 4. Database — Neon PostgreSQL

### 4.1 Create the `.env` file at the project root

```bash
cd ~/dev/dse-sniper/stock-prediction-system
cp .env.example .env
nano .env
```

Set `DATABASE_URL` to your Neon connection string:

```
DATABASE_URL=postgresql://neondb_owner:npg_xxxxxxxx@ep-xxxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Lock the file down — it contains a credential:

```bash
chmod 600 .env
```

> **Why this works without pm2 env injection:** `src/db_manager.py` calls
> `load_dotenv(PROJECT_ROOT / '.env')` at import time, so the backend picks
> up `DATABASE_URL` regardless of how it's launched, as long as the `.env`
> file is at the project root. **Do not** put `DATABASE_URL` into
> `ecosystem.config.js` — that file is committed to git and would leak the
> credential.

### 4.2 Schema bootstrap

The schema (`stock_data`, `metadata`, `fundamentals`, `portfolio`,
`purchase_history`, `signals_today` + indexes) is created automatically the
first time `DatabaseManager()` is instantiated — see
`src/db_manager.py:init_db()`. You don't need to run any DDL by hand.

To verify connectivity and bootstrap the schema before the backend starts:

```bash
source venv/bin/activate    # see section 5 if venv doesn't exist yet
python -c "from src.db_manager import DatabaseManager; db = DatabaseManager(); print('OK'); db.close()"
```

You should see:

```
INFO:src.db_manager:Database initialized at ep-xxxxx-pooler.ap-southeast-1.aws.neon.tech
OK
```

### 4.3 Migrate existing data from a local SQLite file (one-shot)

If you're moving an existing deployment with historical data in
`data/dse_history.db`, copy that file to the server **once** and run the
migration script. After it succeeds, delete the SQLite file — the server
will never read it again.

From your local machine:

```bash
scp data/dse_history.db tushar@<server>:~/dev/dse-sniper/stock-prediction-system/data/dse_history.db
```

On the server:

```bash
cd ~/dev/dse-sniper/stock-prediction-system
source venv/bin/activate

# Dry run first — prints row counts only, no writes
python migrate_sqlite_to_pg.py --dry-run

# Real migration — uses COPY into a staging table for stock_data,
# then INSERT ... ON CONFLICT DO UPDATE for an idempotent merge.
# Re-runnable safely; takes ~80s for 1M+ rows over a Singapore link.
python migrate_sqlite_to_pg.py
```

Verify the row counts on Neon:

```bash
psql "$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)" -c "
  SELECT 'stock_data'       AS table, COUNT(*) FROM stock_data
  UNION ALL SELECT 'metadata',         COUNT(*) FROM metadata
  UNION ALL SELECT 'portfolio',        COUNT(*) FROM portfolio
  UNION ALL SELECT 'purchase_history', COUNT(*) FROM purchase_history
  UNION ALL SELECT 'fundamentals',     COUNT(*) FROM fundamentals
  UNION ALL SELECT 'signals_today',    COUNT(*) FROM signals_today;
"
```

Once verified, archive and remove the SQLite file from the server:

```bash
rm data/dse_history.db
```

### 4.4 Schema-only deployment (no historical data)

If you don't have an existing SQLite file, just skip 4.3 entirely. The
first scrape (or the startup-time analyzer) will populate `stock_data`
from scratch using `src/dse_scraper.py`, and `fill_gap.py` can backfill
history per ticker via `stocksurferbd`:

```bash
source venv/bin/activate
python fill_gap.py            # pulls full history for every metadata ticker
# or
python fill_gap.py GP BATBC   # specific tickers only
```

---

## 5. Backend — Python venv + dependencies

```bash
cd ~/dev/dse-sniper/stock-prediction-system
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip wheel
pip install -r backend/requirements.txt
```

`backend/requirements.txt` already pins everything the backend AND the
`src/` scripts need:

| Package | Used by |
|---|---|
| `fastapi`, `uvicorn[standard]` | API server |
| `pydantic` | request/response models |
| `apscheduler`, `pytz` | scheduled scrapes |
| `pandas`, `numpy` | analyzer |
| `psycopg2-binary` | PostgreSQL driver |
| `SQLAlchemy` | engine pool used by `db.engine` (pandas `to_sql`/`read_sql`) |
| `python-dotenv` | loads `.env` |
| `stocksurferbd` | DSE history fetcher (`fill_gap.py`) |
| `openpyxl` | Excel parser used by `stocksurferbd` |
| `beautifulsoup4` | HTML parser used by `dse_scraper.py` and `fundamentals_scraper.py` |
| `requests` | HTTP client for scrapers |

### 5.1 Smoke-test the backend manually

Always test once with uvicorn before handing it to PM2 — that way any
import error, schema bootstrap problem, or network failure to Neon shows
up in your terminal instead of in `pm2 logs`.

```bash
cd ~/dev/dse-sniper/stock-prediction-system
source venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 12001
```

Expected startup output (first ~10 seconds):

```
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:backend.main:🚀 DSE Sniper API starting up...
INFO:backend.main:📊 Database: postgres @ ep-xxxxx-pooler.ap-southeast-1.aws.neon.tech
INFO:backend.main:📊 Running initial analysis...
INFO:src.db_manager:Database initialized at ep-xxxxx-pooler.ap-southeast-1.aws.neon.tech
INFO:backend.main:Loaded fundamentals for N tickers
INFO:src.analyzer:Analyzing 421 tickers...
WARNING:src.analyzer:Insufficient data for full analysis (need 200 days)   <-- normal, ~5x for newly listed stocks
...
INFO:backend.main:✅ Initial analysis completed: 251 signals generated
INFO:backend.main:✅ Verified: 251 signals saved to signals_today table
INFO:apscheduler.scheduler:Added job "Morning Scrape (10:30 AM)" to job store "default"
... (12 cron jobs total)
INFO:backend.main:Scheduler started: DSE Scraper + Weekly Fundamentals
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:12001 (Press CTRL+C to quit)
```

In another terminal, hit a few endpoints to confirm the read path:

```bash
curl -s http://127.0.0.1:12001/             | head     # health check + last_update
curl -s http://127.0.0.1:12001/api/sniper-signals | head
curl -s http://127.0.0.1:12001/api/tickers   | head
curl -s http://127.0.0.1:12001/api/portfolio | head
```

Then **Ctrl+C** to stop the dev server before launching PM2.

### 5.2 What the backend startup actually does

1. Loads `.env` → `DATABASE_URL`
2. Connects to Neon and runs `init_db()` (idempotent CREATE TABLE / CREATE
   INDEX statements) — only on the first instantiation per process
3. Runs `StockAnalyzer.analyze_all_tickers()` once and writes the result
   to `signals_today` so the frontend has data immediately
4. Starts APScheduler in `Asia/Dhaka` timezone:
   - An **intraday scrape every 8 minutes** between **10:00 and 14:56**
     (Sun–Thu, when DSE is open), plus a **15:00 pre-close** snapshot and
     the **15:15 final EOD** scrape
   - A daily **16:00 PG backup sync**
   - 1 weekly fundamentals scrape at **Saturday 08:00**
5. Listens on the configured port (12001 in this guide)

If any of those steps fails, the process exits non-zero and PM2 will
restart it (`autorestart: true`, `restart_delay: 5000` in
`ecosystem.config.js`).

---

## 6. Frontend — install + build

(unchanged from the SQLite version of this doc)

```bash
cd ~/dev/dse-sniper/stock-prediction-system/frontend

# Point the frontend at your backend (edit if your domain differs)
cat > .env.production <<'EOF'
NEXT_PUBLIC_API_URL=https://dse-sniper-backend.maksudul.com
EOF

npm install
npm run build
```

Quick smoke test:

```bash
PORT=12002 npm start
# Open http://<server>:12002 — Ctrl+C to stop
```

---

## 7. PM2 — start both services

The repo ships with `ecosystem.config.js` at the root. Open it and verify
`BASE_DIR` matches your install path (default:
`/home/tushar/dev/dse-sniper/stock-prediction-system`).

```bash
cd ~/dev/dse-sniper/stock-prediction-system
mkdir -p logs

pm2 start ecosystem.config.js
pm2 status
pm2 logs dse-backend  --lines 50
pm2 logs dse-frontend --lines 50
```

You should see two `online` processes:

```
┌─────┬────────────────┬─────────┬────────┐
│ id  │ name           │ status  │ uptime │
├─────┼────────────────┼─────────┼────────┤
│ 0   │ dse-backend    │ online  │ ...    │
│ 1   │ dse-frontend   │ online  │ ...    │
└─────┴────────────────┴─────────┴────────┘
```

> **Reminder:** `ecosystem.config.js` does **not** set `DATABASE_URL` —
> the backend reads it from `.env` at project-root via `python-dotenv`.
> If pm2 reports the backend in `errored` state with
> `RuntimeError: DATABASE_URL not set`, you forgot section 4.1.

### Make PM2 start on boot

```bash
pm2 save
pm2 startup systemd -u tushar --hp /home/tushar
# Copy/paste the sudo command pm2 prints, then:
pm2 save
```

### Verify scheduler

```bash
curl -s http://127.0.0.1:12001/api/scheduler/status
pm2 logs dse-backend --lines 100 | grep -i 'scheduler\|scrape'
```

Backend logs should mention APScheduler picking up the morning/afternoon
scrape jobs. The first real scrape will fire at the next scheduled slot
(10:30 / 11:00 / ... / 15:15 Asia/Dhaka).

---

## 8. Nginx reverse proxy + HTTPS

Replace `dse-sniper-backend.maksudul.com` and the frontend hostname with
your own.

```bash
sudo tee /etc/nginx/sites-available/dse-sniper > /dev/null <<'EOF'
# Backend (FastAPI)
server {
    listen 80;
    server_name dse-sniper-backend.maksudul.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:12001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}

# Frontend (Next.js)
server {
    listen 80;
    server_name dse-sniper.maksudul.com;

    location / {
        proxy_pass http://127.0.0.1:12002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/dse-sniper /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Issue Let's Encrypt certificates:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d dse-sniper-backend.maksudul.com -d dse-sniper.maksudul.com
```

Certbot installs an auto-renewal timer; verify:

```bash
sudo systemctl list-timers | grep certbot
```

---

## 9. Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Do **not** expose 12001/12002 directly — only Nginx talks to them via
loopback.

---

## 10. Operations cheat-sheet

```bash
# Status & logs
pm2 status
pm2 logs dse-backend
pm2 logs dse-frontend
pm2 logs dse-backend --err
pm2 logs --lines 200

# Restart / reload
pm2 restart dse-backend
pm2 restart dse-frontend
pm2 reload all                  # zero-downtime where possible

# Stop / start
pm2 stop dse-backend
pm2 start dse-backend
pm2 delete dse-backend          # removes from list

# Update after a `git pull`
cd ~/dev/dse-sniper/stock-prediction-system
git pull
source venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
pm2 restart ecosystem.config.js
pm2 save
```

### Database backups

Neon takes its own automatic point-in-time snapshots — for casual use you
can rely on that and skip local backups entirely. If you want a belt-and-
braces nightly dump, install `postgresql-client` (already in section 1)
and add to `crontab -e`:

```
30 3 * * * cd /home/tushar/dev/dse-sniper/stock-prediction-system && \
           mkdir -p backups && \
           pg_dump "$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)" \
             | gzip > backups/neon_$(date +\%F).sql.gz && \
           find backups -name 'neon_*.sql.gz' -mtime +14 -delete
```

---

## 11. Verifying the daily scraper works

After deployment, the easiest verification is to wait for the next 8-minute
scrape slot during the trading window (10:00 AM – 3:15 PM Asia/Dhaka,
Sun–Thu) and confirm:

```bash
# 1. Watch logs live
pm2 logs dse-backend | grep -i 'scrape\|analysis'

# 2. After the scrape, the latest row in stock_data should be today
psql "$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)" \
     -c "SELECT MAX(date) FROM stock_data;"

# 3. signals_today should be repopulated with fresh BUY/WAIT entries
curl -s http://127.0.0.1:12001/api/sniper-signals | head
```

If a scrape fails, look in the logs for:
- `proxy` errors → iproyal credentials may have expired
  (`src/dse_scraper.py:20-23`)
- `connection refused` / `SSL` / `could not translate host name "ep-..."`
  → Neon endpoint is asleep (free tier auto-suspends after inactivity) or
  the server can't reach `*.neon.tech:5432`. The first request after a
  cold start may take 1–3 seconds — this is normal.
- `RuntimeError: DATABASE_URL not set` → `.env` missing or unreadable by
  the user pm2 runs as
- `relation "stock_data" does not exist` → schema bootstrap was skipped;
  re-run the smoke test from section 4.2 to force `init_db()`

---

## Why PostgreSQL on Neon (and not local SQLite)

The original deployment used a local SQLite file. We migrated to Neon
PostgreSQL because:

| Concern | Outcome |
|---|---|
| **Multi-host reads** | The frontend (and any future analytics jobs) can hit Neon directly without going through this server. |
| **Backups** | Neon does point-in-time recovery automatically; no fragile cron-based `.backup` files to manage. |
| **Schema evolution** | Postgres `ALTER TABLE` is far less painful than SQLite's "rebuild the table" dance. |
| **Concurrency** | Multiple writers (manual `fill_gap.py` + scheduled scrapes + portfolio API writes) no longer contend on a single file lock. |
| **Latency** | Mitigated by a SQLAlchemy connection pool (`pool_size=5, max_overflow=10`) so the Singapore RTT is paid only on first connect, not per query. |

The trade-off is that the server **must** have outbound TCP to
`*.neon.tech:5432` and a valid `DATABASE_URL` in `.env`. There is no
"offline mode" — if Neon is unreachable, the backend will fail to start
and PM2 will keep restarting it until connectivity returns.
