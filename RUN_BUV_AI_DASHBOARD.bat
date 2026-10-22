@echo off
setlocal
cd /d "%~dp0"
title BUV AI Evaluation Dashboard v2.0.0

echo.
echo ============================================================
echo   BUV AI Evaluation Dashboard v2.0.0
echo   One-Click Local Controlled Release
echo ============================================================
echo.
echo Please keep this window open while using the dashboard.
echo First start may prepare an official portable Python runtime locally.
echo No Administrator rights are required.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\BOOTSTRAP_AND_RUN.ps1"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo ============================================================
  echo   STARTUP FAILED
  echo ============================================================
  echo.
  echo Read the ERROR above and check logs\bootstrap.log.
  echo Send that error/log to the BUV AI platform owner or ICT.
  echo.
  pause
)
exit /b %RC%
