@echo off
REM Script per verificare che COM4 sia mappata correttamente in Docker
echo ========================================
echo Verifica Porta COM4 in Docker
echo ========================================
echo.

echo 1. Verifica dispositivi seriali nel container:
docker compose exec backend ls -la /dev/tty* 2>nul | findstr /i "ttyS ttyUSB ttyACM"
echo.

echo 2. Test connessione seriale:
docker compose exec backend python -c "import serial; s = serial.Serial('/dev/ttyUSB0', 9600, timeout=1); print('OK: Porta /dev/ttyUSB0 trovata e accessibile'); s.close()" 2>nul
if errorlevel 1 (
    echo ERRORE: Porta /dev/ttyUSB0 non accessibile
    echo.
    echo Possibili soluzioni:
    echo - Verifica che COM4 sia la porta corretta in Windows
    echo - Prova a cambiare /dev/ttyS3 in /dev/ttyUSB0 nel docker-compose.yml
    echo - Verifica che il dispositivo sia collegato e il driver installato
)
echo.

echo 3. Log del backend per errori Modbus:
docker compose logs backend 2>nul | findstr /i "modbus serial port" | findstr /v "INFO"
echo.

pause
