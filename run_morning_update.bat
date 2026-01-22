@echo off
REM DSE Sniper - Morning Update Script
REM Runs at market open (10:00 AM Bangladesh Time)
REM This script runs update and analyze sequentially

echo ========================================
echo DSE SNIPER - Morning Update Started
echo Time: %date% %time%
echo ========================================

cd /d "d:\work\personal\stock-prediction-system"

echo.
echo [1/2] Updating stock data...
python main.py update
if %errorlevel% neq 0 (
    echo ERROR: Data update failed!
    exit /b 1
)

echo.
echo [2/2] Analyzing stocks and generating signals...
python main.py analyze
if %errorlevel% neq 0 (
    echo ERROR: Analysis failed!
    exit /b 1
)

echo.
echo ========================================
echo DSE SNIPER - Morning Update Completed
echo Time: %date% %time%
echo ========================================
echo.

exit /b 0
