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
    {"id": "143.3_NO_PR_2004_A_21",  "indicador": "emae_original",           "titulo": "EMAE (base 2004=100)",                 "unidades": "Índice (2004=100)"},
    {"id": "148.3_INIVELNAL_DICI_M_26","indicador": "ipc_nivel_general",     "titulo": "IPC Nivel General (base dic-2016)",   "unidades": "Índice"},
    {"id": "116.4_TCRZE_2015_D_36_4","indicador": "tcrm_multilateral",        "titulo": "TCRM (2015-12-17=100)",               "unidades": "Índice"},
    {"id": "94.2_UVAD_D_0_0_10",     "indicador": "uva_diario",               "titulo": "UVA Diario (31/03/2016=14,05)",       "unidades": "Índice"},
    {"id": "145.3_INGNACUAL_DICI_M_38","indicador": "ipc_variacion_mensual", "titulo": "IPC variación mensual (nacional)",    "unidades": "Variación intermensual (%)"},
]

HDRS = {"User-Agent": "macro-core-datosar/1.3"}

MAX_LIMIT = 5000  # límite real del API

def _get_json(id_: str, start="2000-01-01", offset=0) -> requests.Response:
    params = {"ids": id_, "format": "json", "start_date": start, "limit": MAX_LIMIT, "offset": offset}
    return requests.get(BASE, params=params, headers=HDRS, timeout=60)

def _get_csv(id_: str, start="2000-01-01", offset=0) -> requests.Response:
    params = {"ids": id_, "format": "csv", "start_date": start, "limit": MAX_LIMIT, "offset": offset}
    return requests.get(BASE, params=params, headers={"User-Agent": HDRS["User-Agent"], "Accept": "text/csv"}, timeout=60)

def _parse_json_payload(id_: str, payload: dict) -> pd.DataFrame:
    cols = payload.get("columns") or []
    data = payload.get("data") or []
    if not cols or not data:
        return pd.DataFrame()

    # ubicamos columnas
    t_idx = None; v_idx = None
    for i, c in enumerate(cols):
        field = (c.get("field") or "").strip()
        if field in ("t", "indice_tiempo", "time"): t_idx = i
        if field == id_: v_idx = i
    if v_idx is None:
        for i, c in enumerate(cols):
            if (c.get("id") or "").strip() == id_:
                v_idx = i; break
    if t_idx is None or v_idx is None:
        return pd.DataFrame()

    rows = [{"fecha": row[t_idx], "valor": row[v_idx]} for row in data]
    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha", "valor"])

def _parse_csv_content(id_: str, content: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content))
    if df.empty:
        return df
    # fecha
    date_col = next((c for c in ("indice_tiempo","t","time","fecha") if c in df.columns), df.columns[0])
    # valor
    value_col = id_ if id_ in df.columns else None
    if value_col is None:
        for c in df.columns:
            if c != date_col:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        num_cols = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols: return pd.DataFrame()
        value_col = num_cols[0]

    out = df[[date_col, value_col]].rename(columns={date_col:"fecha", value_col:"valor"})
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    out["valor"] = pd.to_numeric(out["valor"], errors="coerce")
    return out.dropna(subset=["fecha","valor"])

def fetch_series_paged(id_: str, start="2000-01-01") -> pd.DataFrame:
    """Paginado (limit=5000) con JSON y fallback a CSV."""
    frames = []
    offset = 0
    use_csv = False

    while True:
        try:
            if not use_csv:
                r = _get_json(id_, start=start, offset=offset)
                if r.status_code == 200:
                    df = _parse_json_payload(id_, r.json())
                else:
                    # si devuelve 400 por limit u otro, probamos CSV
                    use_csv = True
                    continue
            if use_csv:
                r = _get_csv(id_, start=start, offset=offset)
                if r.status_code != 200:
                    raise RuntimeError(f"CSV status={r.status_code}, body[:200]={r.text[:200]!r}")
                df = _parse_csv_content(id_, r.content)

            if df.empty:
                break
            frames.append(df)
            # si llegó una página incompleta, no hay más
            if len(df) < MAX_LIMIT:
                break
            offset += MAX_LIMIT
            time.sleep(0.4)  # ser amable
        except Exception as e:
            raise RuntimeError(f"{id_}: fallo en página offset={offset}: {e}") from e

    if not frames:
        raise RuntimeError(f"{id_}: sin datos")
    return pd.concat(frames, ignore_index=True)

def main():
    try:
        frames = []
        for s in SERIES:
            print(f"• Bajando {s['id']} …", flush=True)
            df = fetch_series_paged(s["id"])
            df["indicador"] = s["indicador"]
            df["titulo"]     = s["titulo"]
            df["unidades"]   = s["unidades"]
            df["fuente"]     = "DatosAR"
            frames.append(df)

        long_df = pd.concat(frames, ignore_index=True).sort_values(["indicador","fecha"])
        long_df.to_parquet(OUT, index=False)
        print(f"✅ Guardado {OUT} ({len(long_df):,} filas)")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
