# scripts/fetch_datosar.py
from datosar_utils import fetch_datosar_to_disk, read_allowlist

if __name__ == "__main__":
    ids = read_allowlist()
    if not ids:
        print("⚠️ data/datosar_allowlist.txt vacío. Agregá IDs (uno por línea).")
    fetch_datosar_to_disk(ids or None)
