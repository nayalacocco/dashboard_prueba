import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
# scripts/fetch_datosar_catalog.py
from datosar_utils import build_catalog_and_allowlist

# Elegí palabras clave o dejá None para TODO
KEYWORDS = ["resultado", "financiero", "gasto", "ingreso", "ipc", "inflación", "precios"]

def main():
    print("[DatosAR] Construyendo catálogo…")
    cat, ids = build_catalog_and_allowlist(keywords=KEYWORDS)  # o keywords=None
    print(f"[DatosAR] Catálogo: {len(cat):,} filas | Allowlist: {len(ids):,} IDs")

if __name__ == "__main__":
    main()
