#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descarga catálogo de la API Series de DatosAR (sin necesidad de conocer IDs en la UI).
- Construye data/datosar/catalog_index.json
- (Opcional) Prefetch de series "semilla" listadas en data/datosar/seed_ids.txt
"""

import os, json, time, sys, math
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

BASE = "https://apis.datos.gob.ar/series/api/series"
OUT_DIR = Path("data/datosar")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_FILE = OUT_DIR / "catalog_index.json"
SEED_FILE = OUT_DIR / "seed_ids.txt"
SERIES_DIR = OUT_DIR / "series"
SERIES_DIR.mkdir(parents=True, exist_ok=True)

# ------- Cómo filtramos al principio (ajustable sin tocar código) -------
DEFAULT_TERMS = [
    # Hacienda / MEcon / INDEC
    "resultado primario",
    "resultado financiero",
    "gasto total",
    "ingresos",
    "ingreso total",
    "inflación",
    "ipc",
]

# Intento de filtrar por organismo/tema desde metadata (si el endpoint lo expone):
ORG_HINTS = [
    "Ministerio de Economía", "Secretaría de Hacienda", "INDEC",
    "Tesoro", "Ministerio de Hacienda"
]

# ----------------------- Helpers HTTP -----------------------
def _get(url: str, params: Dict[str, Any], retries: int = 3, timeout=30) -> Dict[str, Any]:
    for i in range(retries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                pass
        time.sleep(1.2 * (i + 1))
    r.raise_for_status()
    return {}

# ----------------------- Catalog crawling -----------------------
def search_series(term: str, limit=1000, offset=0) -> Dict[str, Any]:
    """
    Usa la búsqueda del catálogo de Series. Según la instalación, la query suele ser 'q'.
    Dejamos metadata=full para poder filtrar y mostrar sin tocar el ID.
    """
    params = {
        "q": term,             # <- si tu instalación usa otro nombre (search=), cámbialo acá
        "limit": limit,
        "offset": offset,
        "metadata": "full",
    }
    return _get(BASE, params)

def normalize_hit(hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    A partir de un 'hit' de metadata full, creamos un registro compacto para el índice.
    Campos esperados: 'id', 'title', 'dataset', 'units', 'frequency', 'dataset_source', etc.
    Como cada despliegue puede variar, hacemos 'get' defensivo.
    """
    sid   = hit.get("id") or hit.get("serie_id") or hit.get("series_id")
    title = hit.get("title") or hit.get("description") or hit.get("dataset_title")
    freq  = hit.get("frequency") or hit.get("freq") or hit.get("periodicity")
    unit  = hit.get("units") or hit.get("unit") or hit.get("unit_label")
    org   = hit.get("dataset_source") or hit.get("publisher") or hit.get("dataset_publisher")
    topic = hit.get("dataset_theme") or hit.get("theme") or hit.get("topic")

    if not sid or not title:
        return None
    return {
        "id": sid,
        "title": title.strip(),
        "frequency": (freq or "").strip(),
        "unit": (unit or "").strip(),
        "org": (org or "").strip(),
        "topic": (topic or "").strip(),
    }

def build_catalog(terms: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    rows: List[Dict[str, Any]] = []
    for term in terms:
        offset = 0
        while True:
            payload = search_series(term, limit=1000, offset=offset)
            hits = payload.get("data") or payload.get("results") or payload.get("series") or []
            if not hits:
                break
            for h in hits:
                rec = normalize_hit(h)
                if not rec:
                    continue
                # Filtrado suave por organismo
                if ORG_HINTS and rec["org"]:
                    ok = any(hint.lower() in rec["org"].lower() for hint in ORG_HINTS)
                    if not ok:
                        # si no matchea org, igual dejamos pasar 10% para no perder gems
                        if (hash(rec["id"]) % 10) != 0:
                            continue
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                rows.append(rec)
            # paginado defensivo
            n = len(hits)
            if n < 1000:
                break
            offset += n
    # orden estable por org -> tema -> título
    rows.sort(key=lambda r: (r["org"].lower(), r["topic"].lower(), r["title"].lower()))
    return rows

# ----------------------- Series prefetch (opcional) -----------------------
def fetch_series_by_id(series_id: str) -> Optional[Dict[str, Any]]:
    """
    Trae una serie por ID y la guarda en CSV en data/datosar/series/<ID>.csv
    Según despliegue, el endpoint para datos suele ser el mismo con ?ids=<ID>.
    """
    params = {
        "ids": series_id,
        "format": "json"  # dejamos json, lo convertimos a CSV simple
    }
    payload = _get(BASE, params)
    data = payload.get("data") or payload.get("values") or payload.get("series")
    meta = payload.get("meta") or payload.get("metadata") or {}

    if not data:
        return None

    # normalizamos a una lista de [fecha, valor]
    # muchos despliegues devuelven: {"data":[["2020-01-01", 123.4], ...]}
    out_csv = SERIES_DIR / f"{series_id}.csv"
    with out_csv.open("w", encoding="utf-8") as f:
        f.write("fecha,valor\n")
        for row in data:
            # si vienen dicts, adaptamos
            if isinstance(row, dict):
                fecha = row.get("index") or row.get("fecha") or row.get("date")
                valor = row.get("value") or row.get("valor") or row.get("y")
            else:
                # asumimos [fecha, valor]
                try:
                    fecha, valor = row[0], row[1]
                except Exception:
                    continue
            if fecha is None or valor is None:
                continue
            f.write(f"{fecha},{valor}\n")

    # también guardamos un pequeño sidecar con título para debug/inspección
    title = None
    if isinstance(meta, list) and meta:
        title = meta[0].get("title")
    elif isinstance(meta, dict):
        title = meta.get("title")
    info = {"id": series_id, "title": title}
    with (SERIES_DIR / f"{series_id}.json").open("w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info

def main():
    terms = DEFAULT_TERMS[:]
    if len(sys.argv) > 1:
        # permitir override: python fetch_datosar_catalog.py "resultado primario" "gasto"
        terms = sys.argv[1:]

    print(f"[DatosAR] Construyendo catálogo para términos: {terms}")
    rows = build_catalog(terms)
    with CATALOG_FILE.open("w", encoding="utf-8") as f:
        json.dump({"built_at": time.time(), "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"[DatosAR] Catálogo listo: {CATALOG_FILE} ({len(rows)} series)")

    # Prefetch opcional
    if SEED_FILE.exists():
        seeds = [s.strip() for s in SEED_FILE.read_text(encoding="utf-8").splitlines() if s.strip() and not s.strip().startswith("#")]
        if seeds:
            print(f"[DatosAR] Prefetch de {len(seeds)} series (semillas)…")
            for sid in seeds:
                try:
                    info = fetch_series_by_id(sid)
                    if info:
                        print(f"  - {sid} ✓ {info.get('title') or ''}")
                    else:
                        print(f"  - {sid} ✗ no encontrada")
                except Exception as e:
                    print(f"  - {sid} ✗ error: {e}")
    print("[DatosAR] Done.")

if __name__ == "__main__":
    main()
