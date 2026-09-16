@echo off
chcp 65001 >nul
python "%~dp0rename_images_by_ocr.py" %* --dry-run
echo.
echo Author: CPPU-Jiang
pause
