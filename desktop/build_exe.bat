@echo off
echo ========================================================
echo Building PulseFinance.exe (Standalone Windows Desktop App)
echo ========================================================

python -m pip install pyinstaller

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "PulseFinance" ^
    --collect-all customtkinter ^
    app.py

echo.
echo ========================================================
echo Build Complete!
echo Your standalone executable is located at:
echo   dist\PulseFinance.exe
echo ========================================================
pause
