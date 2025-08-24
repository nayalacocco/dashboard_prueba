# scripts/fetch_datosar_catalog.py
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from typing import List
from datosar_utils import build_catalog_and_allowlist

RAW_DIR = "data/raw"
CATALOG_META_OUT = "data/datosar_catalog_meta.parquet"
ALLOWLIST_OUT     = "data/datosar_allowlist.txt"
KEYWORDS_TXT      = "data/datosar_keywords.txt"

def _read_keywords(path: str) -> List[str] | None:
    p = Path(path)
    if not p.exists():
        return None
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
    kw = [x for x in lines if x]
    return kw or None

def main():
    print("[DatosAR] Construyendo catálogo…")
    keywords = _read_keywords(KEYWORDS_TXT)
    cat, ids = build_catalog_and_allowlist(RAW_DIR, CATALOG_META_OUT, keywords=keywords)
    # guardo allowlist plano (uno por línea)
    Path(ALLOWLIST_OUT).write_text("\n".join(ids), encoding="utf-8")
    print(f"[DatosAR] Catálogo: {len(cat):,} filas | Allowlist: {len(ids):,} ids")
    print(f"         -> {CATALOG_META_OUT}")
    print(f"         -> {ALLOWLIST_OUT}")

if __name__ == "__main__":
    main()
