@echo off
cd /d "%~dp0"
python -m tankbuilder gui
if errorlevel 1 pause
