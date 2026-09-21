@echo off
setlocal
set "APP_DIR=%~dp0"
set "LOCAL_PYTHON=%APP_DIR%.venv\Scripts\python.exe"

echo [%TIME%] Elden Ring Appearance Copier starting...
call :find_system_python
if not errorlevel 1 (
    echo [%TIME%] Using system Python and PySide6: %PYTHON_CMD%
    goto launch
)

if exist "%LOCAL_PYTHON%" (
    "%LOCAL_PYTHON%" -c "import PySide6" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD="%LOCAL_PYTHON%""
        echo [%TIME%] Using locally installed dependencies: %APP_DIR%.venv
        goto launch
    )
)

echo.
echo Python with PySide6 was not found on the system.
echo A private Python runtime, if needed, will be installed at:
echo   %APP_DIR%runtime\windows
echo The Python packages will be installed at:
echo   %APP_DIR%.venv
echo This does not require administrator access or modify system packages.
echo.
set "INSTALL_ANSWER="
set /p "INSTALL_ANSWER=Install the dependencies now? [y/N] "
if /i "%INSTALL_ANSWER%"=="y" goto install
if /i "%INSTALL_ANSWER%"=="yes" goto install
echo [%TIME%] Dependencies were not installed.
echo [%TIME%] Run "%APP_DIR%install-dependencies.bat" when you are ready.
exit /b 1

:install
call "%APP_DIR%install-dependencies.bat"
if errorlevel 1 (
    echo [%TIME%] ERROR: Dependency installation failed. 1>&2
    pause
    exit /b 1
)
set "PYTHON_CMD="%LOCAL_PYTHON%""

:launch
set "ER_APPEARANCE_ROOT=%APP_DIR%"
set "PYTHONPATH=%APP_DIR%app"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUNBUFFERED=1"
echo [%TIME%] Opening the application...
call %PYTHON_CMD% "%APP_DIR%app\face_favorites_gui.py" %*
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
    echo [%TIME%] ERROR: Application exited with code %APP_EXIT%. 1>&2
    pause
) else (
    echo [%TIME%] Application closed normally.
)
exit /b %APP_EXIT%

:find_system_python
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
    py -%%V -c "import PySide6" >nul 2>nul && set "PYTHON_CMD=py -%%V" && exit /b 0
)
for %%P in (python3.exe python.exe) do (
    where %%P >nul 2>nul && %%P -c "import sys, PySide6; raise SystemExit(not (sys.version_info[0] == 3 and sys.version_info[1] in range(10, 15)))" >nul 2>nul && set "PYTHON_CMD=%%P" && exit /b 0
)
exit /b 1
