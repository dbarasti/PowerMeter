# Thermal Test System

Sistema per test termici su camion frigoriferi con acquisizione dati da power meter Eastron SDM120 via Modbus RTU.

## Caratteristiche

- **Acquisizione dati Modbus RTU**: Lettura periodica da 2 SDM120 (stufa e ventilatore)
- **Gestione sessioni di test**: Creazione, avvio, monitoraggio, esportazione
- **Web UI**: Interfaccia browser accessibile da LAN
- **Autenticazione**: Login con password (JWT)
- **Database SQLite**: Storage locale dei dati
- **Export CSV**: Download dati per analisi esterne

## Requisiti

- Python 3.11+
- Windows (testato su Windows)
- Adattatore USB-RS485 isolato
- 2 power meter Eastron SDM120 configurati con ID Modbus 1 e 2

## Installazione

1. Clona o scarica il progetto
2. Installa dipendenze:
```bash
pip install -r requirements.txt
```

3. Configura porta Modbus in `app/config.py`:
```python
MODBUS_CONFIG = {
    "port": "COM3",  # Modifica con la tua porta seriale
    ...
}
```

4. Avvia l'applicazione:
```bash
python -m app.main
```

5. Apri browser su `http://localhost:8000`
6. Login con:
   - Username: `admin`
   - Password: `admin` (CAMBIARE IN PRODUZIONE!)

## Struttura Progetto

```
app/
├── main.py                 # Entry point FastAPI
├── config.py               # Configurazione
├── modbus/
│   └── sdm120.py          # Driver Modbus RTU
├── services/
│   ├── acquisition.py     # Servizio acquisizione dati
│   ├── sessions.py        # Gestione sessioni
│   └── calculations.py    # Calcoli statistici
├── db/
│   ├── database.py        # Setup database
│   └── models.py          # Modelli SQLAlchemy
├── api/
│   ├── auth.py            # API autenticazione
│   ├── sessions.py        # API sessioni
│   └── data.py            # API dati/export
└── web/
    ├── templates/         # Template Jinja2
    └── static/            # CSS/JS
```

## Utilizzo

### Creare una nuova sessione di test

1. Clicca "Nuova Prova"
2. Compila:
   - Targa camion (obbligatorio)
   - Dimensioni cella (opzionale)
   - Durata prova in minuti
   - Frequenza campionamento in secondi (default: 5s)
   - Note (opzionale)

### Avviare acquisizione

1. Dalla lista sessioni, clicca "Avvia" su una sessione in stato IDLE
2. Il sistema inizia a leggere dati dai due SDM120
3. Lo stato passa a RUNNING

### Fermare acquisizione

1. Clicca "Ferma" su una sessione RUNNING
2. Lo stato passa a COMPLETED

### Esportare dati

1. Su una sessione COMPLETED, clicca "Esporta CSV"
2. Il file contiene: timestamp, device, power_w, energy_kwh

## Configurazione Modbus

I due SDM120 devono essere configurati con:
- **Stufa**: Slave ID = 1
- **Ventilatore**: Slave ID = 2

Porta seriale configurabile in `app/config.py` (default: COM3).

## Database

SQLite locale in `data/thermal_tests.db`. Le tabelle vengono create automaticamente al primo avvio.

## Sicurezza

- **Cambiare password default** al primo utilizzo
- Modificare `SECRET_KEY` in produzione (variabile d'ambiente o `config.py`)
- L'applicazione accetta connessioni da LAN (configurare firewall se necessario)

## Sviluppi Futuri

- Calcolo coefficiente K (placeholder già presente)
- Grafici live durante acquisizione
- Pagina dettaglio sessione con grafici storici
- Packaging come EXE Windows (PyInstaller)

## Note Tecniche

- **Thread-safe**: Un solo thread legge Modbus alla volta
- **Retry automatico**: 3 tentativi per ogni lettura Modbus
- **Robustezza**: Errori Modbus non bloccano l'applicazione
- **Sessioni persistenti**: JWT token valido 8 ore

## Troubleshooting

### Modbus non si connette
- Verifica porta seriale in `config.py`
- Controlla che l'adattatore USB-RS485 sia collegato
- Verifica ID Modbus degli SDM120 (1 e 2)

### Database errors
- Verifica permessi scrittura nella cartella `data/`
- Elimina `data/thermal_tests.db` per ricreare il database

### Porta già in uso
- Modifica `SERVER_CONFIG["port"]` in `config.py`

## Licenza

Uso interno aziendale.

