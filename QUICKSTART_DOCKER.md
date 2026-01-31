# Quick Start Docker - PowerMeter

## Avvio Rapido (Windows)

1. **Installa Docker Desktop** (se non già installato)
   - https://www.docker.com/products/docker-desktop
   - Avvia Docker Desktop

2. **Doppio click su `start.bat`**

3. **Apri il browser su: http://localhost**

4. **Login con:**
   - Username: `admin`
   - Password: `admin` (cambia al primo utilizzo!)

## File Creati

- `Dockerfile.backend` - Immagine Docker per backend FastAPI
- `Dockerfile.frontend` - Immagine Docker per frontend SvelteKit
- `docker-compose.yml` - Configurazione completa del progetto
- `nginx.conf` - Reverse proxy per routing unificato
- `.dockerignore` - File esclusi dal build
- `start.bat` - Script di avvio Windows
- `stop.bat` - Script di stop Windows
- `env.example.txt` - Template configurazione (rinominare in `.env`)

## Persistenza Dati

Il database SQLite è salvato in `./data/thermal_tests.db` e persiste anche dopo lo stop dei container.

## Comandi Utili

```bash
# Visualizza log
docker compose logs -f

# Stop
docker compose down

# Riavvio
docker compose restart
```

Per maggiori dettagli, vedere `DOCKER_README.md`.
