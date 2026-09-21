@echo off
setlocal
set "APP_DIR=%~dp0"
set "RUNTIME=%APP_DIR%runtime\windows"
set "RUNTIME_PYTHON=%RUNTIME%\python.exe"
set "VENV=%APP_DIR%.venv"
set "REQ=%APP_DIR%app\requirements.txt"
set "MARKER=%VENV%\.appearance-copier-requirements"
set "PY_NAME=python-3.12.10-amd64.zip"
set "PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.zip"
set "PY_SHA256=8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d"

call :find_python
if not errorlevel 1 goto python_ready
if exist "%RUNTIME_PYTHON%" (
    set "BOOTSTRAP="%RUNTIME_PYTHON%""
    echo [%TIME%] Using private Python: %RUNTIME_PYTHON%
    goto python_ready
)
call :install_python
if errorlevel 1 goto failed
set "BOOTSTRAP="%RUNTIME_PYTHON%""

:python_ready
echo [%TIME%] Dependencies will be installed at: %VENV%
if exist "%VENV%\Scripts\python.exe" goto check_dependencies
echo [%TIME%] Creating the local Python environment with %BOOTSTRAP%...
call %BOOTSTRAP% -m venv "%VENV%"
if errorlevel 1 goto failed

:check_dependencies
if not exist "%MARKER%" goto install
fc /b "%REQ%" "%MARKER%" >nul 2>nul
if errorlevel 1 goto install
"%VENV%\Scripts\python.exe" -c "import PySide6" >nul 2>nul
if errorlevel 1 goto install
echo [%TIME%] The local dependencies are already installed and current.
goto complete

:install
echo [%TIME%] Installing the packages listed in: %REQ%
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --no-input --requirement "%REQ%"
if errorlevel 1 goto failed
copy /y "%REQ%" "%MARKER%" >nul

:complete
echo [%TIME%] Dependency installation complete: %VENV%
exit /b 0

:find_python
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul && set "BOOTSTRAP=py -%%V" && echo [%TIME%] Using system Python: py -%%V && exit /b 0
)
for %%P in (python3.exe python.exe) do (
    where %%P >nul 2>nul && %%P -c "import sys; raise SystemExit(not (sys.version_info[0] == 3 and sys.version_info[1] in range(10, 15)))" >nul 2>nul && set "BOOTSTRAP=%%P" && echo [%TIME%] Using system Python: %%P && exit /b 0
)
exit /b 1

:install_python
if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo [%TIME%] ERROR: Automatic Python installation supports 64-bit x86 Windows only. 1>&2
    exit /b 1
)
where powershell.exe >nul 2>nul || (
    echo [%TIME%] ERROR: PowerShell is required to download Python. 1>&2
    exit /b 1
)
set "BOOTSTRAP_DIR=%APP_DIR%.bootstrap"
set "PY_ARCHIVE=%BOOTSTRAP_DIR%\%PY_NAME%"
if not exist "%BOOTSTRAP_DIR%" mkdir "%BOOTSTRAP_DIR%"
echo [%TIME%] Python will be installed at: %RUNTIME%
echo [%TIME%] Downloading the private Python 3.12.10 runtime from Python.org...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -ErrorAction Stop -Uri $env:PY_URL -OutFile $env:PY_ARCHIVE } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
    echo [%TIME%] ERROR: Python download failed: %PY_URL% 1>&2
    exit /b 1
)
if not exist "%PY_ARCHIVE%" (
    echo [%TIME%] ERROR: Python download did not create: %PY_ARCHIVE% 1>&2
    exit /b 1
)
for /f "usebackq delims=" %%H in (`powershell.exe -NoLogo -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath $env:PY_ARCHIVE).Hash.ToLowerInvariant()"`) do set "ACTUAL_SHA256=%%H"
if /i not "%ACTUAL_SHA256%"=="%PY_SHA256%" (
    echo [%TIME%] ERROR: Python download checksum verification failed. 1>&2
    del /q "%PY_ARCHIVE%" >nul 2>nul
    exit /b 1
)
echo [%TIME%] Extracting Python...
if exist "%BOOTSTRAP_DIR%\extract" rmdir /s /q "%BOOTSTRAP_DIR%\extract"
mkdir "%BOOTSTRAP_DIR%\extract"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -LiteralPath $env:PY_ARCHIVE -DestinationPath '%BOOTSTRAP_DIR%\extract' -Force -ErrorAction Stop } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
    echo [%TIME%] ERROR: Python archive extraction failed. 1>&2
    exit /b 1
)
if not exist "%BOOTSTRAP_DIR%\extract\python.exe" (
    echo [%TIME%] ERROR: Extracted Python runtime is incomplete. 1>&2
    exit /b 1
)
"%BOOTSTRAP_DIR%\extract\python.exe" -c "import ensurepip, venv"
if errorlevel 1 (
    echo [%TIME%] ERROR: Extracted Python runtime failed its self-test. 1>&2
    exit /b 1
)
if not exist "%APP_DIR%runtime" mkdir "%APP_DIR%runtime"
if exist "%RUNTIME%" rmdir /s /q "%RUNTIME%"
move "%BOOTSTRAP_DIR%\extract" "%RUNTIME%" >nul
if errorlevel 1 (
    echo [%TIME%] ERROR: Could not move Python into: %RUNTIME% 1>&2
    exit /b 1
)
rmdir /s /q "%BOOTSTRAP_DIR%"
exit /b 0

:failed
echo [%TIME%] ERROR: Dependency installation failed. See the messages above. 1>&2
pause
exit /b 1
