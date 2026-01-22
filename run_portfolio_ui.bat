@echo off
REM DSE Sniper - Portfolio UI Launcher
REM Runs at 2:45 PM (after market close at 2:30 PM)
REM Opens the Portfolio Guardian web interface

echo ========================================
echo DSE SNIPER - Portfolio UI Starting
echo Time: %date% %time%
echo ========================================

cd /d "d:\work\personal\stock-prediction-system"

echo.
echo Starting Portfolio Guardian UI...
echo Access at: http://localhost:8080
echo.
echo Press CTRL+C to stop the server
echo ========================================
echo.

python portfolio_ui.py

exit /b 0
