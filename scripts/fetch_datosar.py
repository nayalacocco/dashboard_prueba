# scripts/fetch_datosar.py
from datosar_utils import read_allowlist, fetch_datosar_to_disk, load_datosar_long

if __name__ == "__main__":
    ids = read_allowlist()
    if not ids:
        print("No hay IDs en data/datosar_allowlist.txt. Cargá desde la app o agregá a mano.")
    else:
        print(f"Descargando {len(ids)} series…")
        fetch_datosar_to_disk(ids)

    df = load_datosar_long()
    print(df.head())
    print(f"Series: {df['id'].nunique()}  |  Filas: {len(df):,}")
