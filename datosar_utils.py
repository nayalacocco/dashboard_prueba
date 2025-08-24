# datosar_utils.py
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Iterable, List, Tuple, Dict

import pandas as pd
import requests


# --- Paths
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW  = DATA / "raw"
DATA.mkdir(exist_ok=True, parents=True)
RAW.mkdir(exist_ok=True, parents=True)

# --- Archivos de salida estandarizados
CAT_PARQUET   = DATA / "datosar_catalog_meta.parquet"
ALLOWLIST_TXT = DATA / "datosar_allowlist.txt"
LONG_PARQUET  = DATA / "datosar_long.parquet"

# --- Endpoint oficial de Series-tiempo
BASE_API = "https://apis.datos.gob.ar/series/api/series/"

# ---------------------------------------------------------------------
# Helpers robustos
# ---------------------------------------------------------------------
def _norm_col(df: pd.DataFrame, wanted: str, candidates: Iterable[str]) -> str:
    """
    Busca en df.columns algún nombre parecido a la lista candidates.
    Si encuentra, devuelve ese nombre de columna; si no, crea una columna vacía.
    """
    for c in df.columns:
        cl = c.strip().lower()
        for w in candidates:
            if cl == w.lower():
                return c
    # no la tengo: creo columna vacía
    df[wanted] = pd.NA
    return wanted


def load_metadata_csv(csv_path: Path) -> pd.DataFrame:
    """
    Carga el CSV pesado de metadatos (series-tiempo) y normaliza columnas
    claves: id, titulo, descripcion, unidad, organismo, dataset, tema, frecuencia
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"No encuentro el archivo de metadatos: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    # Normalizo columnas con nombres flexibles
    col_id   = _norm_col(df, "id", ["id", "serie_id", "identificador"])
    col_tit  = _norm_col(df, "titulo", ["titulo", "title", "nombre"])
    col_desc = _norm_col(df, "descripcion", ["descripcion", "description"])
    col_unid = _norm_col(df, "unidad", ["unidad_medida", "unidad", "units"])
    col_org  = _norm_col(df, "organismo", ["organismo_nombre", "organismo", "source", "organization"])
    col_ds   = _norm_col(df, "dataset", ["dataset_titulo", "dataset", "dataset_name"])
    col_tema = _norm_col(df, "tema", ["tema", "topic", "group", "categoria"])
    col_freq = _norm_col(df, "frecuencia", ["frecuencia", "frequency"])

    out = pd.DataFrame({
        "id":           df[col_id].str.strip(),
        "titulo":       df[col_tit].str.strip(),
        "descripcion":  df[col_desc].str.strip(),
        "unidad":       df[col_unid].str.strip(),
        "organismo":    df[col_org].str.strip(),
        "dataset":      df[col_ds].str.strip(),
        "tema":         df[col_tema].str.strip(),
        "frecuencia":   df[col_freq].str.strip(),
    })
    # limpio ids vacíos
    out = out[out["id"].notna() & (out["id"] != "")]
    out = out.drop_duplicates(subset=["id"]).reset_index(drop=True)
    return out


def build_catalog_from_keywords(meta: pd.DataFrame, keywords: Iterable[str], limit_per_kw: int = 200) -> pd.DataFrame:
    """
    Filtra el CSV de metadatos por keywords (OR) en un campo combinado,
    devuelve un catálogo reducido con columnas estandarizadas.
    """
    if meta.empty:
        return pd.DataFrame()

    # Campo de búsqueda amplio
    haystack = (
        meta["id"].fillna("") + " " +
        meta["titulo"].fillna("") + " " +
        meta["descripcion"].fillna("") + " " +
        meta["dataset"].fillna("") + " " +
        meta["organismo"].fillna("") + " " +
        meta["tema"].fillna("")
    ).str.lower()

    sel_rows = []
    for kw in keywords:
        k = kw.strip().lower()
        if not k:
            continue
        mask = haystack.str.contains(re.escape(k), na=False)
        chunk = meta[mask].copy()
        if limit_per_kw is not None and limit_per_kw > 0:
            chunk = chunk.head(limit_per_kw)
        sel_rows.append(chunk)

    if not sel_rows:
        return pd.DataFrame()

    reduced = pd.concat(sel_rows, ignore_index=True).drop_duplicates(subset=["id"]).reset_index(drop=True)

    # Catálogo final (group = organismo o dataset; name = título)
    reduced["group"] = reduced["organismo"].fillna("").replace("", pd.NA).fillna(reduced["dataset"]).fillna("Otros")
    reduced["name"]  = reduced["titulo"].replace("", pd.NA).fillna(reduced["id"])
    reduced["units"] = reduced["unidad"]

    catalog = reduced[["id", "name", "group", "units", "frecuencia", "dataset", "organismo", "tema", "titulo", "descripcion"]].copy()
    return catalog.sort_values(["group", "name"]).reset_index(drop=True)


def write_allowlist(catalog: pd.DataFrame, path: Path = ALLOWLIST_TXT) -> None:
    ids = catalog["id"].dropna().unique().tolist()
    path.write_text("\n".join(ids), encoding="utf-8")


# ---------------------------------------------------------------------
# Descarga de series
# ---------------------------------------------------------------------
def _get(url: str, timeout: int = 30, tries: int = 3) -> Dict:
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"{r.status_code} {r.text[:180]}"
        except Exception as e:
            last = str(e)
        time.sleep(1.5)
    raise RuntimeError(f"GET falló para {url} -> {last}")


def fetch_one_series(serie_id: str) -> pd.DataFrame:
    """
    Devuelve un DF con columnas: fecha, valor
    """
    url = f"{BASE_API}?ids={serie_id}&format=json"
    js = _get(url)
    if "data" not in js or "index" not in js:
        raise RuntimeError(f"Respuesta inesperada para {serie_id}")

    idx = pd.to_datetime(js["index"])
    vals = [row[0] if isinstance(row, list) else row for row in js["data"]]
    df = pd.DataFrame({"fecha": idx, "valor": vals})
    return df.dropna(subset=["valor"])


def fetch_many_series(ids: Iterable[str], name_map: Dict[str, str]) -> pd.DataFrame:
    """
    Junta todas las series en formato largo: fecha, descripcion, valor, id
    """
    frames = []
    for sid in ids:
        try:
            s = fetch_one_series(sid)
            s["id"] = sid
            s["descripcion"] = name_map.get(sid, sid)
            frames.append(s)
        except Exception as e:
            print(f"⚠️ No pude bajar {sid}: {e}")
    if not frames:
        return pd.DataFrame(columns=["fecha", "descripcion", "valor", "id"])
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"]).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------
# Orquestadores usados por los scripts
# ---------------------------------------------------------------------
def build_catalog_and_allowlist_from_csv(
    csv_path: Path,
    keywords: Iterable[str],
    out_catalog_parquet: Path = CAT_PARQUET,
    out_allowlist_txt: Path = ALLOWLIST_TXT,
) -> pd.DataFrame:
    meta = load_metadata_csv(csv_path)
    cat = build_catalog_from_keywords(meta, keywords)
    if cat.empty:
        raise RuntimeError("No pude construir el catálogo (sin filas). ¿Keywords muy restrictivas?")

    cat.to_parquet(out_catalog_parquet, index=False)
    write_allowlist(cat, path=out_allowlist_txt)
    return cat


def fetch_to_long_from_allowlist(
    allowlist_path: Path = ALLOWLIST_TXT,
    catalog_parquet: Path = CAT_PARQUET,
    out_long_parquet: Path = LONG_PARQUET,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not allowlist_path.exists():
        raise FileNotFoundError(f"No encuentro allowlist: {allowlist_path}")
    if not catalog_parquet.exists():
        raise FileNotFoundError(f"No encuentro catálogo: {catalog_parquet}")

    ids = [x.strip() for x in allowlist_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    cat = pd.read_parquet(catalog_parquet)
    name_map = dict(zip(cat["id"], cat["name"]))

    long = fetch_many_series(ids, name_map)
    if long.empty:
        raise RuntimeError("No pude descargar ninguna serie.")

    long.to_parquet(out_long_parquet, index=False)
    return cat, long
