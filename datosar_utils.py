# datosar_utils.py
from __future__ import annotations
import pathlib
from typing import List, Optional, Dict

import pandas as pd
import requests
import time

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PARQUET_PATH = DATA_DIR / "datosar_long.parquet"
ALLOWLIST_PATH = DATA_DIR / "datosar_allowlist.txt"

BASE = "https://apis.datos.gob.ar/series/api/series"

# ---------------- I/O allowlist ----------------
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
    cur = set(read_allowlist())
    for x in new_ids:
        if x:
            cur.add(x.strip())
    ALLOWLIST_PATH.write_text("\n".join(sorted(cur)) + "\n", encoding="utf-8")

# --------------- descarga por IDs ---------------
def _get_json(params: Dict) -> dict:
    r = requests.get(BASE, params=params, timeout=45)
    r.raise_for_status()
    return r.json()

def fetch_ids(ids: List[str]) -> pd.DataFrame:
    frames = []
    for _id in ids:
        try:
            js = _get_json({"ids": _id, "format": "json"})
        except Exception:
            # si falla un id, seguimos con el resto
            continue
        data = js.get("data") or []
        if not data:
            continue
        fechas = [pd.to_datetime(x[0]) for x in data]
        vals = [x[1] if len(x) > 1 else None for x in data]
        meta = js.get("meta", [{}])
        titulo = meta[0].get("title", _id)
        df = pd.DataFrame({"fecha": fechas, "valor": vals})
        df["id"] = _id
        df["titulo"] = titulo
        frames.append(df)
        time.sleep(0.2)  # respeto
    if not frames:
        return pd.DataFrame(columns=["id", "fecha", "valor", "titulo"])
    out = pd.concat(frames, ignore_index=True).sort_values(["id", "fecha"])
    return out

def fetch_datosar_to_disk(ids: Optional[List[str]] = None) -> None:
    ids = ids if ids is not None else read_allowlist()
    if not ids:
        print("⚠️ Allowlist vacío (data/datosar_allowlist.txt).")
        return
    df_new = fetch_ids(ids)
    if df_new.empty:
        print("⚠️ No se descargó ninguna serie.")
        return
    if PARQUET_PATH.exists():
        old = pd.read_parquet(PARQUET_PATH)
        df = pd.concat([old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["id", "fecha"]).sort_values(["id", "fecha"])
    else:
        df = df_new
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"✅ Guardado {PARQUET_PATH} con {len(df):,} filas")

def load_datosar_long() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        return pd.DataFrame(columns=["id", "fecha", "valor", "titulo"])
    df = pd.read_parquet(PARQUET_PATH)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.sort_values(["id", "fecha"])
