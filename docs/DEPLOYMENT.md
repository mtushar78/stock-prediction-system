# DSE Sniper — Ubuntu Deployment Guide (PM2)

End-to-end guide to deploy the DSE Sniper backend (FastAPI + APScheduler) and
frontend (Next.js) on a fresh Ubuntu server using **PM2** as the process
manager.

> **Database**: this guide assumes the existing **SQLite** database
> (`data/dse_history.db`). It is the recommended choice — see
> "Why SQLite" at the bottom. If you intend to migrate to PostgreSQL, that
> requires a code rewrite of `src/db_manager.py` and is **not** covered here.

---

## 0. Prerequisites

- Ubuntu 22.04 / 24.04 LTS
- A non-root sudo user (this guide uses `tushar`)
- A domain (optional, recommended for HTTPS) — e.g.
  `dse-sniper-backend.maksudul.com` (already referenced in
  `frontend/.env.production`)
- Outbound internet access to:
  - `dsebd.org` (DSE data source)
  - `geo.iproyal.com:12321` (proxy used by `src/dse_scraper.py`)

---

## 1. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  build-essential git curl ufw \
  python3 python3-venv python3-pip python3-dev \
  libxml2-dev libxslt1-dev zlib1g-dev \
  sqlite3 \
  nginx \
  chrony
```

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

The expected layout:

```
~/dev/dse-sniper/stock-prediction-system/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   └── .env.production
├── src/
├── data/
│   └── dse_history.db
├── ecosystem.config.js
└── docs/DEPLOYMENT.md
```

---

## 4. Restore the database

If you are deploying onto a fresh server, copy your local
`data/dse_history.db` (the one this repo's `fill_gap.py` populates) to the
server **before** starting the backend. From your local machine:

```bash
scp data/dse_history.db tushar@<server>:~/dev/dse-sniper/stock-prediction-system/data/dse_history.db
```

Verify on the server:

```bash
sqlite3 data/dse_history.db "SELECT MIN(date), MAX(date), COUNT(*) FROM stock_data;"
```

You should see the latest date (e.g., `2026-04-07`) and ~1.07M rows.

---

## 5. Backend — Python venv + dependencies

```bash
cd ~/dev/dse-sniper/stock-prediction-system
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip wheel
pip install -r backend/requirements.txt

# Extra deps used by src/ that are not in backend/requirements.txt:
pip install stocksurferbd openpyxl beautifulsoup4 requests
```

Smoke-test (Ctrl+C after you see "Application startup complete"):

```bash
cd backend
../venv/bin/uvicorn main:app --host 127.0.0.1 --port 12001
```

You should see:

```
INFO:main:🚀 DSE Sniper API starting up...
INFO:src.db_manager:Database initialized at .../data/dse_history.db
INFO:main:📊 Running initial analysis...
INFO:main:✅ Initial analysis completed: ... signals generated
INFO: Application startup complete.
```

---

## 6. Frontend — install + build

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
pm2 logs dse-backend --lines 50
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

### Make PM2 start on boot

```bash
pm2 save
pm2 startup systemd -u tushar --hp /home/tushar
# Copy/paste the sudo command pm2 prints, then:
pm2 save
```

### Verify scheduler

```bash
curl -s http://127.0.0.1:12001/system/status
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

# Database backups (run nightly via cron)
cp data/dse_history.db backups/dse_history.$(date +%F).db
```

Add a daily backup cron entry (`crontab -e`):

```
30 3 * * * cd /home/tushar/dev/dse-sniper/stock-prediction-system && \
           mkdir -p backups && \
           sqlite3 data/dse_history.db ".backup backups/dse_history.$(date +\%F).db" && \
           find backups -name 'dse_history.*.db' -mtime +14 -delete
```

`sqlite3 .backup` is hot-safe (atomic) — preferred over plain `cp` while
the backend is writing.

---

## 11. Verifying the daily scraper works

After deployment, the easiest verification is to wait for the next 30-min
scrape slot during the trading window (10:30 AM – 3:15 PM Asia/Dhaka,
Sun–Thu) and confirm:

```bash
# 1. Watch logs live
pm2 logs dse-backend | grep -i 'scrape\|analysis'

# 2. After the scrape, the latest DB row should be today
sqlite3 data/dse_history.db "SELECT MAX(date) FROM stock_data;"

# 3. signals_today should be repopulated with a fresh timestamp
curl -s http://127.0.0.1:12001/signals/today | head
```

If a scrape fails, look in the logs for:
- `proxy` errors → iproyal credentials may have expired
  (`src/dse_scraper.py:20-23`)
- `connection refused` → outbound network blocked by firewall / hosting
  provider
- `no such table` → database was started before the schema migrations ran
  (the `init_db` call in `db_manager.py` creates them on first connect)

---

## Why SQLite (and not PostgreSQL)

| Concern | Reality |
|---|---|
| **DB size** | 135 MB after 13+ years of data; grows ~15-20 MB/year. Will not exhaust any disk. |
| **Concurrency** | Single writer (the scheduler), many readers (the API). SQLite WAL mode handles this perfectly. |
| **Latency** | In-process function calls. Postgres adds 1-300ms RTT per query depending on region. The analyzer makes hundreds of queries per scrape. |
| **Migration cost** | `src/db_manager.py`, `analyzer.py`, `backfill_*.py`, `main.py` all use raw `sqlite3`. INSERT OR REPLACE → ON CONFLICT, schema needs porting, `df.to_sql` needs SQLAlchemy. Days of work + new bugs. |
| **Free Postgres tiers** | Storage caps (Neon 0.5 GB, Supabase 500 MB) get tight. Latency from BD to US/EU regions kills performance. |

If you ever genuinely need Postgres (multi-server writes, multi-tenant,
advanced analytics), the migration is a focused project — open a separate
ticket.
