@echo off
setlocal

cd /d "%~dp0"

echo Starting Industrial Digital Twin demo...

start "Backend - Flask 5000" cmd /k python run.py
timeout /t 2 /nobreak >nul
start "Frontend - Static 3000" cmd /k python -m http.server 3000 -d frontend

timeout /t 1 /nobreak >nul
start "" http://localhost:3000

echo Demo startup commands sent.
endlocal
