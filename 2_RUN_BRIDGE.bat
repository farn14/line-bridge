@echo off
chcp 65001 > nul
title Personal LINE Bridge - Step 2: Bridge Running
cd /d "%~dp0"
python -u 2_run_bridge.py
pause
