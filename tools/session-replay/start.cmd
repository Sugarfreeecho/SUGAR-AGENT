@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
"SessionReplay.exe" %*
if errorlevel 1 pause
