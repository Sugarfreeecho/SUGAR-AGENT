@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PYTHONIOENCODING=utf-8"
set "LAUNCHER_PY=%ROOT%app\tray_launcher.py"
set "REQUIREMENTS=%ROOT%app\requirements.txt"
set "DEPENDENCY_STAMP=%ROOT%app\.requirements.installed"
if not exist "%LAUNCHER_PY%" (
  echo Missing: "%LAUNCHER_PY%"
  pause
  exit /b 1
)

rem Prefer the bundled runtime, then python.exe, then the Windows py launcher.
set "PYTHON_EXE=%ROOT%python\python.exe"
if exist "%PYTHON_EXE%" goto python_ready

set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE goto python_ready

where py >nul 2>&1
if errorlevel 1 goto python_missing
py -c "import sys" >nul 2>&1
if errorlevel 1 goto python_missing
set "PYTHON_EXE=py"

:python_ready
if not exist "%REQUIREMENTS%" (
  echo Missing: "%REQUIREMENTS%"
  pause
  endlocal
  exit /b 1
)

rem Install dependencies on first launch and whenever requirements.txt changes.
if "%SUGARAGENT_SKIP_DEPENDENCY_SYNC%"=="1" goto launch
if not exist "%DEPENDENCY_STAMP%" goto install_dependencies
fc /b "%REQUIREMENTS%" "%DEPENDENCY_STAMP%" >nul 2>&1
if errorlevel 1 goto install_dependencies
goto launch

:install_dependencies
echo Checking and installing Python dependencies...
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo pip is unavailable. Attempting to enable it...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 goto dependency_error
)
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -r "%REQUIREMENTS%"
if errorlevel 1 goto dependency_error
copy /y "%REQUIREMENTS%" "%DEPENDENCY_STAMP%" >nul

:launch
if not exist "%ROOT%app\native\sugaragent-egress-helper.exe" (
  echo Building the Windows egress helper...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\build_egress_helper_windows.ps1"
  if errorlevel 1 (
    echo Egress helper installation failed. SugarAgent will use degraded application-level protection.
  )
)
"%PYTHON_EXE%" "%LAUNCHER_PY%"
if errorlevel 1 pause
endlocal
exit /b

:dependency_error
echo.
echo Failed to install Python dependencies.
echo Check the network connection and run RUN.bat again.
pause
endlocal
exit /b 1

:python_missing
echo Python 3.10 or newer is required, but no Python runtime was found.
echo Install Python from https://www.python.org/downloads/windows/
echo Then run: python -m pip install -r app\requirements.txt
pause
endlocal
exit /b 1
