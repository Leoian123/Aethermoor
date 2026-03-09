@echo off
REM STATISFY RPG - Quick Start (Windows)
REM Avvia backend Flask + frontend Astro in parallelo

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend

REM --- Check .env ---
if not exist "%BACKEND%\.env" (
    echo [ERRORE] .env mancante! Copia backend\.env.example in backend\.env e aggiungi la tua API key.
    pause
    exit /b 1
)

REM --- Check venv ---
if not exist "%BACKEND%\venv\Scripts\python.exe" (
    echo [1/3] Creazione venv...
    python -m venv "%BACKEND%\venv"
    echo [2/3] Installazione dipendenze Python...
    "%BACKEND%\venv\Scripts\pip.exe" install -r "%BACKEND%\requirements.txt"
) else (
    echo [OK] venv trovato
)

REM --- Check node_modules ---
if not exist "%FRONTEND%\node_modules" (
    echo [3/3] Installazione dipendenze npm...
    pushd "%FRONTEND%"
    call npm install
    popd
)

echo.
echo === STATISFY RPG ===
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:3001
echo Chiudi le finestre per fermare tutto
echo.

REM --- Start backend in new window ---
start "Statisfy Backend" cmd /c ""%BACKEND%\venv\Scripts\python.exe" "%BACKEND%\app.py""

REM --- Start frontend in new window ---
start "Statisfy Frontend" cmd /c "cd /d "%FRONTEND%" && npm run dev"

echo Avviati! Puoi chiudere questa finestra.
