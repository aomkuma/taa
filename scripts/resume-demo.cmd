@echo off
rem Resume the TAA DEMO stack paused by "pause-demo.cmd" (web first, then worker and engine).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo-tasks.ps1" -Resume
echo.
echo TAA demo stack resumed: http://localhost:8001
pause
