@echo off
rem Double-click: starts the local TAA demo stack (web, worker, FakeMT5 engine). See scripts\start-demo.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1" %*
if errorlevel 1 pause
