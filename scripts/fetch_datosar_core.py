# scripts/fetch_datosar_core.py
from __future__ import annotations
import sys, time, io
from pathlib import Path
import requests
import pandas as pd

OUT = Path("data/datosar_core_long.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

BASE = "https://apis.datos.gob.ar/series/api/series"

SERIES = [
    {"id": "143.3_NO_PR_2004_A_21", "indicador": "emae_original",              "titulo": "EMAE (base 2004=100)",                              "unidades": "Índice (2004=100)"},
    {"id": "148.3_INIVELNAL_DICI_M_26","indicador": "ipc_nivel_general",       "titulo": "IPC Nivel General (base dic-2016)",                "unidades": "Índice"},
    {"id": "116.4_TCRZE_2015_D_36_4",  "indicador": "tcrm_multilateral",        "titulo": "TCRM (2015-12-17=100)",                            "unidades": "Índice"},
    {"id": "94.2_UVAD_D_0_0_10",       "indicador": "uva_diario",               "titulo": "UVA Diario (31/03/2016=14,05)",                    "unidades": "Índice"},
    {"id": "145.3_INGNACUAL_DICI_M_38","indicador": "ipc_variacion_mensual",    "titulo": "IPC variación mensual (nacional)",                 "unidades": "Variación intermensual (%)"},
]

HDRS = {"User-Agent": "macro-core-datosar/1.2", "Accept": "application/json"}

def _try_json(id_: str, start="2000-01-01", timeout=60):
    params = {"ids": id_, "format": "json", "start_date": start, "limit": 500000}
    url = BASE
    r = requests.get(url, params=params, headers=HDRS, timeout=timeout)
    return url, params, r

def _parse_json(id_: str, r_json: dict) -> pd.DataFrame:
    cols = r_json.get("columns") or []
    data = r_json.get("data") or []
    if not cols or not data:
        raise ValueError("JSON sin columns/data")

    t_idx = None
    v_idx = None
    for i, c in enumerate(cols):
        field = (c.get("field") or "").strip()
        if field in ("t", "indice_tiempo", "time"):
            t_idx = i
        if field == id_:
            v_idx = i
    if v_idx is None:
        # fallback por si la serie viene en 'id'
        for i, c in enumerate(cols):
            if (c.get("id") or "").strip() == id_:
                v_idx = i
                break
    if t_idx is None or v_idx is None:
        raise ValueError(f"No ubico columnas (t_idx={t_idx}, v_idx={v_idx})")

    rows = [{"fecha": row[t_idx], "valor": row[v_idx]} for row in data]
    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha", "valor"])

def _try_csv(id_: str, start="2000-01-01", timeout=60):
    params = {"ids": id_, "format": "csv", "start_date": start, "limit": 500000}
    url = BASE
    r = requests.get(url, params=params, headers={"User-Agent": HDRS["User-Agent"], "Accept": "text/csv"}, timeout=timeout)
    return url, params, r

def _parse_csv(id_: str, content: bytes) -> pd.DataFrame:
    # El CSV viene con una columna temporal (indice_tiempo) y una o más columnas numéricas.
    s = io.BytesIO(content)
    df = pd.read_csv(s)
    # Buscamos fecha:
    date_col = None
    for cand in ("indice_tiempo", "t", "time", "fecha"):
        if cand in df.columns:
            date_col = cand
            break
    if date_col is None:
        # a veces viene la fecha como primer columna
        date_col = df.columns[0]

    # Buscamos la columna de valores: preferimos la que se llama exactamente como el ID,
    # si no existe, tomamos la primera columna numérica distinta de la fecha.
    value_col = id_ if id_ in df.columns else None
    if value_col is None:
        num_cols = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols:
            # intentar forzar a numérico por si viene como texto
            for c in df.columns:
                if c != date_col:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            num_cols = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols:
            raise ValueError("No encontré columna numérica en el CSV.")
        value_col = num_cols[0]

    out = df[[date_col, value_col]].rename(columns={date_col: "fecha", value_col: "valor"})
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    out["valor"] = pd.to_numeric(out["valor"], errors="coerce")
    return out.dropna(subset=["fecha", "valor"])

def fetch_series_resilient(id_: str, start="2000-01-01") -> pd.DataFrame:
    # 1) JSON primero (varios intentos)
    last = None
    for _ in range(3):
        try:
            url, params, r = _try_json(id_, start=start)
            last = r
            if r.status_code == 200:
                return _parse_json(id_, r.json())
        except Exception:
            pass
        time.sleep(0.8)
    # 2) Fallback a CSV (varios intentos)
    for _ in range(3):
        try:
            url, params, r = _try_csv(id_, start=start)
            last = r
            if r.status_code == 200 and (r.content or b"") != b"":
                return _parse_csv(id_, r.content)
        except Exception:
            pass
        time.sleep(0.8)

    # Si llegamos acá, log de diagnóstico corto:
    status = getattr(last, "status_code", None)
    snippet = ""
    try:
        snippet = (last.text or "")[:280]
    except Exception:
        pass
    raise RuntimeError(f"Fallo al bajar {id_} (status={status}). URL={url} params={params} body[:280]={snippet!r}")

def main():
    try:
        frames = []
        for s in SERIES:
            print(f"• Bajando {s['id']} …", flush=True)
            df = fetch_series_resilient(s["id"])
            df["indicador"] = s["indicador"]
            df["titulo"]     = s["titulo"]
            df["unidades"]   = s["unidades"]
            df["fuente"]     = "DatosAR"
            frames.append(df)

        long_df = pd.concat(frames, ignore_index=True).sort_values(["indicador", "fecha"])
        long_df.to_parquet(OUT, index=False)
        print(f"✅ Guardado {OUT} ({len(long_df):,} filas)")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
