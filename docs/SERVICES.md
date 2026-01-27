# DSE Sniper Services

## Quick Commands

### Start Services
```bash
sudo systemctl start dse-sniper-backend dse-sniper-frontend
```

### Stop Services
```bash
sudo systemctl stop dse-sniper-backend dse-sniper-frontend
```

### Restart Services
```bash
sudo systemctl restart dse-sniper-backend dse-sniper-frontend
```

### Check Status
```bash
sudo systemctl status dse-sniper-backend dse-sniper-frontend
```

### View Logs
```bash
# Backend logs
sudo journalctl -u dse-sniper-backend -f

# Frontend logs
sudo journalctl -u dse-sniper-frontend -f
```

---

## URLs

**Local:**
- Frontend: http://localhost:12002
- Backend: http://localhost:12001

**Production:**
- Frontend: https://dse-sniper.maksudul.com
- Backend: https://dse-sniper-backend.maksudul.com
- API Docs: https://dse-sniper-backend.maksudul.com/docs

---

## Service Info

- **Backend Port:** 12001
- **Frontend Port:** 12002
- **Auto-Updates:** 10:15 AM, 12:00 PM, 2:45 PM (Bangladesh Time)
