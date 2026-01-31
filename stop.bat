@echo off
REM Script di stop per Windows - PowerMeter Docker
echo ========================================
echo PowerMeter - Stop Docker
echo ========================================
echo.

docker compose down

if errorlevel 1 (
    echo ERRORE durante lo stop dei container!
    pause
    exit /b 1
)

echo.
echo Container fermati con successo!
echo.
pause
