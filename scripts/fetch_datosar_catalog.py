#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construye el catálogo local de series de Datos Argentina.
1) Intenta usar /series/api/series/available (si está disponible).
2) Si no, recurre a CKAN /api/3/action/package_search para datasets de INDEC / MEcon / Hacienda
   y extrae los IDs de series desde los metadatos de distributions (cuando están).
Guarda:
- data/datosar_catalog.parquet   (tabla con metadatos)
- data/datosar_index.json        (dict {id: etiqueta limpia})
"""

import os, sys, json, time, re
from typing import List, Dict, Any
import requests
import pandas as pd

BASE_SERIES_AVAILABLE = "https://apis.datos.gob.ar/series/api/series/available"
BASE_CKAN_SEARCH = "https://datos.gob.ar/api/3/action/package_search"

OUT_DIR = "data"
CAT_PARQUET = os.path.join(OUT_DIR, "datosar_catalog.parquet")
IDX_JSON = os.path.join(OUT_DIR, "datosar_index.json")

os.makedirs(OUT_DIR, exist_ok=True)

SEED_ORGS = [
    # org id en CKAN (con espacios es mejor usar fq=organization:*texto*)
    "indec",
    "ministerio-de-economia",
    "secretaria-de-hacienda",
    "tesoro",
    "ministerio-de-economia-de-la-nacion",
]

def _clean_label(s: str) -> str:
    s = s or ""
    s = re.sub(r"\s*\(en\s*%.*?\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(en\s*millones.*?\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(expresado.*?\)", "", s, flags=re.I)
    s = re.sub(r"\s*–\s*", " - ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def try_available_endpoint(limit=5000) -> pd.DataFrame:
    """
    Intenta listar TODAS las series desde /series/available con paginado.
    Devuelve DF con columnas: id, title, dataset, source, frequency (si existen).
    """
    rows: List[Dict[str, Any]] = []
    offset = 0
    step = 1000
    while True:
        params = {"format": "json", "limit": step, "offset": offset}
        r = requests.get(BASE_SERIES_AVAILABLE, params=params, timeout=60)
        if r.status_code >= 400:
            # No existe o está deshabilitado => devolvemos vacío
            return pd.DataFrame()
        data = r.json()
        # el payload habitual trae "data" o lista directa
        items = data.get("data") or data.get("results") or data
        if not isinstance(items, list) or len(items) == 0:
            break
        for it in items:
            rid = it.get("id") or it.get("series_id")
            if not rid:
                continue
            rows.append({
                "id": rid,
                "title": it.get("title") or it.get("description") or rid,
                "dataset": it.get("dataset") or it.get("dataset_title") or "",
                "source": it.get("source") or it.get("publisher") or "",
                "frequency": it.get("frequency") or it.get("freq") or "",
            })
        offset += step
        if len(items) < step or len(rows) >= limit:
            break
        time.sleep(0.2)
    return pd.DataFrame(rows).drop_duplicates("id")

def ckan_search_all(limit=1000) -> pd.DataFrame:
    """
    Barrido general en CKAN: busca todos los datasets y filtra resources que apunten a /series/api/series.
    """
    rows = []
    start = 0
    step = 100
    while True:
        params = {"q": "", "rows": step, "start": start}
        r = requests.get(BASE_CKAN_SEARCH, params=params, timeout=60)
        if r.status_code >= 400:
            break
        payload = r.json()
        result = payload.get("result", {})
        datasets = result.get("results", [])
        if not datasets:
            break
        for ds in datasets:
            ds_title = ds.get("title") or ""
            org_title = (ds.get("organization") or {}).get("title") or ""
            for res in ds.get("resources", []):
                url = res.get("url") or ""
                if "series/api/series?ids=" in url:
                    sid = url.split("ids=")[1].split("&")[0]
                    rows.append({
                        "id": sid,
                        "title": res.get("name") or ds_title or sid,
                        "dataset": ds_title,
                        "source": org_title,
                        "frequency": res.get("frequency") or "",
                    })
        start += step
        if start >= (result.get("count") or 0) or len(rows) >= limit:
            break
        time.sleep(0.2)
    return pd.DataFrame(rows).drop_duplicates("id")

def main():
    print("[DatosAR] Construyendo catálogo…")
    df = try_available_endpoint()
    if df.empty:
        print(" - Endpoint /series/available no respondió; usando CKAN fallback…")
        df = ckan_search_all()
    if df.empty:
        raise RuntimeError("No pude construir el catálogo de DatosAR (sin filas).")

    # Limpieza y etiqueta amigable
    df["label"] = df.apply(
        lambda r: _clean_label(f'{r.get("title") or ""}').strip() or r["id"],
        axis=1,
    )

    # Guardados
    df = df[["id", "label", "title", "dataset", "source", "frequency"]].drop_duplicates("id")
    df.to_parquet(CAT_PARQUET, index=False)
    idx = {row["id"]: row["label"] for _, row in df.iterrows()}
    with open(IDX_JSON, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

    print(f"✓ Catálogo: {len(df):,} series → {CAT_PARQUET}")
    print(f"✓ Index    : {len(idx):,} ids    → {IDX_JSON}")

if __name__ == "__main__":
    main()
