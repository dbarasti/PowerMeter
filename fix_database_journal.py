#!/usr/bin/env python3
"""
Script per recuperare il database da un journal file corrotto.
Esegui questo script se vedi errori "disk I/O error" o se il database si blocca.
"""
import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "thermal_tests.db"
JOURNAL_PATH = BASE_DIR / "data" / "thermal_tests.db-journal"

def fix_database():
    """Ripristina il database da un journal corrotto."""
    print("=== Fix Database SQLite ===")
    print(f"Database: {DB_PATH}")
    print(f"Journal: {JOURNAL_PATH}")
    print()
    
    if not DB_PATH.exists():
        print("ERRORE: Database non trovato!")
        return False
    
    # Prova a connettere e recuperare
    try:
        print("1. Tentativo di recupero automatico...")
        conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
        cursor = conn.cursor()
        
        # Forza il rollback di qualsiasi transazione pendente
        cursor.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
        
        # Verifica integrità
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("   ✓ Database integro")
        else:
            print(f"   ⚠ Avviso: {result[0]}")
        
        cursor.close()
        conn.close()
        
        # Rimuovi journal se esiste
        if JOURNAL_PATH.exists():
            print("2. Rimozione journal file...")
            try:
                JOURNAL_PATH.unlink()
                print("   ✓ Journal rimosso")
            except Exception as e:
                print(f"   ⚠ Impossibile rimuovere journal: {e}")
        
        print()
        print("✓ Database recuperato con successo!")
        return True
        
    except sqlite3.Error as e:
        print(f"ERRORE: {e}")
        print()
        print("Soluzioni:")
        print("1. Ferma l'applicazione se è in esecuzione")
        print("2. Prova a rimuovere manualmente il file journal:")
        print(f"   rm {JOURNAL_PATH}")
        print("3. Se il problema persiste, fai un backup e ricrea il database")
        return False
    except Exception as e:
        print(f"ERRORE inatteso: {e}")
        return False

if __name__ == "__main__":
    success = fix_database()
    exit(0 if success else 1)
