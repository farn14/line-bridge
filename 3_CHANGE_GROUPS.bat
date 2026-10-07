@echo off
chcp 65001 > nul
title Personal LINE Bridge - Change Groups
cd /d "%~dp0"
python -u 3_change_groups.py
