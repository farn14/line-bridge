@echo off
chcp 65001 > nul
title Personal LINE Bridge - Step 1: Login & Find Groups
cd /d "%~dp0"
python -u 1_login_and_find_groups.py
pause
