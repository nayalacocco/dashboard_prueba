# --- ensure repo root is importable ---
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# scripts/fetch_datosar.py
from datosar_utils import fetch_datosar_to_disk, load_datosar_long

if __name__ == "__main__":
    metas, wide = fetch_datosar_to_disk()
    print(f"Guardé {len(metas)} metadatos y {wide.shape[1]} series (anchas).")
    print(load_datosar_long().head())
