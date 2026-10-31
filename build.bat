@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Tk Windows Switcher - Nuitka build
echo ========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python launcher 'py' was not found. Install Python 3 for Windows first.
    pause
    exit /b 1
)

py -3 -m pip --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: pip is not available for Python 3.
    pause
    exit /b 1
)

echo Installing/updating Nuitka and its build dependency...
py -3 -m pip install --upgrade nuitka ordered-set
if errorlevel 1 goto :failed

echo.
echo Building a standalone, single-file GUI executable...
py -3 -m nuitka ^
    --onefile ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=disable ^
    --output-dir=dist ^
    --output-filename=TkWindowsSwitcher.exe ^
    --assume-yes-for-downloads ^
    main.py
if errorlevel 1 goto :failed

echo.
echo Build complete: dist\TkWindowsSwitcher.exe
echo Test the executable on a Windows machine before distributing it.
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Review the error output above.
pause
exit /b 1
