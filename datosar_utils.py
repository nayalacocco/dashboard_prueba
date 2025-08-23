# datosar_utils.py
from __future__ import annotations
import json
import pathlib as p
from typing import Iterable, Dict, Any
import pandas as pd
import requests

DATA_DIR = p.Path("data")
RAW_DIR  = DATA_DIR / "datosar_raw"
PARQUET  = DATA_DIR / "datosar_long.parquet"

RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://apis.datos.gob.ar/series/api/series/"

def _fetch_series_json(series_id: str) -> Dict[str, Any]:
    params = {"ids": series_id, "format": "json"}
    r = requests.get(API_BASE, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def fetch_datosar_to_disk(series_ids: Iterable[str]) -> None:
    """Baja una lista de IDs de la API de Datos Argentina, guarda raws y consolida a long parquet."""
    frames = []
    for sid in series_ids:
        try:
            payload = _fetch_series_json(sid)
        except requests.HTTPError as e:
            print(f"⚠️  No pude bajar {sid}: {e}")
            continue

        # Raw
        (RAW_DIR / f"{sid.replace('/', '_')}.json").write_text(
            json.dumps(payload, ensure_ascii=False)
        )

        data = payload.get("data", [])
        meta = payload.get("series", [])
        if not data or not meta:
            continue

        df = pd.DataFrame(data, columns=["fecha"] + [s["id"] for s in meta])
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.melt(id_vars="fecha", var_name="id", value_name="valor")

        meta_map = {s["id"]: s.get("description", s.get("title", s["id"])) for s in meta}
        df["descripcion"] = df["id"].map(meta_map)
        frames.append(df)

    if not frames:
        raise RuntimeError("No se pudo bajar ninguna serie de Datos Argentina")

    out = pd.concat(frames, ignore_index=True)
    out.sort_values(["id", "fecha"], inplace=True)
    out.to_parquet(PARQUET, index=False)
    print(f"✅ Guardé {len(out):,} registros en {PARQUET}")

def load_datosar_long() -> pd.DataFrame:
    if not PARQUET.exists():
        return pd.DataFrame(columns=["fecha", "id", "valor", "descripcion"])
    df = pd.read_parquet(PARQUET)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df
