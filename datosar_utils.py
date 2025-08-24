# datosar_utils.py
from __future__ import annotations

import csv
import json
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import pandas as pd
import requests


# ---------- Config ----------
BASE_SERIES_API = "https://apis.datos.gob.ar/series/api/series"
RAW_DIR = "data/raw"
CATALOG_META_OUT = "data/datosar_catalog_meta.parquet"
ALLOWLIST_OUT = "data/datosar_allowlist.txt"
LONG_OUT = "data/datosar_long.parquet"
LOG_PATH = "data/datosar_fetch_log.ndjson"

# Límite blando de columnas por request (la API soporta varios IDs por llamada)
BATCH_COLS = 6

# Map flexible de columnas -> nombres estandarizados
_COL_ALIASES = {
    "id": ["id", "serie_id", "identificador", "serie"],
    "name": ["title", "titulo", "series_title", "serie_titulo", "nombre", "name"],
    "dataset": ["dataset_title", "dataset", "conjunto", "origen", "dataset_nombre"],
    "units": ["units", "unit", "unidad", "unidades", "scale"],
    "frequency": ["frequency", "frecuencia"],
}


def _first_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    cols = [c for c in df.columns]
    lower = {c.lower(): c for c in cols}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DataFrame con columnas normalizadas: id, name, dataset, units, frequency."""
    colmap = {}
    for std, cand in _COL_ALIASES.items():
        col = _first_col(df, [x.lower() for x in cand])
        if col:
            colmap[std] = col

    out = pd.DataFrame()
    for k in ["id", "name", "dataset", "units", "frequency"]:
        if k in colmap:
            out[k] = df[colmap[k]].astype(str).str.strip()
        else:
            out[k] = None
    # Fallbacks mínimos
    if out["name"].isna().all():
        out["name"] = out["id"]
    if out["dataset"].isna().all():
        out["dataset"] = "Sin grupo"
    return out.dropna(subset=["id"]).drop_duplicates(subset=["id"]).reset_index(drop=True)


def load_metadata_csvs(raw_dir: str = RAW_DIR) -> pd.DataFrame:
    """Lee todos los CSVs de `data/raw/series-tiempo-metadatos-*.csv` y los une."""
    import glob

    paths = sorted(glob.glob(os.path.join(raw_dir, "series-tiempo-metadatos-*.csv")))
    if not paths:
        raise FileNotFoundError(
            f"No encontré CSVs en {raw_dir}/series-tiempo-metadatos-*.csv"
        )

    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p, dtype=str, engine="python", on_bad_lines="skip")
        except UnicodeDecodeError:
            df = pd.read_csv(p, encoding="latin-1")
        df = _map_columns(df)
        df["source_file"] = os.path.basename(p)
        frames.append(df)

    cat = pd.concat(frames, ignore_index=True)
    # Limpieza básica
    cat["id"] = cat["id"].str.strip()
    cat = cat[cat["id"].str.len() > 0].drop_duplicates("id")
    # “Grupo”: nos quedamos con el dataset/origen corto
    cat["group"] = (
        cat["dataset"]
        .fillna("Sin grupo")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return cat[["id", "name", "group", "units", "frequency", "source_file"]]


def build_catalog_from_raw(raw_dir: str = RAW_DIR, out_path: str = CATALOG_META_OUT) -> pd.DataFrame:
    """Construye catálogo normalizado desde CSVs locales y guarda parquet."""
    cat = load_metadata_csvs(raw_dir)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cat.to_parquet(out_path, index=False)
    return cat


def build_allowlist(cat: pd.DataFrame, out_path: str = ALLOWLIST_OUT, keywords: Iterable[str] | None = None) -> List[str]:
    """
    Genera allowlist de IDs.
    - Si `keywords` se provee, filtra por esas palabras en name o group (case-insensitive).
    - Si no, usa TODO el catálogo (ojo tamaño).
    """
    if keywords:
        pat = "|".join([re.escape(k) for k in keywords if k.strip()])
        mask = (cat["name"].str.contains(pat, case=False, na=False)) | (
            cat["group"].str.contains(pat, case=False, na=False)
        )
        sub = cat[mask].copy()
    else:
        sub = cat.copy()

    ids = sorted(sub["id"].unique().tolist())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for i in ids:
            f.write(i + "\n")
    return ids


def _chunked(xs: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def _log_event(obj: dict):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def fetch_series_batch(ids: List[str]) -> Tuple[pd.DataFrame, dict]:
    """
    Llama a la API de series por un grupo de IDs. Devuelve (df_long, meta_json_bruto).
    La API devuelve:
      - "data": matriz de valores
      - "index": fechas
      - "series": metadatos por columna
    """
    params = {
        "ids": ",".join(ids),
        "format": "json",
        "metadata": "full",
    }
    r = requests.get(BASE_SERIES_API, params=params, timeout=60)
    r.raise_for_status()
    js = r.json()

    data = js.get("data", [])
    index = js.get("index", [])
    series_meta = js.get("series", [])  # lista de dicts (una por columna)

    if not data or not index or not series_meta:
        return pd.DataFrame(), js

    # data: lista de filas; la trasponemos a columnas por ID
    df = pd.DataFrame(data, index=pd.to_datetime(index))
    # A veces vienen más columnas que metadatos (o viceversa). Cortamos al mínimo común.
    n_cols = min(df.shape[1], len(series_meta))
    df = df.iloc[:, :n_cols]
    series_meta = series_meta[:n_cols]

    # Armamos en largo
    long_frames = []
    for i, meta in enumerate(series_meta):
        sid = meta.get("id") or meta.get("serie_id") or f"col_{i}"
        s = df.iloc[:, i]
        tmp = pd.DataFrame(
            {
                "fecha": s.index,
                "id": sid,
                "valor": pd.to_numeric(s.values, errors="coerce"),
            }
        )
        long_frames.append(tmp)

    long_df = pd.concat(long_frames, ignore_index=True)
    long_df = long_df.dropna(subset=["valor"])
    return long_df, js


def fetch_ids_to_long(ids: List[str]) -> pd.DataFrame:
    """Descarga todas las IDs en batches y devuelve un DF largo unido."""
    frames = []
    done = 0
    for batch in _chunked(ids, BATCH_COLS):
        try:
            long_df, meta = fetch_series_batch(batch)
            frames.append(long_df)
            _log_event({"ok": True, "batch": batch, "rows": len(long_df)})
        except Exception as e:
            _log_event({"ok": False, "batch": batch, "error": str(e)})
        # gentil con la API
        done += len(batch)
        time.sleep(0.5 if done < 50 else 1.0)

    if not frames:
        return pd.DataFrame(columns=["fecha", "id", "valor"])
    df = pd.concat(frames, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def attach_labels(df_long: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    """Enriquece el largo con `descripcion` (label), `group`, `units`."""
    lab = catalog[["id", "name", "group", "units"]].drop_duplicates("id")
    out = df_long.merge(lab, on="id", how="left")
    out = out.rename(columns={"name": "descripcion"})
    return out[["fecha", "id", "descripcion", "group", "units", "valor"]]


# ---------- Orquestadores  ----------

def build_catalog_and_allowlist(
    raw_dir: str = RAW_DIR,
    out_catalog: str = CATALOG_META_OUT,
    out_allowlist: str = ALLOWLIST_OUT,
    keywords: Iterable[str] | None = None,
) -> Tuple[pd.DataFrame, List[str]]:
    cat = build_catalog_from_raw(raw_dir, out_catalog)
    ids = build_allowlist(cat, out_allowlist, keywords=keywords)
    return cat, ids


def fetch_all_and_save(
    ids: List[str],
    catalog: pd.DataFrame,
    out_long: str = LONG_OUT,
) -> pd.DataFrame:
    long_df = fetch_ids_to_long(ids)
    long_df = attach_labels(long_df, catalog)
    os.makedirs(os.path.dirname(out_long), exist_ok=True)
    long_df.to_parquet(out_long, index=False)
    return long_df
