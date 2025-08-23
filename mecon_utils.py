# mecon_utils.py
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import datetime as dt

import pandas as pd
import requests

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_JSON = DATA_DIR / "mecon_catalog.json"
LONG_PARQUET = DATA_DIR / "mecon_long.parquet"

# -------------------------------
# Helpers
# -------------------------------
def _load_catalog() -> List[Dict]:
    if CATALOG_JSON.exists():
        with open(CATALOG_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_catalog(rows: List[Dict]) -> None:
    with open(CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

def _ensure_long_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizamos columnas a: fecha, valor, descripcion, fuente, unidad (opc)"""
    cols = {
        "date": "fecha", "fecha": "fecha",
        "value": "valor", "valor": "valor",
        "descripcion": "descripcion", "description": "descripcion",
        "fuente": "fuente", "source": "fuente",
        "unidad": "unidad", "unit": "unidad",
    }
    df = df.rename(columns={c: cols.get(c, c) for c in df.columns})
    out_cols = ["fecha", "valor", "descripcion", "fuente", "unidad"]
    for c in out_cols:
        if c not in df.columns:
            df[c] = None
    df = df[out_cols].copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values("fecha")

# -------------------------------
# Descarga desde datos.gob.ar/series
# (API genérica del GCBA/INDEC/MECON – requiere el ID de la serie)
# -------------------------------
DATOS_API = "https://apis.datos.gob.ar/series/api/series"

def _fetch_datos_gobar_series(series_id: str) -> pd.DataFrame:
    """
    Trae una serie por ID desde apis.datos.gob.ar/series.
    Retorna DF con columnas: fecha, valor.
    """
    params = {
        "ids": series_id,
        "format": "json",
    }
    r = requests.get(DATOS_API, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    # Estructura: { "data": [[ts,value], ...], "meta": { "names": {id: label}, "units": {...} } }
    data = js.get("data", [])
    if not data:
        return pd.DataFrame(columns=["fecha", "valor"])

    df = pd.DataFrame(data, columns=["fecha", "valor"])
    # fecha viene como ISO (yyyy-mm-dd) o yyyy-mm; dejamos date
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    # Intentamos nombre/unidad
    names = js.get("meta", {}).get("names", {})
    units = js.get("meta", {}).get("units", {})
    desc = names.get(series_id, series_id)
    unit = units.get(series_id, None)

    df["descripcion"] = desc
    df["fuente"] = "MECON / datos.gob.ar"
    df["unidad"] = unit
    return _ensure_long_schema(df)

# -------------------------------
# API pública del módulo
# -------------------------------
def add_series_to_catalog(label: str, series_id: str, provider: str = "datos_gobar", unidad: str | None = None) -> None:
    """
    Agrega una entrada al catálogo local (para persistir qué serie traer).
    provider: por ahora solo 'datos_gobar' (apis.datos.gob.ar/series)
    """
    rows = _load_catalog()
    rows = [r for r in rows if not (r.get("id")==series_id and r.get("provider")==provider)]
    rows.append({
        "label": label,
        "id": series_id,
        "provider": provider,
        "unidad": unidad,
        "added_at": dt.datetime.utcnow().isoformat()+"Z",
    })
    _save_catalog(rows)

def fetch_mecon_to_disk() -> pd.DataFrame:
    """
    Recorre el catálogo local, baja cada serie, concatena y guarda en parquet largo.
    """
    cat = _load_catalog()
    if not cat:
        # devolvemos DF vacío con esquema esperado
        empty = pd.DataFrame(columns=["fecha","valor","descripcion","fuente","unidad"])
        empty.to_parquet(LONG_PARQUET, index=False)
        return empty

    frames = []
    for row in cat:
        prov = row.get("provider","datos_gobar")
        sid  = row["id"]
        label_override = row.get("label")
        unidad = row.get("unidad")

        if prov == "datos_gobar":
            df = _fetch_datos_gobar_series(sid)
        else:
            # futuro: otros providers
            df = pd.DataFrame(columns=["fecha","valor","descripcion","fuente","unidad"])

        if label_override:
            df["descripcion"] = label_override
        if unidad is not None:
            df["unidad"] = unidad

        frames.append(df)

    long_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["fecha","valor","descripcion","fuente","unidad"])
    long_df = _ensure_long_schema(long_df)
    long_df.to_parquet(LONG_PARQUET, index=False)
    return long_df

def load_mecon_long() -> pd.DataFrame:
    """
    Carga el largo consolidado; si no existe intenta construirlo desde el catálogo.
    """
    if LONG_PARQUET.exists():
        try:
            df = pd.read_parquet(LONG_PARQUET)
            return _ensure_long_schema(df)
        except Exception:
            pass
    return fetch_mecon_to_disk()
