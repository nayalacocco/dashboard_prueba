# scripts/fetch_datosar.py
import json
import time
from pathlib import Path
from typing import Tuple

import requests
import pandas as pd

CAT_META = Path("data/datosar_catalog_meta.parquet")
OUT_LONG = Path("data/datosar_long.parquet")

SERIES_BASE = "https://apis.datos.gob.ar/series/api/series/"

HEADERS = {"User-Agent": "AtlasDashboard/1.0 (+github.com/tu-repo)"}

def _get_series_tiempo_ar(series_id: str) -> pd.DataFrame:
    params = {
        "ids": series_id,
        "format": "json",
        "metadata": "full",
    }
    r = requests.get(SERIES_BASE, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    # estructura típica: data["data"] lista de listas, data["columns"] con "names"
    cols = [c["name"] for c in data.get("columns", [])]
    df = pd.DataFrame(data.get("data", []), columns=cols)
    # normalizo nombres comunes
    date_col = next((c for c in df.columns if c.lower().startswith("indice_tiempo") or c.lower()=="time"), df.columns[0])
    value_col = next((c for c in df.columns if c != date_col), df.columns[-1])
    df = df[[date_col, value_col]].rename(columns={date_col:"fecha", value_col:"valor"})
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")
    return df

def _get_csv(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    # heurística básica para fecha/valor
    date_col = next((c for c in df.columns if "fecha" in c.lower() or "periodo" in c.lower() or "mes" in c.lower()), df.columns[0])
    val_col = next((c for c in df.columns if c != date_col and df[c].dtype != "O"), df.columns[-1])
    out = df[[date_col, val_col]].rename(columns={date_col:"fecha", val_col:"valor"})
    out["fecha"] = pd.to_datetime(out["fecha"])
    out = out.sort_values("fecha")
    return out

def fetch_one(source: str, id_or_url: str) -> pd.DataFrame:
    if source == "series-tiempo-ar":
        return _get_series_tiempo_ar(id_or_url)
    elif source in {"ckan", "presupuesto-abierto", "indec"}:
        # asumimos URL a CSV/JSON (CSV preferido)
        if id_or_url.endswith(".json"):
            df = pd.read_json(id_or_url)
            # misma heurística que CSV
            date_col = next((c for c in df.columns if "fecha" in c.lower() or "periodo" in c.lower() or "mes" in c.lower()), df.columns[0])
            val_col = next((c for c in df.columns if c != date_col and df[c].dtype != "O"), df.columns[-1])
            out = df[[date_col, val_col]].rename(columns={date_col:"fecha", val_col:"valor"})
            out["fecha"] = pd.to_datetime(out["fecha"])
            return out.sort_values("fecha")
        else:
            return _get_csv(id_or_url)
    else:
        raise ValueError(f"source no soportado: {source}")

def main():
    if not CAT_META.exists():
        raise FileNotFoundError("Falta data/datosar_catalog_meta.parquet. Corré scripts/fetch_datosar_catalog.py primero.")

    meta = pd.read_parquet(CAT_META)
    rows = []
    fails = []

    for _, row in meta.iterrows():
        group = row["group"]
        name = row["name"]
        source = row["source"]
        ref = row["id_or_url"]
        units = row.get("units", "")

        try:
            df = fetch_one(source, ref)
            df["descripcion"] = name
            df["grupo"] = group
            df["unidades"] = units
            rows.append(df)
            time.sleep(0.2)  # suaviza el rate
            print(f"[OK] {name} ({source})")
        except Exception as e:
            fails.append((name, source, ref, str(e)))
            print(f"[FAIL] {name}: {e}")

    if not rows:
        raise RuntimeError("No se pudo bajar ninguna serie DatosAR.")

    long = pd.concat(rows, ignore_index=True)
    long["valor"] = pd.to_numeric(long["valor"], errors="coerce")
    long = long.dropna(subset=["fecha", "valor"]).sort_values(["descripcion", "fecha"])
    OUT_LONG.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(OUT_LONG, index=False)
    print(f"[DatosAR] Guardado {len(long):,} filas -> {OUT_LONG}")

    if fails:
        LOG = Path("data/datosar_fetch_failures.json")
        with LOG.open("w") as f:
            json.dump([{"name":n,"source":s,"ref":r,"error":e} for (n,s,r,e) in fails], f, ensure_ascii=False, indent=2)
        print(f"[WARN] {len(fails)} series fallaron. Ver {LOG}")

if __name__ == "__main__":
    main()
