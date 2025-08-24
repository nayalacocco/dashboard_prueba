# scripts/fetch_datosar_core.py
from __future__ import annotations
import sys, time
from pathlib import Path
import requests
import pandas as pd

OUT = Path("data/datosar_core_long.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

BASE = "https://apis.datos.gob.ar/series/api/series"

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
    "User-Agent": "macro-core-datosar/1.1",
    "Accept": "application/json",
}

def fetch_series_json(id_: str, start="2000-01-01", retries=4, pause=0.8) -> pd.DataFrame:
    """
    Usa el formato JSON de Series-Tiempo:
      - 'columns': metadatos por columna
      - 'data': filas con valores en el mismo orden que 'columns'
    Devuelve DataFrame con columnas: fecha, valor
    """
    params = {
        "ids": id_,
        "format": "json",
        "start_date": start,
        "limit": 500000,   # grande para no paginar
    }
    last = None
    for _ in range(retries):
        try:
            r = requests.get(BASE, params=params, headers=HDRS, timeout=60)
            last = r
            if r.status_code == 200:
                js = r.json()
                cols = js.get("columns") or []
                data = js.get("data") or []
                if not cols or not data:
                    raise RuntimeError("JSON sin columns/data.")

                # Ubico índices de tiempo y de la serie pedida
                t_idx = None
                v_idx = None
                for i, c in enumerate(cols):
                    # c es dict: {'field': 't', 'title': 'indice_tiempo', ...} o {'field': '143.3_...'}
                    field = c.get("field") or ""
                    if field in ("t", "indice_tiempo", "time"):
                        t_idx = i
                    if field == id_:
                        v_idx = i
                # Fallback: a veces 'field' de la serie viene en 'id'
                if v_idx is None:
                    for i, c in enumerate(cols):
                        if c.get("id") == id_:
                            v_idx = i

                if t_idx is None or v_idx is None:
                    raise RuntimeError(f"No pude localizar columnas (t_idx={t_idx}, v_idx={v_idx}).")

                rows = []
                for row in data:
                    # cada row es una lista con valores alineados a 'columns'
                    ts = row[t_idx]
                    val = row[v_idx]
                    rows.append({"fecha": ts, "valor": val})

                df = pd.DataFrame(rows)
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
                df = df.dropna(subset=["fecha", "valor"])
                return df
        except Exception:
            pass
        time.sleep(pause)
    raise RuntimeError(f"Fallo al bajar {id_} (último status: {getattr(last, 'status_code', None)})")

def main():
    try:
        frames = []
        for s in SERIES:
            print(f"• Bajando {s['id']} …", flush=True)
            df = fetch_series_json(s["id"])
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
