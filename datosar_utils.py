# datosar_utils.py
from __future__ import annotations
import json
import pathlib as p
from typing import Iterable, Dict, Any, List, Tuple
import pandas as pd
import requests

# Directorios/archivos
DATA_DIR = p.Path("data")
RAW_DIR  = DATA_DIR / "datosar_raw"
PARQUET  = DATA_DIR / "datosar_long.parquet"
ALLOWLIST = DATA_DIR / "datosar_allowlist.txt"

RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API base (Datos Argentina - Series de Tiempo)
API_BASE = "https://apis.datos.gob.ar/series/api/series/"

# ---------------------------
# Utilidades de red
# ---------------------------
def _http_get(params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.get(API_BASE, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def _fetch_series_json(series_id: str) -> Dict[str, Any]:
    # Bajada “por id” (formato JSON)
    return _http_get({"ids": series_id, "format": "json"})

def search_datosar(query: str, limit: int = 50) -> List[Tuple[str, str, str]]:
    """
    Busca series por texto. Devuelve lista de tuplas (id, title/description, dataset).
    Nota: la API expone búsqueda por 'q'. Algunos catálogos usan 'search'; probamos ambos.
    """
    out: List[Tuple[str, str, str]] = []
    for key in ("q", "search"):
        try:
            payload = _http_get({key: query, "limit": limit, "format": "json", "metadata": "full"})
        except Exception:
            continue
        # payload típico: {"data": [...], "series": [{id, title, dataset, ...}]}
        meta = payload.get("series", [])
        for s in meta:
            sid   = s.get("id", "")
            title = s.get("title") or s.get("description") or sid
            ds    = (s.get("dataset", {}) or {}).get("title", "")
            if sid:
                out.append((sid, title, ds))
        if out:
            break
    return out

# ---------------------------
# Persistencia lista blanca
# ---------------------------
def read_allowlist() -> List[str]:
    if not ALLOWLIST.exists():
        return []
    ids = [ln.strip() for ln in ALLOWLIST.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # únicos y ordenados
    return sorted(set(ids))

def upsert_allowlist(ids: Iterable[str]) -> List[str]:
    current = set(read_allowlist())
    current.update(i.strip() for i in ids if i and i.strip())
    ordered = sorted(current)
    ALLOWLIST.write_text("\n".join(ordered), encoding="utf-8")
    return ordered

# ---------------------------
# Fetch + load
# ---------------------------
def fetch_datosar_to_disk(series_ids: Iterable[str]) -> None:
    """
    Baja una lista de IDs de Datos Argentina, guarda raws y consolida todo a long parquet.
    """
    frames = []
    for sid in series_ids:
        try:
            payload = _fetch_series_json(sid)
        except requests.HTTPError as e:
            print(f"⚠️  No pude bajar {sid}: {e}")
            continue
        except Exception as e:
            print(f"⚠️  Error desconocido con {sid}: {e}")
            continue

        # Guardamos raw
        (RAW_DIR / f"{sid.replace('/', '_')}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        data = payload.get("data", [])
        meta = payload.get("series", [])
        if not data or not meta:
            continue

        # Columnas: fecha + una columna por serie del paquete
        cols = ["fecha"] + [s["id"] for s in meta]
        df = pd.DataFrame(data, columns=cols)
        df["fecha"] = pd.to_datetime(df["fecha"])

        # Long
        df = df.melt(id_vars="fecha", var_name="id", value_name="valor")

        # Descripción amigable
        meta_map = {s["id"]: (s.get("description") or s.get("title") or s["id"]) for s in meta}
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

# ---------------------------
# Atajo: buscar y añadir
# ---------------------------
def add_and_fetch(ids: Iterable[str]) -> None:
    """Agrega IDs a la allowlist y los baja/actualiza en el parquet."""
    ids_final = upsert_allowlist(ids)
    fetch_datosar_to_disk(ids_final)
