# PowerMeter - Guida Docker

Questo progetto è stato dockerizzato per essere eseguito facilmente su Windows (e altri sistemi operativi) con un semplice click.

## Prerequisiti

1. **Docker Desktop** installato e avviato
   - Scarica da: https://www.docker.com/products/docker-desktop
   - Assicurati che Docker Desktop sia in esecuzione prima di avviare il progetto

2. **Porte disponibili**:
   - Porta 80 (nginx - accesso principale)
   - Porta 8000 (backend API)
   - Porta 5173 (frontend diretto, opzionale)

## Avvio Rapido (Windows)

### Metodo 1: Script Batch (Consigliato)

1. Doppio click su `start.bat`
2. Attendi che i container vengano costruiti e avviati
3. Apri il browser su: **http://localhost**

### Metodo 2: Docker Compose Manuale

```bash
# Build e avvio
docker compose up -d --build

# Visualizza log
docker compose logs -f

# Stop
docker compose down
```

## Configurazione

### File .env

Il file `.env.example` contiene le variabili d'ambiente configurabili. Se non esiste un file `.env`, viene creato automaticamente da `.env.example` al primo avvio.

**Variabili importanti:**

- `MODBUS_PORT`: Porta seriale Modbus (default: `/dev/ttyUSB0`)
  - Su Windows, potrebbe essere necessario mappare la porta COM
  - Esempio: `COM3` potrebbe essere `/dev/ttyS2` o `/dev/ttyUSB0`
  
- `SECRET_KEY`: Chiave segreta per JWT (CAMBIARE IN PRODUZIONE!)

- `TIMEZONE`: Fuso orario (default: `Europe/Rome`)

### Porta Serial Modbus su Windows

Su Windows, per usare una porta seriale COM con Docker:

1. Identifica la porta COM (es. `COM3`)
2. In Docker Desktop, vai su Settings > Resources > WSL Integration
3. Oppure usa un driver USB-to-Serial che espone la porta come `/dev/ttyUSB*`

**Nota**: Il mapping delle porte seriali in Docker su Windows può essere complesso. Se necessario, consulta la documentazione Docker per il tuo sistema.

## Struttura Docker

Il progetto è composto da 3 container:

1. **backend** (powermeter-backend)
   - FastAPI su Python 3.11
   - Porta: 8000
   - Database SQLite persistito in `./data`

2. **frontend** (powermeter-frontend)
   - SvelteKit con adapter-node
   - Porta: 5173
   - Serve l'interfaccia web

3. **nginx** (powermeter-nginx)
   - Reverse proxy
   - Porta: 80
   - Routing unificato: `/api/*` → backend, `/` → frontend

## Persistenza Dati

### Database SQLite

Il database è persistito nella cartella `./data` del progetto:
- File: `./data/thermal_tests.db`
- **IMPORTANTE**: Questa cartella viene montata come volume, quindi i dati persistono anche dopo lo stop dei container

### Log

I log vengono salvati in `./logs` (se configurato)

## Accesso all'Applicazione

Dopo l'avvio, l'applicazione è disponibile su:

- **http://localhost** (tramite nginx - consigliato)
- **http://localhost:8000** (backend API diretto)
- **http://localhost:5173** (frontend diretto)

### Credenziali Default

- Username: `admin`
- Password: `admin`
- **IMPORTANTE**: Cambiare la password al primo utilizzo!

## Comandi Utili

### Visualizzare i log

```bash
# Tutti i container
docker compose logs -f

# Solo backend
docker compose logs -f backend

# Solo frontend
docker compose logs -f frontend
```

### Riavviare un container

```bash
docker compose restart backend
docker compose restart frontend
```

### Ricostruire i container

```bash
docker compose up -d --build
```

### Stop e rimozione

```bash
# Stop
docker compose down

# Stop e rimozione volumi (ATTENZIONE: cancella i dati!)
docker compose down -v
```

### Accesso al container

```bash
# Backend
docker exec -it powermeter-backend /bin/bash

# Frontend
docker exec -it powermeter-frontend /bin/sh
```

## Troubleshooting

### Container non si avvia

1. Verifica che Docker Desktop sia in esecuzione
2. Controlla i log: `docker compose logs`
3. Verifica che le porte non siano già in uso

### Database non persiste

1. Verifica che la cartella `./data` esista e abbia i permessi corretti
2. Controlla i log del backend per errori di database

### Frontend non si connette al backend

1. Verifica che entrambi i container siano in esecuzione: `docker compose ps`
2. Controlla i log: `docker compose logs frontend backend`
3. Verifica la configurazione nginx

### Modbus non funziona

1. Verifica la configurazione della porta seriale in `.env`
2. Su Windows, potrebbe essere necessario configurare il mapping della porta COM
3. Controlla i log del backend per errori Modbus

### Porta già in uso

Modifica le porte in `docker-compose.yml`:

```yaml
ports:
  - "8080:80"  # Cambia 80 in 8080
```

## Sviluppo

Per sviluppo locale senza Docker, vedere il README principale.

## Note di Sicurezza

1. **Cambiare la password default** al primo utilizzo
2. **Modificare SECRET_KEY** in produzione
3. **Configurare il firewall** se l'applicazione è accessibile da LAN
4. **Backup regolari** della cartella `./data`

## Supporto

Per problemi o domande, consultare i log dei container o la documentazione del progetto.
