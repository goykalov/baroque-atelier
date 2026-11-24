@echo off
setlocal
set "BAROQUE_ATELIER=1"
set "entry=%~dp0palace_launcher.pyw"
if defined BAROQUE_PYTHON if exist "%BAROQUE_PYTHON%" call :try "%BAROQUE_PYTHON%"
if defined started exit /b 0
where pyw.exe >nul 2>&1
if not errorlevel 1 (
  py.exe -3 -c "import sys, tkinter; assert sys.version_info[:2] >= (3,9); tkinter.Tcl()" >nul 2>&1
  if not errorlevel 1 (
    start "" pyw.exe -3 "%entry%"
    exit /b 0
  )
)
where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe -c "import sys, tkinter; assert sys.version_info[:2] >= (3,9); tkinter.Tcl()" >nul 2>&1
  if not errorlevel 1 (
    start "" python.exe "%entry%"
    exit /b 0
  )
)
if exist "%USERPROFILE%\.rhinocode\py313-rh9\python.exe" call :try "%USERPROFILE%\.rhinocode\py313-rh9\python.exe"
if defined started exit /b 0
echo Python 3.9 or newer with Tcl/Tk is required. Install from python.org or set BAROQUE_PYTHON.
pause
exit /b 1

:try
set "python_path=%~1"
"%python_path%" -c "import sys, tkinter; assert sys.version_info[:2] >= (3,9); tkinter.Tcl()" >nul 2>&1
if errorlevel 1 exit /b 0
if exist "%~dp1pythonw.exe" set "python_path=%~dp1pythonw.exe"
start "" "%python_path%" "%entry%"
if not errorlevel 1 set "started=yes"
exit /b 0
