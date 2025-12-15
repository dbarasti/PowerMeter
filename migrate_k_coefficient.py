"""
Script di migrazione per aggiornare la tabella k_coefficients.
Aggiunge i nuovi campi per il calcolo del coefficiente U.
"""
import sqlite3
import os
from pathlib import Path

# Path database
db_path = Path("data/thermal_tests.db")

if not db_path.exists():
    print(f"Database non trovato: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("Aggiornamento tabella k_coefficients...")

try:
    # Verifica quali colonne esistono già
    cursor.execute("PRAGMA table_info(k_coefficients)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"Colonne esistenti: {existing_columns}")

    # Aggiungi nuove colonne se non esistono
    new_columns = [
        ("temp_internal_avg", "FLOAT NOT NULL DEFAULT 0"),
        ("temp_external_avg", "FLOAT NOT NULL DEFAULT 0"),
        ("equivalent_surface_m2", "FLOAT"),
        ("avg_power_w", "FLOAT"),
        ("delta_t", "FLOAT"),
        ("u_value", "FLOAT"),
    ]

    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            print(f"  Aggiungo colonna: {col_name}")
            cursor.execute(
                f"ALTER TABLE k_coefficients ADD COLUMN {col_name} {col_def}"
            )
        else:
            print(f"  Colonna già esistente: {col_name}")

    # Aggiorna calculation_method default se necessario
    cursor.execute(
        "UPDATE k_coefficients SET calculation_method = 'geometric_mean' "
        "WHERE calculation_method IS NULL"
    )

    conn.commit()
    print("✓ Migrazione completata con successo!")

except sqlite3.Error as e:
    print(f"✗ Errore durante la migrazione: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()

