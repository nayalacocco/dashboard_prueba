# -*- coding: utf-8 -*-
"""
Utilidades para Datos Argentina (Series-tiempo).
Lectura del catálogo local + descarga de series por id.
"""

import os, json
from typing import List
import pandas as pd
import requests

CAT_PARQUET = "data/datosar_catalog.parquet"
IDX_JSON = "data/datosar_index.json"
BASE_SERIES = "https://apis.datos.gob.ar/series/api/series"

def load_catalog() -> pd.DataFrame:
    if not os.path.exists(CAT_PARQUET):
        raise FileNotFoundError("Falta data/datosar_catalog.parquet (corré scripts/fetch_datosar_catalog.py).")
    return pd.read_parquet(CAT_PARQUET)

def load_index() -> dict:
    if not os.path.exists(IDX_JSON):
        raise FileNotFoundError("Falta data/datosar_index.json (corré scripts/fetch_datosar_catalog.py).")
    with open(IDX_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_series(ids: List[str]) -> pd.DataFrame:
    """
    Devuelve un wide DataFrame con index 'fecha' y columnas por cada id pedido.
    """
    if not ids:
        return pd.DataFrame()
    params = {
        "ids": ",".join(ids),
        "format": "json",
    }
    r = requests.get(BASE_SERIES, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    # Estructura usual: {"data": [[ts, v1, v2...], ...], "columns": [{"name":"indice_tiempo"}, {"name": id1}, ...]}
    cols = [c.get("name") for c in payload.get("columns", [])]
    data = payload.get("data", [])
    if not data or not cols or cols[0] not in ("indice_tiempo", "fecha"):
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=cols)
    df = df.rename(columns={"indice_tiempo": "fecha"})
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha").sort_index()
    return df
