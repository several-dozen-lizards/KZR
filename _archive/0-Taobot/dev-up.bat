@echo off
set SCRIPT=%~dp0scripts\dev-up.ps1
powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%" -Detach -SkipPip
