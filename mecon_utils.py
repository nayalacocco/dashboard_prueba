# mecon_utils.py
from __future__ import annotations
import requests
from functools import lru_cache

BASE = "https://apis.datos.gob.ar/series/api"

@lru_cache(maxsize=256)
def series_search(q: str, page_size: int = 50):
    # Busca series por texto libre (título, descripción, tema, publisher)
    url = f"{BASE}/search"
    params = {"q": q, "page_size": page_size}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

@lru_cache(maxsize=256)
def series_get(ids: list[str], start: str | None = None, end: str | None = None,
               collapse: str | None = None, format_: str = "json", metadata: str = "simple"):
    url = f"{BASE}/series"
    params = {
        "ids": ",".join(ids),
        "format": format_,
        "metadata": metadata,
        "limit": 5000,    # suficiente para mensual/anual
    }
    if start:    params["start_date"] = start   # "YYYY-MM-DD"
    if end:      params["end_date"]   = end
    if collapse: params["collapse"]   = collapse  # "month", "year", etc.
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()
