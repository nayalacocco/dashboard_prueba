#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Construye el catálogo local desde data/series_tiempo_metadatos.csv
y baja las series seleccionadas (por keywords) desde la API
https://apis.datos.gob.ar/series/api/series/

Salida:
- data/datosar_catalog_meta.parquet  (catálogo curado)
- data/datosar_long.parquet          (series en formato largo: fecha/descripcion/valor)
"""

import os
import re
import time
import json
import math
import random
import pathlib
import textwrap
import warnings
from typing import List, Dict, Optional

import pandas as pd
import requests

BASE_API = "https://apis.datos.gob.ar/series/api/series/"
DATA_DIR = pathlib.Path("data")
META_CSV = DATA_DIR / "series_tiempo_metadatos.csv"
CAT_OUT  = DATA_DIR / "datosar_catalog_meta.parquet"
LONG_OUT = DATA_DIR / "datosar_long.parquet"
KW_FILE  = DATA_DIR / "datosar_keywords.txt"

# ---------- utilidades suaves para nombres/columnas ----------
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _clean_label(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 180:
        s = s[:177] + "…"
    return s

def _load_keywords() -> List[str]:
    if KW_FILE.exists():
        kws = [x.strip().lower() for x in KW_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
        if kws:
            return kws
    # fallback por defecto
    return [
        "inflación", "ipc",
        "resultado primario", "resultado financiero",
        "ingresos", "gasto", "déficit", "superávit",
        "mecon", "hacienda", "tesoro", "indec"
    ]

def _looks_percent(label: str) -> bool:
    s = label.lower()
    toks = ["%", "tna", "tea", "variación", "variacion", "interanual", "mensual", "ipc", "inflación", "inflacion"]
    return any(t in s for t in toks)

# ---------- lectura de metadatos ----------
def load_meta() -> pd.DataFrame:
    if not META_CSV.exists():
        raise FileNotFoundError(f"No encuentro {META_CSV}. Poné el CSV de metadatos ahí.")

    df = pd.read_csv(META_CSV)
    # columnas probables con nombres alternativos
    col_id     = _first_col(df, ["id", "series_id", "identificador", "identificador_serie"])
    col_title  = _first_col(df, ["title", "titulo", "nombre", "nombre_serie"])
    col_org    = _first_col(df, ["publisher", "organismo", "organism", "organizacion"])
    col_units  = _first_col(df, ["units", "unidad_medida", "unidades", "unit"])
    col_theme  = _first_col(df, ["theme", "tema", "categoria"])
    col_freq   = _first_col(df, ["periodicity", "frecuencia", "periodicidad"])
    col_start  = _first_col(df, ["start_date", "desde", "inicio"])
    col_end    = _first_col(df, ["end_date", "hasta", "fin"])

    needed = [("id", col_id), ("title", col_title)]
    missing = [k for k, v in needed if v is None]
    if missing:
        raise RuntimeError(f"El CSV de metadatos no tiene columnas mínimas: {missing}. Columns={list(df.columns)}")

    cat = pd.DataFrame({
        "id": df[col_id].astype(str),
        "name": df[col_title].astype(str).map(_clean_label),
        "group": df[col_org]  .astype(str) if col_org else "(desconocido)",
        "units": df[col_units].astype(str) if col_units else "",
        "theme": df[col_theme].astype(str) if col_theme else "",
        "frequency": df[col_freq].astype(str) if col_freq else "",
        "start": df[col_start] if col_start else None,
        "end": df[col_end] if col_end else None,
    })

    # limpiar NaNs a strings
    for c in ["group", "units", "theme", "frequency"]:
        if c in cat.columns:
            cat[c] = cat[c].fillna("")

    # drop duplicados por id con preferencia a títulos más largos (suelen ser más descriptivos)
    cat = cat.sort_values(by=["id", "name"], key=lambda s: s.str.len(), ascending=False)
    cat = cat.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return cat

# ---------- selección por keywords ----------
def filter_by_keywords(cat: pd.DataFrame, keywords: List[str]) -> pd.DataFrame:
    if not keywords:
        return cat.copy()

    def hit(row) -> bool:
        blob = " ".join([
            row.get("id", ""), row.get("name", ""), row.get("group", ""),
            row.get("units", ""), row.get("theme", "")
        ]).lower()
        return any(kw in blob for kw in keywords)

    mask = cat.apply(hit, axis=1)
    return cat[mask].reset_index(drop=True)

# ---------- descarga series ----------
def fetch_one_series(serie_id: str, session: requests.Session, max_rows: int = 100000) -> pd.DataFrame:
    # Pedimos una por una (más fácil de parsear)
    params = {
        "ids": serie_id,
        "format": "json",
        "metadata": "full",
        "limit": str(max_rows)
    }
    r = session.get(BASE_API, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    # API responde con 'data' = lista de filas, cada fila tiene 'index' + columna con el ID
    data = js.get("data", [])
    if not data:
        return pd.DataFrame(columns=["fecha", "valor"])

    df = pd.DataFrame(data)
    if "index" not in df.columns or serie_id not in df.columns:
        # formato raro: probamos variantes
        # a veces la columna del id viene como string con espacios o mayúsculas iguales
        col_val = None
        for c in df.columns:
            if c.strip() == serie_id:
                col_val = c
                break
        if col_val is None:
            # damos contexto para depurar
            raise RuntimeError(f"Respuesta sin columnas esperadas para {serie_id}. Keys={list(df.columns)}")
        value_col = col_val
    else:
        value_col = serie_id

    df = df.rename(columns={"index": "fecha", value_col: "valor"})
    # parseo de fecha (API suele traer 'YYYY-MM-DD')
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[["fecha", "valor"]].dropna(subset=["fecha"]).sort_values("fecha")
    return df

def polite_sleep(min_s=0.25, max_s=0.6):
    time.sleep(random.uniform(min_s, max_s))

def build_long(cat_sel: pd.DataFrame) -> pd.DataFrame:
    sess = requests.Session()
    rows = []
    total = len(cat_sel)
    for i, row in cat_sel.iterrows():
        sid = row["id"]
        name = row["name"]
        try:
            df = fetch_one_series(sid, sess)
            if df.empty:
                continue
            df["descripcion"] = name  # usamos el nombre humano en la UI
            rows.append(df)
        except requests.HTTPError as e:
            # 400/404 de una serie puntual => seguimos
            print(f"[skip] {sid} ({name}): {e}")
        except Exception as e:
            print(f"[warn] {sid} ({name}): {e}")
        finally:
            polite_sleep()

        if (i + 1) % 10 == 0:
            print(f"  bajadas {i+1}/{total}…")

    if not rows:
        return pd.DataFrame(columns=["fecha", "valor", "descripcion"])
    out = pd.concat(rows, ignore_index=True)
    # tipos
    out["valor"] = pd.to_numeric(out["valor"], errors="coerce")
    out = out.dropna(subset=["valor", "fecha"])
    return out

# ---------- main ----------
def main():
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    print("[DatosAR] Leyendo metadatos…")
    cat = load_meta()
    print(f"  metadatos: {len(cat):,} series")

    kws = _load_keywords()
    print(f"[DatosAR] Filtrando por keywords: {kws}")
    cat_sel = filter_by_keywords(cat, kws)
    print(f"  seleccionadas: {len(cat_sel):,} series")

    if cat_sel.empty:
        raise RuntimeError("La selección quedó vacía. Ajustá data/datosar_keywords.txt o quitá filtro.")

    # guardamos catálogo curado
    cat_sel.to_parquet(CAT_OUT, index=False)
    print(f"[DatosAR] Catálogo guardado en {CAT_OUT} ({len(cat_sel):,} filas).")

    print("[DatosAR] Bajando series… (modo paciente)")
    long_df = build_long(cat_sel)
    if long_df.empty:
        raise RuntimeError("No pude bajar datos de ninguna serie seleccionada.")

    long_df.to_parquet(LONG_OUT, index=False)
    print(f"[DatosAR] Datos guardados en {LONG_OUT} ({len(long_df):,} filas).")

if __name__ == "__main__":
    main()
