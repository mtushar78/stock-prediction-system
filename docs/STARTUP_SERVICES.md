# DSE Sniper Startup Services

## Overview
Both the backend and frontend services are configured to run automatically on system startup using systemd.

## Service Status

### Check Service Status
```bash
# Check backend status
systemctl status dse-sniper-backend.service

# Check frontend status
systemctl status dse-sniper-frontend.service

# Check if services are enabled
systemctl is-enabled dse-sniper-backend.service dse-sniper-frontend.service
```

### Managing Services

#### Start Services
```bash
sudo systemctl start dse-sniper-backend.service
sudo systemctl start dse-sniper-frontend.service
```

#### Stop Services
```bash
sudo systemctl stop dse-sniper-backend.service
sudo systemctl stop dse-sniper-frontend.service
```

#### Restart Services
```bash
sudo systemctl restart dse-sniper-backend.service
sudo systemctl restart dse-sniper-frontend.service
```

#### Enable/Disable Autostart
```bash
# Enable services to run on startup (already done)
sudo systemctl enable dse-sniper-backend.service
sudo systemctl enable dse-sniper-frontend.service

# Disable services from running on startup
sudo systemctl disable dse-sniper-backend.service
sudo systemctl disable dse-sniper-frontend.service
```

## Service Details

### Backend Service
- **Name:** dse-sniper-backend.service
- **Description:** DSE Sniper Backend API
- **Port:** 12001
- **Location:** `/etc/systemd/system/dse-sniper-backend.service`
- **Command:** `uvicorn backend.main:app --host 0.0.0.0 --port 12001`
- **Auto-restart:** Yes (10 second delay)

### Frontend Service
- **Name:** dse-sniper-frontend.service
- **Description:** DSE Sniper Frontend
- **Port:** 12002
- **Location:** `/etc/systemd/system/dse-sniper-frontend.service`
- **Command:** `npm start` (Next.js production server)
- **Auto-restart:** Yes (10 second delay)

## Viewing Logs

### Real-time Logs
```bash
# Backend logs
sudo journalctl -u dse-sniper-backend.service -f

# Frontend logs
sudo journalctl -u dse-sniper-frontend.service -f

# Both services
sudo journalctl -u dse-sniper-backend.service -u dse-sniper-frontend.service -f
```

### Recent Logs
```bash
# Last 50 lines
sudo journalctl -u dse-sniper-backend.service -n 50
sudo journalctl -u dse-sniper-frontend.service -n 50

# Since boot
sudo journalctl -u dse-sniper-backend.service -b
sudo journalctl -u dse-sniper-frontend.service -b
```

## Updating Service Configuration

If you need to modify the service files:

1. Edit the service file in the project directory:
   - `dse-sniper-backend.service`
   - `dse-sniper-frontend.service`

2. Copy the updated file to systemd:
   ```bash
   sudo cp dse-sniper-backend.service /etc/systemd/system/
   sudo cp dse-sniper-frontend.service /etc/systemd/system/
   ```

3. Reload systemd daemon:
   ```bash
   sudo systemctl daemon-reload
   ```

4. Restart the service:
   ```bash
   sudo systemctl restart dse-sniper-backend.service
   sudo systemctl restart dse-sniper-frontend.service
   ```

## Access URLs

- **Frontend:** http://localhost:12002
- **Backend API:** http://localhost:12001
- **Backend Docs:** http://localhost:12001/docs

## Troubleshooting

### Service won't start
```bash
# Check detailed status
systemctl status dse-sniper-backend.service -l

# Check recent logs
sudo journalctl -u dse-sniper-backend.service -n 100 --no-pager
```

### Port already in use
```bash
# Find what's using the port
sudo lsof -i :12001  # for backend
sudo lsof -i :12002  # for frontend
```

### Service keeps restarting
Check the logs to identify the issue:
```bash
sudo journalctl -u dse-sniper-backend.service -f
```

## Notes

- Services are configured to restart automatically on failure
- Services start after the network is available
- Logs are stored in systemd journal
- Both services run as user `tushar`
- Backend working directory: `/home/tushar/dev/dse-sniper/stock-prediction-system`
- Frontend working directory: `/home/tushar/dev/dse-sniper/stock-prediction-system/frontend`
