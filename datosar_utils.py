# datosar_utils.py
from __future__ import annotations
import json, os, io
from typing import List, Dict, Tuple, Optional
import pandas as pd
import requests

API_BASE = "https://apis.datos.gob.ar/series/api/series/"
DATA_DIR = "data"
ALLOWLIST = os.path.join(DATA_DIR, "datosar_allowlist.txt")
KEYWORDS = os.path.join(DATA_DIR, "datosar_keywords.txt")
META_PATH = os.path.join(DATA_DIR, "datosar_meta.json")
LONG_PATH = os.path.join(DATA_DIR, "datosar_long.parquet")

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def read_allowlist() -> List[str]:
    if not os.path.exists(ALLOWLIST): return []
    with open(ALLOWLIST, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

def read_keywords() -> List[str]:
    if not os.path.exists(KEYWORDS): 
        return ["resultado primario", "gasto total", "ingresos", "resultado financiero"]
    with open(KEYWORDS, "r", encoding="utf-8") as f:
        kws = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
    return kws or ["resultado primario", "gasto total", "ingresos", "resultado financiero"]

def search_series(term: str, limit: int = 20) -> List[Dict]:
    q = term.strip()
    url = f"{API_BASE}?q={requests.utils.quote(q)}&limit={int(limit)}&format=json"
    r = requests.get(url, timeout=30)
    if r.status_code != 200: return []
    data = r.json()
    # API devuelve una mezcla de resultados; si trae series directamente, perfecto.
    # La key "data" suele contener registros con "ids" o "id".
    items = []
    for row in data.get("data", []):
        # Normalizamos: algunos traen 'id' único, otros 'ids' (lista)
        if "id" in row:
            items.append(row)
        elif "ids" in row and row["ids"]:
            first = dict(row)
            first["id"] = row["ids"][0]
            items.append(first)
    return items

def fetch_one_series(series_id: str) -> Tuple[pd.DataFrame, Dict]:
    url = f"{API_BASE}?ids={requests.utils.quote(series_id)}&format=json"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    js = r.json()
    # Estructura típica: js["data"] = [[fecha, valor], ...]; js["meta"] con metadatos por id
    df = pd.DataFrame(js.get("data", []), columns=["fecha", series_id])
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)
    df.set_index("fecha", inplace=True)
    meta = js.get("meta", {}).get(series_id, {})
    return df, meta

def fetch_by_allowlist_or_keywords() -> Tuple[List[Dict], pd.DataFrame]:
    ids = read_allowlist()
    metas: List[Dict] = []
    dfs = []
    # Si no hay allowlist, vamos por keywords
    if not ids:
        for kw in read_keywords():
            results = search_series(kw, limit=15)
            # Elegimos 3 primeras series por keyword (heurística simple)
            for row in results[:3]:
                sid = row.get("id")
                if sid and sid not in ids:
                    ids.append(sid)

    if not ids:
        raise RuntimeError("No se encontraron series en la búsqueda (catálogo vacío).")

    for sid in ids:
        try:
            df, meta = fetch_one_series(sid)
            if not df.empty:
                dfs.append(df)
                metas.append({
                    "id": sid,
                    "title": meta.get("title") or meta.get("dataset_title") or sid,
                    "units": meta.get("units"),
                    "dataset_title": meta.get("dataset_title"),
                    "source": meta.get("source"),
                })
        except Exception:
            # seguimos con las demás
            continue

    if not dfs:
        raise RuntimeError("No pude descargar ninguna serie válida de DatosAR.")

    wide = pd.concat(dfs, axis=1).sort_index()
    return metas, wide

def fetch_datosar_to_disk() -> Tuple[List[Dict], pd.DataFrame]:
    _ensure_data_dir()
    metas, wide = fetch_by_allowlist_or_keywords()
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)
    # long
    long_rows = []
    for sid in wide.columns:
        s = wide[sid].dropna()
        long_rows.append(pd.DataFrame({"id": sid, "fecha": s.index, "valor": s.values}))
    long_df = pd.concat(long_rows, ignore_index=True)
    long_df.to_parquet(LONG_PATH, index=False)
    return metas, wide

def load_datosar_meta() -> List[Dict]:
    if not os.path.exists(META_PATH): return []
    with open(META_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_datosar_long() -> pd.DataFrame:
    if not os.path.exists(LONG_PATH):
        return pd.DataFrame(columns=["id", "fecha", "valor"])
    df = pd.read_parquet(LONG_PATH)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)
    return df
