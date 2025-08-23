# scripts/fetch_datosar.py
from __future__ import annotations
import os
from datosar_utils import (
    read_allowlist, upsert_allowlist, fetch_datosar_to_disk, load_datosar_long
)

def main():
    # Opcional: permitir pasar IDs por variable de entorno (coma-separados)
    env_ids = os.getenv("DATOSAR_IDS", "").strip()
    ids_from_env = [x.strip() for x in env_ids.split(",") if x.strip()]

    # Si vienen por ENV, los agrego a la allowlist
    if ids_from_env:
        print(f"Agregando {len(ids_from_env)} IDs desde DATOSAR_IDS…")
        upsert_allowlist(ids_from_env)

    ids = read_allowlist()  # lee (o crea) data/datosar_allowlist.txt
    if not ids:
        print("No hay IDs en data/datosar_allowlist.txt y no se pasaron por DATOSAR_IDS. Nada para bajar.")
        return

    print(f"Descargando {len(ids)} series…")
    fetch_datosar_to_disk(ids)

    df = load_datosar_long()
    print(df.head())
    print(f"Series: {df['id'].nunique()}  |  Filas: {len(df):,}")

if __name__ == "__main__":
    main()
