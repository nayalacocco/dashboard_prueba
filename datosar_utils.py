# datosar_utils.py
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

API_BASE = "https://apis.datos.gob.ar/series/api"
DATA_DIR = Path("data")
CATALOG_JSON = DATA_DIR / "datosar_catalog.json"
SERIES_PARQUET = DATA_DIR / "datosar_series.parquet"
ALLOWLIST = DATA_DIR / "datosar_allowlist.txt"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------- HTTP helpers ----------------------------- #

def _get(url: str, params: Dict[str, str] | None = None, *, retries: int = 3, timeout: int = 30) -> dict:
    for i in range(retries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        # backoff suave ante 4xx/5xx
        time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"GET {url} {params} -> {r.status_code} {r.text[:200]}")

# ----------------------------- API wrappers ----------------------------- #

def api_search(q: str, limit: int = 200, offset: int = 0) -> dict:
    """
    Docs oficiales:
    - GET Buscar series de tiempo (/search) y
    - GET Valores de series (/series)
    https://series-tiempo.argentina.apidocs.ar/operations/search    [oai_citation:0‡series-tiempo.argentina.apidocs.ar](https://series-tiempo.argentina.apidocs.ar/operations/search)
    https://series-tiempo.argentina.apidocs.ar/operations/values    [oai_citation:1‡series-tiempo.argentina.apidocs.ar](https://series-tiempo.argentina.apidocs.ar/operations/series)
    """
    url = f"{API_BASE}/search"
    return _get(url, {"q": q, "limit": str(limit), "offset": str(offset)})

def api_values(ids: Iterable[str], start: str | None = None, end: str | None = None, limit: int = 50000) -> dict:
    url = f"{API_BASE}/series"
    params = {"ids": ",".join(ids), "format": "json", "limit": str(limit)}
    if start: params["start_date"] = start
    if end:   params["end_date"] = end
    return _get(url, params)

# ----------------------------- ETL helpers ----------------------------- #

@dataclass
class SeriesMeta:
    id: str
    title: str
    dataset_title: Optional[str] = None
    publisher: Optional[str] = None
    units: Optional[str] = None
    frequency: Optional[str] = None
    source: Optional[str] = None

def _flatten_search_item(it: dict) -> SeriesMeta:
    m = it.get("metadata", {}) or {}
    return SeriesMeta(
        id=it.get("id") or m.get("id"),
        title=m.get("title") or it.get("title") or it.get("description") or "",
        dataset_title=(m.get("dataset", {}) or {}).get("title"),
        publisher=(m.get("dataset", {}) or {}).get("publisher"),
        units=(m.get("units") or m.get("unit")),
        frequency=m.get("frequency") or m.get("periodicity"),
        source=m.get("source"),
    )

def _df_from_values(payload: dict) -> pd.DataFrame:
    """
    Convierte la respuesta /series en wide, index fecha (datetime).
    """
    # payload["data"] es tabla; payload["headers"] describe columnas (la 1ra es "index")
    headers = payload.get("headers", [])
    data = payload.get("data", [])
    if not headers or not data:
        return pd.DataFrame()

    cols = [h.get("name") for h in headers]
    df = pd.DataFrame(data, columns=cols)
    # 1ra col → fecha
    date_col = cols[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    # el resto son series (ids)
    return df

# ----------------------------- Disco ----------------------------- #

def save_catalog(metas: List[SeriesMeta]) -> None:
    payload = [m.__dict__ for m in metas if m.id]
    CATALOG_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def load_catalog() -> List[SeriesMeta]:
    if not CATALOG_JSON.exists():
        return []
    raw = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    return [SeriesMeta(**x) for x in raw]

def save_series_parquet(df_wide: pd.DataFrame) -> None:
    if df_wide.empty:
        return
    df_wide.to_parquet(SERIES_PARQUET)

def load_datosar_long() -> pd.DataFrame:
    """
    Devuelve formato largo: fecha, id, valor + metadatos básicos.
    """
    if not SERIES_PARQUET.exists():
        return pd.DataFrame(columns=["fecha", "id", "valor"])
    wide = pd.read_parquet(SERIES_PARQUET)
    long = (
        wide.stack()
            .rename("valor")
            .reset_index()
            .rename(columns={wide.index.name or "index": "fecha", "level_1": "id"})
            .sort_values("fecha")
    )
    return long

# ----------------------------- FETCH principal ----------------------------- #

DEFAULT_QUERIES = [
    # Fiscal / Tesoro
    "resultado primario",
    "resultado financiero",
    "ingresos totales",
    "gasto total",
    "resultado del sector público",
    # Actividad, empleo, precios (para poblar el catálogo con algo útil)
    "inflación ipc nivel general",
    "pbi trimestral a precios",
    "desempleo tasa",
    "índice de producción industrial",
]

def _read_allowlist() -> List[str]:
    if ALLOWLIST.exists():
        ids = [l.strip() for l in ALLOWLIST.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        return sorted(set(ids))
    return []

def fetch_datosar_to_disk(
    queries: List[str] | None = None,
    *,
    hard_allowlist: List[str] | None = None,
    per_query_limit: int = 120,
) -> Tuple[List[SeriesMeta], pd.DataFrame]:
    """
    1) arma catálogo (metadatos) vía /search con consultas predefinidas o allowlist
    2) baja valores vía /series y los guarda en wide parquet
    """
    allow_ids = set(hard_allowlist or []) | set(_read_allowlist())
    metas: Dict[str, SeriesMeta] = {}

    if allow_ids:
        # si hay allowlist, metadata mínima a partir de /search id:xxx
        for sid in allow_ids:
            payload = api_search(f"id:{sid}", limit=1)
            items = payload.get("items") or payload.get("data") or []
            if items:
                m = _flatten_search_item(items[0])
                metas[m.id] = m

    queries = queries or DEFAULT_QUERIES
    for q in queries:
        payload = api_search(q, limit=per_query_limit)
        items = payload.get("items") or payload.get("data") or []
        for it in items:
            m = _flatten_search_item(it)
            if m.id:
                metas[m.id] = m

    if not metas:
        raise RuntimeError("No se encontraron series en la búsqueda (catálogo vacío).")

    # bajamos valores en tandas
    ids = sorted(metas.keys())
    W: Optional[pd.DataFrame] = None
    batch = 20
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        val = api_values(chunk, limit=50000)
        df = _df_from_values(val)
        if df.empty:
            continue
        W = df if W is None else W.join(df, how="outer")
        time.sleep(0.2)

    if W is None or W.empty:
        raise RuntimeError("No llegaron datos de valores para las series encontradas.")

    save_catalog(list(metas.values()))
    save_series_parquet(W)

    return list(metas.values()), W

# ----------------------------- Helpers UI ----------------------------- #

def publishers_datasets_series() -> Tuple[List[str], Dict[str, List[str]], Dict[Tuple[str, str], List[SeriesMeta]]]:
    """
    A partir del catálogo local, arma 3 estructuras:
      - publishers: lista única de publicadores
      - datasets_by_pub: dict pub -> [dataset_title]
      - series_by_pub_ds: dict (pub, dataset_title) -> [SeriesMeta]
    """
    metas = load_catalog()
    by_pub: Dict[str, List[str]] = {}
    by_key: Dict[Tuple[str, str], List[SeriesMeta]] = {}

    pubs: List[str] = []
    for m in metas:
        pub = m.publisher or "Desconocido"
        ds  = m.dataset_title or "Dataset sin título"
        if pub not in pubs:
            pubs.append(pub)
        by_pub.setdefault(pub, [])
        if ds not in by_pub[pub]:
            by_pub[pub].append(ds)
        by_key.setdefault((pub, ds), []).append(m)

    pubs.sort()
    for k in by_pub:
        by_pub[k] = sorted(by_pub[k])
    for k in by_key:
        by_key[k] = sorted(by_key[k], key=lambda x: x.title or x.id)
    return pubs, by_pub, by_key
