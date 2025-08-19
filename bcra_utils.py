# bcra_utils.py
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
CSV_MAIN = DATA_DIR / "base_monetaria.csv"      # histórico largo que ya guardamos
JSON_CAT  = DATA_DIR / "catalogo_monetarias.json"  # opcional, si lo guardaste

def load_bcra_long() -> pd.DataFrame:
    """
    Lee el CSV 'base_monetaria.csv' (formato largo: fecha, valor, descripcion)
    y adjunta series derivadas útiles (BM/Reservas).
    """
    df = pd.read_csv(CSV_MAIN)
    # normalizaciones
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_localize(None)
    # aseguramos float
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["fecha", "valor", "descripcion"]).sort_values("fecha")

    # Adjuntamos derivadas
    df = attach_derived(df)
    return df

# ------------------------------
# Helpers de búsqueda de series
# ------------------------------
def _slug(s: str) -> str:
    return (s or "").lower()

def find_first(lista: list[str], *palabras: str) -> str | None:
    """
    Devuelve el primer label de 'lista' que contenga todas las 'palabras'
    (match case-insensitive).
    """
    must = [p.lower() for p in palabras]
    for x in lista:
        lx = x.lower()
        if all(p in lx for p in must):
            return x
    return None

def resample_series(s: pd.Series, freq: str = "D", how: str = "last") -> pd.Series:
    if s.empty:
        return s
    if how == "last":
        return s.resample(freq).last()
    if how == "mean":
        return s.resample(freq).mean()
    return s.resample(freq).last()

# ------------------------------
# Derivadas
# ------------------------------
def attach_derived(df_long: pd.DataFrame) -> pd.DataFrame:
    """
    A partir del largo (fecha, valor, descripcion), crea:
      • BM/Reservas (pesos por USD)  = [Base monetaria (M$)] / [Reservas (MUSD)]
    y lo apendea al largo original.
    """
    if df_long.empty:
        return df_long

    # Pasamos a ancho para combinar por fecha
    wide = df_long.pivot_table(index="fecha", columns="descripcion", values="valor", aggfunc="last")

    # Identificamos columnas clave
    cols = wide.columns.tolist()
    base = find_first(cols, "base", "monetaria", "millones de pesos")
    reservas = find_first(cols, "reservas", "millones de dólares") or find_first(cols, "reservas", "usd")

    derived_frames = []

    if base and reservas:
        # Ambas están en millones → el cociente queda en “pesos por USD”
        serie = (wide[base] / wide[reservas]).rename("Benchmark CCL (BM/Reservas, $ por USD) – derivada")
        d = serie.dropna().reset_index().rename(columns={0: "valor"})
        d["descripcion"] = "Benchmark CCL (BM/Reservas, $ por USD) – derivada"
        d = d[["fecha", "valor", "descripcion"]]
        derived_frames.append(d)

    if not derived_frames:
        return df_long

    df_der = pd.concat(derived_frames, ignore_index=True)
    out = pd.concat([df_long, df_der], ignore_index=True).sort_values("fecha")
    return out

# ------------------------------
# KPIs centralizados
# ------------------------------
def compute_kpis(serie_full: pd.Series, serie_visible: pd.Series, d_fin) -> tuple[float | None, float | None, float | None]:
    """
    Devuelve (MoM, YoY, Delta periodo visible).
    - MoM/YoY se calculan siempre sobre fin de mes del histórico completo (robusto).
    - Δ periodo: primer vs último punto del rango visible (con frecuencia actual).
    """
    if serie_full.empty:
        return None, None, None

    m = serie_full.resample("M").last().dropna()
    # ultimo <= d_fin
    m = m.loc[:d_fin] if len(m) else m

    mom = None
    if len(m) >= 2:
        mom = (m.iloc[-1] / m.iloc[-2] - 1.0) * 100.0

    yoy = None
    if len(m) >= 13:
        last_idx = m.index[-1]
        ref = last_idx - pd.DateOffset(years=1)
        if ref in m.index and m.loc[ref] != 0:
            yoy = (m.loc[last_idx] / m.loc[ref] - 1.0) * 100.0

    d_per = None
    s = serie_visible.dropna()
    if len(s) >= 2 and s.iloc[0] != 0:
        d_per = (s.iloc[-1] / s.iloc[0] - 1.0) * 100.0

    return mom, yoy, d_per
