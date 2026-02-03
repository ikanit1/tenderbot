@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if %errorlevel% equ 0 (
    echo.
    echo Done. Run bot: python main.py
) else (
    echo.
    echo Trying: pip install -r requirements.txt
    pip install -r requirements.txt
)
pause
