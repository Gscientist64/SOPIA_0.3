@echo off
rem ===========================================================================
rem  SOPIA Demo - offline launcher
rem
rem  Starts everything the demonstration needs and opens the browser.
rem  No internet connection, no PostgreSQL and no Python installation are
rem  required: the API is bundled, the database is bundled, and the AI model
rem  runs locally through Ollama.
rem
rem  Deliberately a .cmd rather than a .ps1: PowerShell scripts are blocked by
rem  the default execution policy on many Windows machines.
rem
rem  Closing this window stops the SOPIA API. The AI runtime keeps running so
rem  the next start is faster; use "Stop SOPIA Demo.cmd" to stop it as well.
rem ===========================================================================
setlocal enabledelayedexpansion
title SOPIA Demo

set "ROOT=%~dp0"
set "PORT=8000"
set "DBURL=sqlite:///%ROOT:\=/%data/sopia-demo.db"
set "TAGS=%TEMP%\sopia-ollama-tags.json"

rem --- Local AI runtime ------------------------------------------------------
rem Models ship inside this bundle, so point Ollama at them instead of the
rem per-user default. A single parallel request and one loaded model keep
rem memory use predictable on a laptop.
set "OLLAMA_MODELS=%ROOT%ollama\models"
set "OLLAMA_NUM_PARALLEL=1"
set "OLLAMA_MAX_LOADED_MODELS=1"
set "OLLAMA_KEEP_ALIVE=2m"

rem --- Application -----------------------------------------------------------
set "DATABASE_URL=%DBURL%"
set "UPLOAD_DIR=%ROOT%data/uploads"
set "FRONTEND_DIST=%ROOT%frontend"
set "AI_PROVIDER=local"
set "OLLAMA_BASE_URL=http://127.0.0.1:11434"
set "EMBEDDING_DIM=1024"
set "ENVIRONMENT=development"

echo.
echo   SOPIA - Standard Operating Procedure Intelligent Assistant
echo   Offline demonstration
echo   -------------------------------------------------------------
echo.

if not exist "%ROOT%data\sopia-demo.db" (
  echo   ERROR: data\sopia-demo.db is missing.
  echo   The bundle is incomplete - re-copy the whole folder.
  echo.
  pause
  exit /b 1
)

rem --- 1. AI runtime installed? ---------------------------------------------
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA_EXE%" (
  echo   [1/4] Installing the local AI runtime ^(one time, no internet needed^)...
  if not exist "%ROOT%ollama\OllamaSetup.exe" (
    echo.
    echo   ERROR: ollama\OllamaSetup.exe is missing from the bundle.
    pause
    exit /b 1
  )
  start /wait "" "%ROOT%ollama\OllamaSetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
  rem The installer returns before its background service settles.
  ping -n 6 127.0.0.1 >nul
) else (
  echo   [1/4] Local AI runtime already installed.
)

rem --- 2. Make sure OUR runtime with OUR models is the one running ----------
rem An AI runtime left over from an earlier crash can hold the port while
rem answering nothing, and a runtime installed by the user keeps its models
rem elsewhere and would not have the bundled model at all. In both cases the
rem demo must take over rather than wait on it, so readiness is decided by
rem probing the API and checking for the models, never by looking for a process.
call :runtime_ready
if not errorlevel 1 (
  echo   [2/4] Local AI runtime is already running with the bundled model.
  goto ollama_up
)

echo   [2/4] Starting the local AI runtime...

tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if not errorlevel 1 (
  echo         a different or unresponsive runtime is present - restarting it...
  taskkill /f /im "ollama app.exe" >nul 2>&1
  taskkill /f /im ollama.exe >nul 2>&1
  rem Give the operating system time to release port 11434.
  ping -n 5 127.0.0.1 >nul
)

rem Anything else holding 11434 would stop our runtime from binding, and waiting
rem would only produce a confusing timeout. Report the holder immediately.
call :port_holder
if defined HOLDER (
  echo.
  echo   ERROR: port 11434 is already in use by another program ^(process !HOLDER!^).
  echo.
  echo   The AI runtime cannot start until that port is free. Identify it with:
  echo     tasklist /fi "pid eq !HOLDER!"
  echo.
  echo   A previous SOPIA demo that did not shut down cleanly is the usual cause:
  echo   close any leftover "SOPIA - Ollama" window, or run
  echo     taskkill /f /im ollama.exe
  echo   then start the demo again.
  echo.
  pause
  exit /b 1
)

start "SOPIA - Ollama" /min "%OLLAMA_EXE%" serve

rem NB: ping is used for waiting rather than `timeout`, which fails when the
rem script runs with stdin redirected - it would then spin as fast as the CPU
rem allows and the readiness check could never succeed.
set /a tries=0
:wait_ollama
call :runtime_ready
if not errorlevel 1 goto ollama_up
set /a tries+=1
if !tries! GEQ 45 goto ollama_failed
if !tries! LSS 4 echo         starting up...
ping -n 3 127.0.0.1 >nul
goto wait_ollama

:ollama_failed
echo.
echo   ERROR: the local AI runtime did not start within 90 seconds.
echo.
echo   To see the underlying error, open a Command Prompt and run:
echo     "%OLLAMA_EXE%" serve
echo.
echo   The most common causes are an antivirus blocking ollama.exe, or an
echo   existing Ollama installation that needs updating.
echo.
pause
exit /b 1

:ollama_up
echo         ready.

rem --- 3. Start the API -----------------------------------------------------
echo   [3/4] Starting the SOPIA API on port %PORT%...
start "SOPIA - API" /min "%ROOT%app\sopia-api.exe" --host 127.0.0.1 --port %PORT% --workers 1

set /a tries=0
:wait_api
curl.exe -s -f -o NUL --max-time 2 http://127.0.0.1:%PORT%/ready >nul 2>&1
if not errorlevel 1 goto api_up
set /a tries+=1
if !tries! GEQ 45 goto api_failed
if !tries! LSS 4 echo         starting up...
ping -n 3 127.0.0.1 >nul
goto wait_api

:api_failed
echo.
echo   ERROR: the SOPIA API did not become ready.
echo   Check the "SOPIA - API" window for details.
echo   If port %PORT% is already in use, stop the other copy of the demo first.
echo.
pause
exit /b 1

:api_up
echo         ready.

rem --- 4. Open the browser --------------------------------------------------
echo   [4/4] Opening the browser...
start "" http://localhost:%PORT%/

echo.
echo   -------------------------------------------------------------
echo   SOPIA is running at  http://localhost:%PORT%/
echo.
echo   Sign in with:   demo@sopia.local  /  Sopia-Demo-2025
echo.
echo   The first answer takes 10-30 seconds while the model loads into
echo   memory. Later answers are faster.
echo.
echo   Close this window to stop the demonstration.
echo   -------------------------------------------------------------
echo.

rem Stay open (so "close to stop" is meaningful) and report health periodically.
set /a ticks=0
:keepalive
ping -n 31 127.0.0.1 >nul
curl.exe -s -f -o NUL --max-time 3 http://127.0.0.1:%PORT%/health >nul 2>&1
if errorlevel 1 (
  echo   [!] The API stopped responding. Check the "SOPIA - API" window.
) else (
  set /a ticks+=1
  echo   [ok] SOPIA is running - http://localhost:%PORT%/   ^(health check !ticks!^)
)
goto keepalive

rem ===========================================================================
rem  Subroutine: who is listening on 11434?  Sets HOLDER to the PID (or clears it).
rem ===========================================================================
:port_holder
set "HOLDER="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":11434 .*LISTENING"') do set "HOLDER=%%p"
exit /b 0

rem ===========================================================================
rem  Subroutine: is a usable AI runtime already answering on 11434?
rem  Exit code 0 = yes (it responds AND has the bundled models), 1 = no.
rem ===========================================================================
:runtime_ready
curl.exe -s -f -o NUL --max-time 3 http://127.0.0.1:11434/api/version >nul 2>&1
if errorlevel 1 exit /b 1
curl.exe -s --max-time 8 http://127.0.0.1:11434/api/tags > "%TAGS%" 2>nul
if not exist "%TAGS%" exit /b 1
find /i "qwen2.5" "%TAGS%" >nul
if errorlevel 1 exit /b 1
find /i "mxbai-embed-large" "%TAGS%" >nul
if errorlevel 1 exit /b 1
exit /b 0
