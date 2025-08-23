# mecon_utils.py
from __future__ import annotations
import pandas as pd
import requests
from pathlib import Path
import json

_BASE = "https://apis.datos.gob.ar/series/api/series"
_CATALOG = Path("data/mecon_catalog.json")
_PARQUET = Path("data/mecon_long.parquet")


def _fetch_series(ident: str) -> pd.DataFrame:
    url = f"{_BASE}?ids={ident}&format=json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    js = r.json()

    data = js["data"]
    cols = js["meta"][0]["fields"]

    df = pd.DataFrame(data, columns=[c["name"] for c in cols])
    df["fecha"] = pd.to_datetime(df["indice_tiempo"], errors="coerce")
    df = df.rename(columns={ident: "valor"})
    df["serie_id"] = ident
    df = df[["fecha", "valor", "serie_id"]].dropna()

    return df


def fetch_mecon_to_disk(series: list[str] | None = None) -> pd.DataFrame:
    """
    Baja series del MECON y guarda en parquet + catálogo.
    Por ahora está hardcodeada una lista mínima de IDs.
    """
    if series is None:
        # 🔧 acá se pueden ir agregando más IDs del MECON
        series = [
            "143.3_TCRZE_0_M_36",   # Resultado fiscal primario ($ corrientes, base caja)
            "143.3_TCRZE_0_M_41",   # Resultado financiero
            "143.3_TCRZE_0_M_33",   # Ingresos totales
            "143.3_TCRZE_0_M_34",   # Gastos primarios
        ]

    all_dfs = []
    for sid in series:
        try:
            df = _fetch_series(sid)
            all_dfs.append(df)
        except Exception as e:
            print(f"⚠ No pude bajar {sid}: {e}")

    if not all_dfs:
        raise RuntimeError("No se pudo bajar ninguna serie MECON")

    df_long = pd.concat(all_dfs).reset_index(drop=True)

    # guardar parquet y catálogo
    _PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df_long.to_parquet(_PARQUET, index=False)

    catalog = [{"id": sid} for sid in series]
    with open(_CATALOG, "w") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    return df_long


def load_mecon_long() -> pd.DataFrame:
    if not _PARQUET.exists():
        raise FileNotFoundError(f"No encontré {_PARQUET}. Corré primero scripts/fetch_mecon.py")
    return pd.read_parquet(_PARQUET)
