# datosar_utils.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import requests

BASE = "https://apis.datos.gob.ar/series/api/series"
DATA_DIR = Path("data/datosar")
CATALOG_FILE = DATA_DIR / "catalog_index.json"
SERIES_DIR = DATA_DIR / "series"
SERIES_DIR.mkdir(parents=True, exist_ok=True)

def load_catalog() -> pd.DataFrame:
    if not CATALOG_FILE.exists():
        return pd.DataFrame(columns=["id","title","frequency","unit","org","topic"])
    js = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    rows = js.get("rows", [])
    return pd.DataFrame(rows)

def _download_series_to_cache(series_id: str) -> Optional[Path]:
    params = {"ids": series_id, "format": "json"}
    r = requests.get(BASE, params=params, timeout=40)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") or payload.get("values") or payload.get("series")
    if not data:
        return None
    out_csv = SERIES_DIR / f"{series_id}.csv"
    with out_csv.open("w", encoding="utf-8") as f:
        f.write("fecha,valor\n")
        for row in data:
            if isinstance(row, dict):
                fecha = row.get("index") or row.get("fecha") or row.get("date")
                valor = row.get("value") or row.get("valor") or row.get("y")
            else:
                try:
                    fecha, valor = row[0], row[1]
                except Exception:
                    continue
            if fecha is None or valor is None:
                continue
            f.write(f"{fecha},{valor}\n")
    return out_csv

def load_series(series_id: str) -> pd.Series:
    """
    Carga una serie (fecha, valor) desde cache CSV; si no existe, intenta bajarla una vez.
    Devuelve pd.Series indexada por fecha (DatetimeIndex) con dtype float.
    """
    csv_path = SERIES_DIR / f"{series_id}.csv"
    if not csv_path.exists():
        csv_path = _download_series_to_cache(series_id) or csv_path
    if not csv_path.exists():
        # serie no disponible
        return pd.Series(dtype=float)

    df = pd.read_csv(csv_path)
    if "fecha" not in df.columns or "valor" not in df.columns:
        return pd.Series(dtype=float)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")
    s = pd.Series(df["valor"].astype(float).values, index=df["fecha"])
    s.name = series_id
    return s
