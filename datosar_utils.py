# datosar_utils.py (en la raíz del repo)
import csv
import io
import time
import json
import pathlib as p
from typing import Iterable, Tuple, List

import pandas as pd
import requests

BASE = "https://apis.datos.gob.ar/series/api/series"

# ---------- helpers robustos ----------

def _read_csv_robust(content: bytes) -> pd.DataFrame:
    return pd.read_csv(
        io.BytesIO(content),
        dtype=str,
        engine="python",
        on_bad_lines="skip"
    )

def _normalize_series_df(df: pd.DataFrame, series_id: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["fecha", "valor"])

    time_candidates = ["fecha", "Fecha", "indice_tiempo", "time", "index", "periodo"]
    tcol = next((c for c in time_candidates if c in df.columns), None)
    if tcol is None:
        return pd.DataFrame(columns=["fecha", "valor"])

    df = df.rename(columns={tcol: "fecha"})

    value_candidates = ["valor", "Valor", "value", "serie", series_id]
    vcol = next((c for c in value_candidates if c in df.columns), None)
    if vcol is None:
        non_time = [c for c in df.columns if c != "fecha"]
        vcol = non_time[-1] if non_time else None
        if vcol is None:
            return pd.DataFrame(columns=["fecha", "valor"])

    df = df[["fecha", vcol]].rename(columns={vcol: "valor"})

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    df = df.dropna(subset=["fecha"]).sort_values("fecha")
    return df


def _series_url(series_id: str, fmt: str = "csv", limit: int = 50000) -> str:
    return f"{BASE}?ids={series_id}&format={fmt}&limit={limit}"


# ---------- API pública ----------

def fetch_ids_to_long(ids: Iterable[str]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for sid in ids:
        url = _series_url(sid, fmt="csv")
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            df_raw = _read_csv_robust(r.content)
            df_norm = _normalize_series_df(df_raw, sid)
            if df_norm.empty:
                continue
            df_norm.insert(0, "descripcion", sid)
            frames.append(df_norm)
        except requests.HTTPError as e:
            print(f"[WARN] {sid}: HTTP {e}")
            continue
        except Exception as e:
            print(f"[WARN] {sid}: {e}")
            continue
        time.sleep(0.2)

    if not frames:
        return pd.DataFrame(columns=["descripcion", "fecha", "valor"])

    long_df = pd.concat(frames, ignore_index=True)
    return long_df


def save_long(df_long: pd.DataFrame, out_path: str) -> None:
    out = p.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df_long.to_parquet(out, index=False)


def build_catalog_and_allowlist(raw_dir: str, out_catalog: str, keywords: List[str] | None = None) -> Tuple[pd.DataFrame, List[str]]:
    raw = p.Path(raw_dir)
    metas = []
    for f in raw.glob("series-tiempo-metadatos-*.csv"):
        try:
            df = pd.read_csv(f, dtype=str, engine="python", on_bad_lines="skip")
            metas.append(df)
        except Exception as e:
            print(f"[WARN] No pude leer {f.name}: {e}")
    if not metas:
        raise RuntimeError("No pude construir el catálogo de DatosAR (sin filas).")

    cat = pd.concat(metas, ignore_index=True)

    id_col = next((c for c in ["identifier", "id", "series_id"] if c in cat.columns), None)
    name_col = next((c for c in ["title", "nombre", "title_es"] if c in cat.columns), None)
    src_col = next((c for c in ["publisher", "dataset_publisher_name"] if c in cat.columns), None)
    if id_col is None:
        raise RuntimeError("No encuentro columna de ID en los metadatos (identifier/id).")

    cat_min = pd.DataFrame({
        "id": cat[id_col].astype(str),
        "name": cat[name_col].astype(str) if name_col else cat[id_col].astype(str),
        "source": cat[src_col].astype(str) if src_col else "",
    }).dropna(subset=["id"])

    cat_min = cat_min.drop_duplicates(subset=["id"]).reset_index(drop=True)

    if keywords:
        kw = "|".join([k.strip() for k in keywords if k.strip()])
        mask = cat_min["name"].str.contains(kw, case=False, na=False) | cat_min["id"].str.contains(kw, case=False, na=False)
        allow = cat_min.loc[mask, "id"].tolist()
    else:
        allow = cat_min["id"].tolist()

    out = p.Path(out_catalog)
    out.parent.mkdir(parents=True, exist_ok=True)
    cat_min.to_parquet(out, index=False)

    return cat_min, allow
