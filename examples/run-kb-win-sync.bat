@echo off
set CONFIG=%USERPROFILE%\kb-win-sync\config.yaml
python -m kb_win_sync --config "%CONFIG%"
