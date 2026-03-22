@echo off
setlocal

set "APP_HOME=%~dp0.."
set "TARGET=%APP_HOME%\.venv\Scripts\pyama-gui.exe"

if not exist "%TARGET%" (
    echo PyAMA GUI is not installed correctly. Expected "%TARGET%".
    exit /b 1
)

start "" "%TARGET%" %*
