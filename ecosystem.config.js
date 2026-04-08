// PM2 ecosystem config for DSE Sniper
// Usage:
//   pm2 start ecosystem.config.js
//   pm2 save && pm2 startup
//
// Adjust BASE_DIR below if you clone to a different path.
// Both the backend and frontend assume a Python venv at  $BASE_DIR/venv
// and the frontend already built (`npm run build`) in $BASE_DIR/frontend.

const BASE_DIR = '/home/tushar/dev/dse-sniper/stock-prediction-system';

module.exports = {
  apps: [
    {
      name: 'dse-backend',
      cwd: `${BASE_DIR}/backend`,
      script: `${BASE_DIR}/venv/bin/uvicorn`,
      args: 'main:app --host 0.0.0.0 --port 12001',
      interpreter: 'none', // run the binary directly
      env: {
        PYTHONUNBUFFERED: '1',
        TZ: 'Asia/Dhaka', // not strictly required (CronTrigger uses BD tz) but keeps logs consistent
      },
      max_memory_restart: '1G',
      autorestart: true,
      restart_delay: 5000,
      out_file: `${BASE_DIR}/logs/backend.out.log`,
      error_file: `${BASE_DIR}/logs/backend.err.log`,
      merge_logs: true,
      time: true,
    },
    {
      name: 'dse-frontend',
      cwd: `${BASE_DIR}/frontend`,
      script: 'npm',
      args: 'start',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production',
        PORT: '12002',
      },
      max_memory_restart: '512M',
      autorestart: true,
      restart_delay: 5000,
      out_file: `${BASE_DIR}/logs/frontend.out.log`,
      error_file: `${BASE_DIR}/logs/frontend.err.log`,
      merge_logs: true,
      time: true,
    },
  ],
};
