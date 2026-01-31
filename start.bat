@echo off
REM Script di avvio per Windows - PowerMeter Docker
echo ========================================
echo PowerMeter - Avvio Docker
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

REM Crea directory necessarie se non esistono
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo Directory create/verificate.
echo.

REM Controlla se esiste file .env, altrimenti crea da env.example.txt
if not exist ".env" (
    if exist "env.example.txt" (
        echo Creazione file .env da env.example.txt...
        copy env.example.txt .env >nul
        echo File .env creato. Modifica le configurazioni se necessario.
        echo.
    ) else if exist ".env.example" (
        echo Creazione file .env da .env.example...
        copy .env.example .env >nul
        echo File .env creato. Modifica le configurazioni se necessario.
        echo.
    )
)

REM Build e avvio container
echo Avvio container Docker...
echo.
docker compose up -d --build

if errorlevel 1 (
    echo.
    echo ERRORE durante l'avvio dei container!
    echo Controlla i log con: docker compose logs
    pause
    exit /b 1
)

echo.
echo ========================================
echo Container avviati con successo!
echo ========================================
echo.
echo Applicazione disponibile su:
echo   - Frontend: http://localhost:80 (tramite nginx)
echo   - Backend API: http://localhost:8000
echo   - Frontend diretto: http://localhost:5173
echo.
echo Per vedere i log: docker compose logs -f
echo Per fermare: docker compose down
echo.
pause
