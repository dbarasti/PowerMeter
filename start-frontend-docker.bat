@echo off
REM Script per avviare solo il frontend in Docker (backend in locale) - Windows
echo ========================================
echo PowerMeter - Avvio Frontend Docker
echo ========================================
echo.

REM Verifica che Docker sia installato e in esecuzione
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Docker non trovato o non in esecuzione!
    echo Assicurati di aver installato Docker Desktop e che sia avviato.
    pause
    exit /b 1
)

REM Verifica che Docker Compose sia disponibile
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Docker Compose non trovato!
    pause
    exit /b 1
)

echo Verifica Docker completata.
echo.

REM Avvia frontend e nginx
echo Avvio frontend e nginx in Docker...
echo.
docker compose -f docker-compose.frontend-only.yml up -d --build

if errorlevel 1 (
    echo.
    echo ERRORE durante l'avvio dei container!
    echo Controlla i log con: docker compose -f docker-compose.frontend-only.yml logs
    pause
    exit /b 1
)

echo.
echo ========================================
echo Container avviati con successo!
echo ========================================
echo.
echo Frontend disponibile su:
echo   - http://localhost (tramite nginx)
echo   - http://localhost:5173 (frontend diretto)
echo.
echo IMPORTANTE: Assicurati che il backend sia in esecuzione su http://localhost:8000
echo Per avviarlo: python -m app.main
echo.
echo Per vedere i log: docker compose -f docker-compose.frontend-only.yml logs -f
echo Per fermare: docker compose -f docker-compose.frontend-only.yml down
echo.
pause
