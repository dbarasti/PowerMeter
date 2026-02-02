#!/bin/bash
# Script per avviare solo il frontend in Docker (backend in locale)

echo "========================================"
echo "PowerMeter - Avvio Frontend Docker"
echo "========================================"
echo ""

# Verifica che Docker sia installato e in esecuzione
docker --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERRORE: Docker non trovato o non in esecuzione!"
    echo "Assicurati di aver installato Docker Desktop e che sia avviato."
    exit 1
fi

# Verifica che Docker Compose sia disponibile
docker compose version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERRORE: Docker Compose non trovato!"
    exit 1
fi

echo "Verifica Docker completata."
echo ""

# Avvia frontend e nginx
echo "Avvio frontend e nginx in Docker..."
echo ""
docker compose -f docker-compose.frontend-only.yml up -d --build

if [ $? -ne 0 ]; then
    echo ""
    echo "ERRORE durante l'avvio dei container!"
    echo "Controlla i log con: docker compose -f docker-compose.frontend-only.yml logs"
    exit 1
fi

echo ""
echo "========================================"
echo "Container avviati con successo!"
echo "========================================"
echo ""
echo "Frontend disponibile su:"
echo "  - http://localhost (tramite nginx)"
echo "  - http://localhost:5173 (frontend diretto)"
echo ""
echo "IMPORTANTE: Assicurati che il backend sia in esecuzione su http://localhost:8000"
echo "Per avviarlo: python -m app.main"
echo ""
echo "Per vedere i log: docker compose -f docker-compose.frontend-only.yml logs -f"
echo "Per fermare: docker compose -f docker-compose.frontend-only.yml down"
echo ""
