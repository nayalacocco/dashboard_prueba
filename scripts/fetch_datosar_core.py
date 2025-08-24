# scripts/fetch_datosar_core.py
from __future__ import annotations
import sys, time
from pathlib import Path
import io
import requests
import pandas as pd

OUT = Path("data/datosar_core_long.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

BASE = "https://apis.datos.gob.ar/series/api/series"

# Catálogo mínimo (IDs + metadatos para títulos/unidades)
SERIES = [
    {
        "id": "143.3_NO_PR_2004_A_21",
        "indicador": "emae_original",
        "titulo": "EMAE (base 2004=100)",
        "unidades": "Índice (2004=100)",
    },
    {
        "id": "148.3_INIVELNAL_DICI_M_26",
        "indicador": "ipc_nivel_general_nacional",
        "titulo": "IPC Nivel General (base dic-2016)",
        "unidades": "Índice",
    },
    {
        "id": "116.4_TCRZE_2015_D_36_4",
        "indicador": "tcrm_multilateral",
        "titulo": "Tipo de Cambio Real Multilateral (2015-12-17=100)",
        "unidades": "Índice (17-Dic-2015=100)",
    },
    {
        "id": "94.2_UVAD_D_0_0_10",
        "indicador": "uva_diario",
        "titulo": "UVA Diario (31-mar-2016=14,05)",
        "unidades": "Índice",
    },
    {
        "id": "145.3_INGNACUAL_DICI_M_38",
        "indicador": "ipc_variacion_mensual",
        "titulo": "IPC variación mensual (nacional)",
        "unidades": "Variación intermensual (%)",
    },
]

HDRS = {
    "User-Agent": "macro-core-datosar/1.0",
    "Accept": "text/csv,application/json",
}

def fetch_csv(id_: str, start="2000-01-01", retries=4, pause=0.8) -> pd.DataFrame:
    """Lee la serie por CSV (más fácil que JSON). Devuelve df con columnas: fecha, valor."""
    params = {
        "ids": id_,
        "format": "csv",
        "start_date": start,
    }
    last = None
    for k in range(retries):
        try:
            r = requests.get(BASE, params=params, headers=HDRS, timeout=60)
            last = r
            if r.status_code == 200 and r.content:
                df = pd.read_csv(io.BytesIO(r.content))
                # El CSV trae col 'indice_tiempo' + una col con el ID
                time_col = "indice_tiempo"
                if time_col not in df.columns or id_ not in df.columns:
                    raise RuntimeError("CSV inesperado (faltan columnas).")
                out = df[[time_col, id_]].rename(columns={time_col: "fecha", id_: "valor"})
                out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
                out["valor"] = pd.to_numeric(out["valor"], errors="coerce")
                out = out.dropna(subset=["fecha", "valor"])
                return out
        except Exception:
            pass
        time.sleep(pause)
    raise RuntimeError(f"Fallo al bajar {id_} (último status: {getattr(last,'status_code',None)})")

def main():
    rows = []
    for s in SERIES:
        print(f"• Bajando {s['id']} …", flush=True)
        df = fetch_csv(s["id"])
        df["indicador"] = s["indicador"]
        df["titulo"]     = s["titulo"]
        df["unidades"]   = s["unidades"]
        df["fuente"]     = "DatosAR"
        rows.append(df)

    long_df = pd.concat(rows, ignore_index=True).sort_values(["indicador","fecha"])
    OUT.write_bytes(b"") if OUT.exists() else None
    long_df.to_parquet(OUT, index=False)
    print(f"✅ Guardado {OUT} ({len(long_df):,} filas)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
