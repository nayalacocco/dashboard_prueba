# datosar_utils.py
from __future__ import annotations
import os
import io
import json
import time
import math
import pathlib
from typing import List, Dict, Tuple, Optional

import pandas as pd
import requests

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_PATH = DATA_DIR / "datosar_long.parquet"
ALLOWLIST_PATH = DATA_DIR / "datosar_allowlist.txt"

# -----------------------------
# Presets curados (MEcon/Hacienda)
# -----------------------------
# IDs típicos de Hacienda (serie mensual, millones de $ corrientes):
# NOTA: estos IDs funcionan en el endpoint /series?ids=...
DATOSAR_PRESETS: Dict[str, List[Dict[str, str]]] = {
    "Finanzas públicas (Hacienda)": [
        {
            "id": "sspm_resultado_primario_mensual",
            "label": "Resultado primario (Nación) - mensual",
            "hint": "Ingresos totales - Gasto primario",
        },
        {
            "id": "sspm_resultado_financiero_mensual",
            "label": "Resultado financiero (Nación) - mensual",
            "hint": "Primario - Intereses",
        },
        {
            "id": "sspm_ingresos_totales_mensual",
            "label": "Ingresos totales - mensual",
            "hint": "Recaudación + otros",
        },
        {
            "id": "sspm_gasto_total_mensual",
            "label": "Gasto total - mensual",
            "hint": "Gasto primario + intereses",
        },
        {
            "id": "sspm_gasto_primario_mensual",
            "label": "Gasto primario - mensual",
            "hint": "Sin intereses",
        },
    ],
}

# -----------------------------
# I/O allowlist
# -----------------------------
def read_allowlist() -> List[str]:
    if not ALLOWLIST_PATH.exists():
        return []
    ids = []
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            ids.append(s)
    return sorted(set(ids))

def upsert_allowlist(new_ids: List[str]) -> None:
    current = set(read_allowlist())
    for x in new_ids:
        if x: current.add(x.strip())
    ALLOWLIST_PATH.write_text("\n".join(sorted(current)) + "\n", encoding="utf-8")

# -----------------------------
# HTTP helpers
# -----------------------------
BASE = "https://apis.datos.gob.ar/series/api/series"

def _get(url: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def datosar_search(query: str, limit: int = 50) -> List[dict]:
    """Búsqueda de series por texto."""
    if not query.strip():
        return []
    url = f"{BASE}/search"
    js = _get(url, params={"q": query, "limit": limit})
    return js.get("results", []) or []

def fetch_series(ids: List[str]) -> pd.DataFrame:
    """Baja varias series por id (join por fecha); devuelve LONG (id, fecha, valor, titulo)."""
    out_frames: List[pd.DataFrame] = []
    for _id in ids:
        url = f"{BASE}"
        try:
            js = _get(url, params={"ids": _id, "format": "json"})
        except Exception:
            continue
        data = js.get("data")
        if not data:
            continue
        fechas = [pd.to_datetime(x[0]) for x in data]
        valores = [x[1] if len(x) > 1 else None for x in data]
        # metadatos
        meta = js.get("meta", [{}])
        title = meta[0].get("title", _id)
        df = pd.DataFrame({"fecha": fechas, "valor": valores})
        df["id"] = _id
        df["titulo"] = title
        out_frames.append(df)
        time.sleep(0.2)  # respeto
    if not out_frames:
        return pd.DataFrame(columns=["id", "fecha", "valor", "titulo"])
    long_df = pd.concat(out_frames, ignore_index=True).sort_values(["id", "fecha"])
    return long_df

def fetch_datosar_to_disk(ids: List[str]) -> None:
    df_new = fetch_series(ids)
    if df_new.empty:
        print("⚠️ No se descargó ninguna serie.")
        return
    if PARQUET_PATH.exists():
        df_old = pd.read_parquet(PARQUET_PATH)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["id", "fecha"]).sort_values(["id", "fecha"])
    else:
        df = df_new
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"✅ Guardado: {PARQUET_PATH} ({len(df):,} filas)")

def load_datosar_long() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        return pd.DataFrame(columns=["id", "fecha", "valor", "titulo"])
    df = pd.read_parquet(PARQUET_PATH)
    # tipificación
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["id", "fecha"])
    return df

def presets_catalog() -> Dict[str, List[Dict[str, str]]]:
    return DATOSAR_PRESETS
