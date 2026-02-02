@echo off
REM Script per avviare il backend in locale - Windows
echo ========================================
echo PowerMeter - Avvio Backend Locale
echo ========================================
echo.

REM Verifica che Python sia installato
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Python non trovato!
    echo Assicurati di aver installato Python 3.11+
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Python trovato: %PYTHON_VERSION%
echo.

REM Verifica che esista l'ambiente virtuale
if not exist "venv" (
    echo Ambiente virtuale non trovato. Creazione in corso...
    python -m venv venv
    echo Ambiente virtuale creato.
    echo.
)

REM Attiva ambiente virtuale
echo Attivazione ambiente virtuale...
call venv\Scripts\activate.bat

REM Verifica/installa dipendenze
if not exist "venv\.dependencies_installed" (
    echo Installazione dipendenze...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    type nul > venv\.dependencies_installed
    echo Dipendenze installate.
    echo.
)

REM Crea directory necessarie
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
    )
)

REM Avvia il backend
echo ========================================
echo Avvio backend FastAPI...
echo ========================================
echo.
echo Backend disponibile su: http://localhost:8000
echo Documentazione API: http://localhost:8000/docs
echo.
echo Premi Ctrl+C per fermare il server
echo.

python -m app.main
