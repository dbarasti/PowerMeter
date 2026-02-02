# Frontend Docker - Backend Locale

Questa configurazione permette di eseguire solo il frontend in Docker mentre il backend gira in locale. Utile per sviluppo o quando serve accesso diretto al dispositivo Modbus.

## Setup

### 1. Avvia il Backend in Locale

**Su macOS/Linux:**
```bash
./start-backend-local.sh
```

**Su Windows:**
```bash
start-backend-local.bat
```

**Oppure manualmente:**
```bash
# Attiva ambiente virtuale (se presente)
# macOS/Linux: source venv/bin/activate
# Windows: venv\Scripts\activate

python -m app.main
```

Il backend sarà disponibile su `http://localhost:8000`

### 2. Avvia il Frontend in Docker

**Su macOS/Linux:**
```bash
./start-frontend-docker.sh
```

**Su Windows:**
```bash
start-frontend-docker.bat
```

**Oppure manualmente:**
```bash
docker compose -f docker-compose.frontend-only.yml up -d --build
```

## Accesso

Dopo l'avvio, l'applicazione è disponibile su:

- **http://localhost** (tramite nginx - consigliato)
- **http://localhost:5173** (frontend diretto)

## Come Funziona

- **Frontend**: Esegue in Docker (container `powermeter-frontend`)
- **Nginx**: Esegue in Docker e fa proxy delle chiamate `/api/*` al backend locale
- **Backend**: Esegue in locale su `localhost:8000`
- **Comunicazione**: Usa `host.docker.internal` per raggiungere il backend dal container

## Vantaggi

- ✅ Accesso diretto al dispositivo Modbus (nessun problema con porte seriali in Docker)
- ✅ Debug più semplice del backend (log diretti, breakpoint, etc.)
- ✅ Modifiche al backend si riflettono immediatamente (hot reload se abilitato)
- ✅ Frontend isolato in Docker (ambiente consistente)

## Troubleshooting

### Il frontend non si connette al backend

1. **Verifica che il backend sia in esecuzione:**
   ```bash
   curl http://localhost:8000/docs
   ```

2. **Verifica che il backend ascolti su `0.0.0.0`:**
   - Controlla `app/config.py`: `SERVER_CONFIG["host"] = "0.0.0.0"`

3. **Su Linux, `host.docker.internal` potrebbe non funzionare:**
   - Trova l'IP del host: `ip addr show docker0 | grep inet`
   - Modifica `docker-compose.frontend-only.yml` e `nginx-frontend-only.conf`:
     - Sostituisci `host.docker.internal` con l'IP trovato (es: `172.17.0.1`)

### Porta 8000 già in uso

Se hai già il backend Docker in esecuzione:
```bash
docker compose down
```

Poi avvia il backend locale.

### Frontend non si avvia

Controlla i log:
```bash
docker compose -f docker-compose.frontend-only.yml logs -f frontend
```

## Comandi Utili

```bash
# Visualizza log
docker compose -f docker-compose.frontend-only.yml logs -f

# Riavvia frontend
docker compose -f docker-compose.frontend-only.yml restart frontend

# Stop
docker compose -f docker-compose.frontend-only.yml down

# Rebuild frontend
docker compose -f docker-compose.frontend-only.yml up -d --build frontend
```

## Note

- Il backend locale deve essere in ascolto su `0.0.0.0:8000` (già configurato)
- Su macOS/Windows, `host.docker.internal` funziona automaticamente
- Su Linux potrebbe essere necessario configurare manualmente l'IP del host
