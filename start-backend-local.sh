#!/bin/bash
# Script per avviare il backend in locale (macOS/Linux)

echo "========================================"
echo "PowerMeter - Avvio Backend Locale"
echo "========================================"
echo ""

# Verifica che Python sia installato
python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERRORE: Python 3 non trovato!"
    echo "Assicurati di aver installato Python 3.11+"
    exit 1
fi

echo "Python trovato: $(python3 --version)"
echo ""

# Verifica che esista l'ambiente virtuale
if [ ! -d "venv" ]; then
    echo "Ambiente virtuale non trovato. Creazione in corso..."
    python3 -m venv venv
    echo "Ambiente virtuale creato."
    echo ""
fi

# Attiva ambiente virtuale
echo "Attivazione ambiente virtuale..."
source venv/bin/activate

# Verifica/installa dipendenze
if [ ! -f "venv/.dependencies_installed" ]; then
    echo "Installazione dipendenze..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/.dependencies_installed
    echo "Dipendenze installate."
    echo ""
fi

# Crea directory necessarie
mkdir -p data
mkdir -p logs

echo "Directory create/verificate."
echo ""

# Controlla se esiste file .env, altrimenti crea da env.example.txt
if [ ! -f ".env" ]; then
    if [ -f "env.example.txt" ]; then
        echo "Creazione file .env da env.example.txt..."
        cp env.example.txt .env
        echo "File .env creato. Modifica le configurazioni se necessario."
        echo ""
    fi
fi

# Avvia il backend
echo "========================================"
echo "Avvio backend FastAPI..."
echo "========================================"
echo ""
echo "Backend disponibile su: http://localhost:8000"
echo "Documentazione API: http://localhost:8000/docs"
echo ""
echo "Premi Ctrl+C per fermare il server"
echo ""

python -m app.main
