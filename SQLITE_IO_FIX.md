# Fix Errori I/O SQLite

## Problema

Gli errori "disk I/O error" di SQLite possono essere causati da:
1. **Latenza I/O** sui volumi montati (Docker) o filesystem lenti
2. **Lock del database** durante scritture concorrenti
3. **Problemi di sincronizzazione** del filesystem
4. **Journal file corrotto** (transazione non completata)
5. **Freeze del backend** quando un commit fallisce

## Soluzioni Implementate

### 1. Configurazione SQLite Robusta (`app/db/database.py`)

- **Timeout per lock**: 30 secondi (evita deadlock)
- **Cache size**: 64MB (riduce I/O)
- **Synchronous mode**: NORMAL (compromesso sicurezza/performance)
- **Journal mode**: DELETE (più sicuro per volumi montati rispetto a WAL)
- **Pool pre-ping**: Verifica connessioni prima di usarle

### 2. Retry Logic con Backoff (`app/services/acquisition.py`)

Il metodo `_save_measurement` ora:
- **Riprova fino a 3 volte** in caso di errore I/O
- **Backoff esponenziale**: attesa crescente tra tentativi (0.5s, 1s, 1.5s)
- **Ricrea la sessione** dopo ogni errore per evitare sessioni corrotte
- **Non blocca il loop** di acquisizione se il salvataggio fallisce

### 3. Gestione Errori Migliorata

- **Distinzione** tra errori I/O temporanei e errori permanenti
- **Rollback automatico** in caso di errore
- **Logging dettagliato** per debugging
- **Recovery automatico** della sessione database

## Recovery Database

Se vedi un file `thermal_tests.db-journal`, significa che c'è una transazione non completata:

```bash
# Esegui lo script di recovery
python fix_database_journal.py
```

Oppure manualmente:
```bash
# Ferma l'applicazione
# Rimuovi il journal
rm data/thermal_tests.db-journal
```

## Configurazione Docker (se usi Docker)

Per migliorare ulteriormente le performance I/O, considera:

### Opzione 1: Volume Named (più veloce)
```yaml
volumes:
  - database-data:/app/data

volumes:
  database-data:
```

### Opzione 2: Bind Mount con Cached (Windows)
```yaml
volumes:
  - ./data:/app/data:cached
```

### Opzione 3: Database su Volume Docker
Crea un volume Docker invece di bind mount per migliori performance.

## Verifica

Dopo il fix, verifica:

1. **Log errori**: Dovrebbero essere meno frequenti
2. **Retry automatico**: Gli errori I/O vengono ritentati
3. **Backend non si blocca**: Il loop di acquisizione continua anche con errori

## Monitoraggio

Controlla i log per:
- `"Errore I/O database (tentativo X/3)"` - Retry in corso
- `"Misura salvata"` - Successo
- `"Errore salvataggio misura"` - Fallimento dopo tutti i tentativi

## Note Importanti

- **Non perdere dati**: Se un salvataggio fallisce, viene loggato ma l'acquisizione continua
- **Performance**: Il retry aggiunge latenza ma previene perdite di dati
- **Database**: Il database viene automaticamente recuperato dopo errori

## Troubleshooting

Se gli errori persistono:

1. **Verifica permessi** sulla cartella `./data`
2. **Controlla spazio disco** disponibile
3. **Usa volume Docker** invece di bind mount
4. **Riduci frequenza** di acquisizione (aumenta `sample_rate_seconds`)
5. **Verifica antivirus** che non blocchi accessi al database
