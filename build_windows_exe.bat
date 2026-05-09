@echo off
setlocal

cd /d "%~dp0"

set "APP_NAME=SpriteAnchor"
set "VENV_DIR=.venv-windows"
set "PYTHON_CMD="

if not exist "%APP_NAME%.py" (
    echo ERROR: %APP_NAME%.py was not found in this folder.
    pause
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD (
        py -3.11 -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3.11"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERROR: Python 3.11 or 3.12 was not found.
    echo Install Python from https://www.python.org/downloads/windows/
    echo During install, check "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Using Python:
%PYTHON_CMD% --version
if errorlevel 1 (
    echo ERROR: Could not run Python.
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.11 or 3.12 is required for this build.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating build virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo Installing build requirements...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install -r requirements_windows.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements_windows.txt.
    pause
    exit /b 1
)

if exist "dist\%APP_NAME%.exe" del /f /q "dist\%APP_NAME%.exe"
if exist "dist\%APP_NAME%_windows.zip" del /f /q "dist\%APP_NAME%_windows.zip"

echo Building %APP_NAME%.exe...
"%VENV_PY%" -m PyInstaller --clean --noconfirm "%APP_NAME%_windows.spec"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    echo Check the output above for the first error.
    pause
    exit /b 1
)

if not exist "dist\%APP_NAME%.exe" (
    echo ERROR: dist\%APP_NAME%.exe was not created.
    pause
    exit /b 1
)

echo Creating Windows zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\%APP_NAME%.exe' -DestinationPath 'dist\%APP_NAME%_windows.zip' -Force"
if errorlevel 1 (
    echo ERROR: Failed to create dist\%APP_NAME%_windows.zip.
    pause
    exit /b 1
)

echo.
echo Build complete.
echo EXE: dist\%APP_NAME%.exe
echo ZIP: dist\%APP_NAME%_windows.zip
echo.
echo Double-click dist\%APP_NAME%.exe to test it.
pause
