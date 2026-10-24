@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python backend\local_server.py
) else (
  py backend\local_server.py
)
pause
