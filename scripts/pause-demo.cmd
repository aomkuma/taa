@echo off
rem Pause the TAA DEMO stack (web, worker, engine) before closing the laptop.
rem Open positions keep their broker-side SL/TP. "resume-demo.cmd" starts it again.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo-tasks.ps1" -Pause
echo.
echo TAA demo stack paused. Double-click "TAA Resume" to start it again.
pause
