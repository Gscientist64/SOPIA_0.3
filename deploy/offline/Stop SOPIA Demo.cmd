@echo off
rem Stops the SOPIA demo: the API and the local AI runtime.
rem Both are stopped unconditionally so this cannot fail when one of them has
rem already exited, and it needs no interactive input.
setlocal

echo Stopping SOPIA...

tasklist /fi "imagename eq sopia-api.exe" 2>nul | find /i "sopia-api.exe" >nul
if errorlevel 1 (echo   - API was not running) else (
  taskkill /f /im sopia-api.exe >nul 2>&1
  echo   - API stopped
)

tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (echo   - AI runtime was not running) else (
  taskkill /f /im "ollama app.exe" >nul 2>&1
  taskkill /f /im ollama.exe >nul 2>&1
  echo   - AI runtime stopped
)

echo.
echo   Memory used by the model has been released.
echo.
pause
