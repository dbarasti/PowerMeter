@echo off
REM Script per avviare backend locale + frontend Docker - Windows
echo ========================================
echo PowerMeter - Avvio Completo (Backend Locale + Frontend Docker)
echo ========================================
echo.

REM Verifica che Docker sia installato
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Docker non trovato o non in esecuzione!
    echo Assicurati di aver installato Docker Desktop e che sia avviato.
    pause
    exit /b 1
)

REM Verifica che Python sia installato
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Python non trovato!
    pause
    exit /b 1
)

echo Prerequisiti verificati.
echo.

REM Avvia backend in una nuova finestra
echo 1. Avvio backend in locale...
start "PowerMeter Backend" cmd /k "start-backend-local.bat"

REM Attendi che il backend sia pronto
echo Attesa avvio backend...
timeout /t 5 /nobreak >nul

REM Avvia frontend Docker
echo.
echo 2. Avvio frontend in Docker...
docker compose -f docker-compose.frontend-only.yml up -d --build

if errorlevel 1 (
    echo ERRORE durante l'avvio del frontend!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Tutto avviato con successo!
echo ========================================
echo.
echo Applicazione disponibile su:
echo   - http://localhost (tramite nginx)
echo   - http://localhost:5173 (frontend diretto)
echo   - http://localhost:8000 (backend diretto)
echo.
echo Per fermare:
echo   - Frontend: docker compose -f docker-compose.frontend-only.yml down
echo   - Backend: Chiudi la finestra "PowerMeter Backend"
echo.
pause
