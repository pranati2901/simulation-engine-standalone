@echo off
title Goalcert Scenario Engine
cd /d "%~dp0backend"
echo ================================================
echo   Goalcert Scenario Engine
echo   Starting server...
echo.
echo   When it says "Application startup complete",
echo   open your browser at:  http://127.0.0.1:8002
echo.
echo   To stop: close this window (or press Ctrl+C).
echo ================================================
echo.
REM Port 8002 is the pinned engine port: the hub's .env (SCENARIO_BASE_URL) and the
REM frontend's dev proxy both point here. This file used to say 8000 while everything
REM else said 8002 — that class of mismatch is what produced the 503 on the Agentic
REM integration (hub pointed at 8001, the service ran on 8097). One port, agreed everywhere.
REM
REM The venv is .venv — this said `venv`, which does not exist, so the script could not
REM have run as written.
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002
pause
