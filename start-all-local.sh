#!/bin/bash
# Script per avviare backend locale + frontend Docker (macOS/Linux)

echo "========================================"
echo "PowerMeter - Avvio Completo (Backend Locale + Frontend Docker)"
echo "========================================"
echo ""

# Verifica che Docker sia installato
docker --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERRORE: Docker non trovato o non in esecuzione!"
    echo "Assicurati di aver installato Docker Desktop e che sia avviato."
    exit 1
fi

# Verifica che Python sia installato
python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERRORE: Python 3 non trovato!"
    exit 1
fi

echo "Prerequisiti verificati."
echo ""

# Avvia backend in background
echo "1. Avvio backend in locale..."
./start-backend-local.sh &
BACKEND_PID=$!

# Attendi che il backend sia pronto
echo "Attesa avvio backend..."
sleep 3

# Verifica che il backend risponda
for i in {1..10}; do
    curl -s http://localhost:8000/docs >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ Backend avviato correttamente"
        break
    fi
    echo "Attesa backend... ($i/10)"
    sleep 1
done

# Avvia frontend Docker
echo ""
echo "2. Avvio frontend in Docker..."
docker compose -f docker-compose.frontend-only.yml up -d --build

if [ $? -ne 0 ]; then
    echo "ERRORE durante l'avvio del frontend!"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "========================================"
echo "Tutto avviato con successo!"
echo "========================================"
echo ""
echo "Applicazione disponibile su:"
echo "  - http://localhost (tramite nginx)"
echo "  - http://localhost:5173 (frontend diretto)"
echo "  - http://localhost:8000 (backend diretto)"
echo ""
echo "Per fermare:"
echo "  - Frontend: docker compose -f docker-compose.frontend-only.yml down"
echo "  - Backend: kill $BACKEND_PID o Ctrl+C in questo terminale"
echo ""

# Attendi terminazione
trap "echo ''; echo 'Fermata applicazione...'; docker compose -f docker-compose.frontend-only.yml down; kill $BACKEND_PID 2>/dev/null; exit" INT TERM

wait $BACKEND_PID
