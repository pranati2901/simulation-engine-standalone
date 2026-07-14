@echo off
title NextXR Simulation Hub
cd /d "%~dp0backend"
echo ================================================
echo   NextXR Simulation Hub
echo   Starting server...
echo.
echo   When it says "Application startup complete",
echo   open your browser at:  http://127.0.0.1:8000
echo.
echo   To stop: close this window (or press Ctrl+C).
echo ================================================
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
pause
