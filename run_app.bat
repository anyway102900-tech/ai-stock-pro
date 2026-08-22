@echo off
start "Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 2 > nul
start "Frontend" cmd /k "cd /d %~dp0frontend && npm.cmd run dev"
timeout /t 3 > nul
npx.cmd -y untun@latest tunnel --port 5173
