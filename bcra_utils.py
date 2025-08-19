# bcra_utils.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

DATA_DIR = Path("data")

# -------------------------------------------------------------------
# Helpers básicos
# -------------------------------------------------------------------
def _parse_date_col(s: pd.Series) -> pd.DatetimeIndex:
    """Convierte una columna a datetime (UTC naive) y la ordena."""
    out = pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)
    return out

def _coerce_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _load_csv_safe(p: Path) -> Optional[pd.DataFrame]:
    try:
        return pd.read_csv(p)
    except Exception:
        return None

# -------------------------------------------------------------------
# Carga de datos (larga: fecha, descripcion, valor)
# -------------------------------------------------------------------
def load_bcra_long() -> pd.DataFrame:
    """
    Devuelve un DataFrame largo con columnas: ['fecha', 'descripcion', 'valor'].

    - Si existe data/series_monetarias.csv la usa como fuente principal.
    - Si no, intenta data/base_monetaria.csv y le asigna una descripción genérica.
    - Si encuentra varios .csv en data/ que ya tengan esas 3 columnas, los concatena.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Preferimos un consolidado si existe
    p_main = DATA_DIR / "series_monetarias.csv"
    if p_main.exists():
        df = pd.read_csv(p_main)
        df = df.rename(
            columns={
                "Fecha": "fecha",
                "fecha": "fecha",
                "Descripcion": "descripcion",
                "descripcion": "descripcion",
                "valor": "valor",
                "Valor": "valor",
            }
        )
        need = {"fecha", "descripcion", "valor"}
        if need.issubset(set(df.columns)):
            df["fecha"] = _parse_date_col(df["fecha"])
            df["valor"] = _coerce_numeric(df["valor"])
            df = df.dropna(subset=["fecha", "valor"]).sort_values("fecha")
            return df[["fecha", "descripcion", "valor"]]

    # 2) Fallback a base_monetaria.csv si está
    p_base = DATA_DIR / "base_monetaria.csv"
    if p_base.exists():
        dfb = pd.read_csv(p_base)
        # admitir nombres varios
        # (fecha, valor) o (Fecha, Valor)
        c_fecha = next((c for c in dfb.columns if c.lower().startswith("fecha")), None)
        c_valor = next((c for c in dfb.columns if c.lower().startswith("valor")), None)
        if c_fecha and c_valor:
            out = pd.DataFrame(
                {
                    "fecha": _parse_date_col(dfb[c_fecha]),
                    "valor": _coerce_numeric(dfb[c_valor]),
                }
            )
            out["descripcion"] = "Base monetaria - Total (en millones de pesos)"
            out = out.dropna(subset=["fecha", "valor"]).sort_values("fecha")
            return out[["fecha", "descripcion", "valor"]]

    # 3) Como último recurso, escanear otros CSVs que ya tengan las 3 columnas
    rows = []
    for p in DATA_DIR.glob("*.csv"):
        if p.name in {"series_monetarias.csv", "base_monetaria.csv"}:
            continue
        tmp = _load_csv_safe(p)
        if tmp is None:
            continue
        cols = {c.lower(): c for c in tmp.columns}
        if {"fecha", "descripcion", "valor"}.issubset(set(cols.keys())):
            t = tmp.rename(columns={cols["fecha"]: "fecha", cols["descripcion"]: "descripcion", cols["valor"]: "valor"})
            t["fecha"] = _parse_date_col(t["fecha"])
            t["valor"] = _coerce_numeric(t["valor"])
            t = t.dropna(subset=["fecha", "valor"]).sort_values("fecha")
            rows.append(t[["fecha", "descripcion", "valor"]])

    if rows:
        return pd.concat(rows, ignore_index=True).sort_values(["descripcion", "fecha"])

    # No encontramos nada util
    return pd.DataFrame(columns=["fecha", "descripcion", "valor"])


# -------------------------------------------------------------------
# Búsqueda “inteligente” de descripciones
# -------------------------------------------------------------------
def find_first(candidates: Iterable[str], *needles: str) -> Optional[str]:
    """
    Devuelve el primer elemento de candidates que contenga TODOS los `needles`
    (case-insensitive). Si no encuentra, None.
    """
    neds = [n.lower() for n in needles]
    for c in candidates:
        lc = c.lower()
        if all(n in lc for n in neds):
            return c
    return None


# -------------------------------------------------------------------
# Resampling de series
# -------------------------------------------------------------------
def resample_series(s: pd.Series, freq: str = "D", how: str = "last") -> pd.Series:
    """
    Resamplea una Serie con índice datetime.
    - freq: 'D' (diaria), 'M' (mensual fin de mes), etc.
    - how: 'last' (default), 'mean', 'sum'...
    """
    if s.empty:
        return s
    s = s.sort_index()
    if how == "mean":
        return s.resample(freq).mean()
    if how == "sum":
        return s.resample(freq).sum()
    # default: last
    return s.resample(freq).last()


# -------------------------------------------------------------------
# KPIs (MoM, YoY y Δ del período visible)
# -------------------------------------------------------------------
def compute_kpis(
    serie_full: pd.Series,
    serie_visible: pd.Series,
    d_fin: pd.Timestamp | pd.Timestamp
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    - MoM: último fin de mes vs mes previo (sobre la serie histórica).
    - YoY: último fin de mes vs igual mes del año previo (si hay historia).
    - Δ período: primer vs último dato de lo visible (respeta frecuencia actual).
    Devuelve porcentajes (0..100) o None.
    """
    # Asegurar índice datetime ordenado
    if not isinstance(serie_full.index, pd.DatetimeIndex):
        raise ValueError("serie_full debe tener DatetimeIndex")
    if not isinstance(serie_visible.index, pd.DatetimeIndex):
        raise ValueError("serie_visible debe tener DatetimeIndex")

    # Serie mensual (histórico) para MoM/YoY
    m = serie_full.sort_index().resample("M").last().dropna()
    mom = yoy = None

    if len(m) >= 2:
        # último ≤ d_fin
        m_lim = m.loc[:pd.to_datetime(d_fin)]
        if len(m_lim) >= 2:
            mom = (m_lim.iloc[-1] / m_lim.iloc[-2] - 1.0) * 100.0

    if len(m) >= 13:
        last_idx = m.index[m.index <= pd.to_datetime(d_fin)]
        if len(last_idx) > 0:
            last_idx = last_idx[-1]
            ref = last_idx - pd.DateOffset(years=1)
            base = m.loc[:ref]
            if len(base) > 0 and base.iloc[-1] != 0:
                yoy = (m.loc[last_idx] / base.iloc[-1] - 1.0) * 100.0

    # Δ del período visible (con frecuencia del gráfico)
    s = serie_visible.dropna()
    d_per = None
    if len(s) >= 2 and s.iloc[0] != 0:
        d_per = (s.iloc[-1] / s.iloc[0] - 1.0) * 100.0

    return _safe_float(mom), _safe_float(yoy), _safe_float(d_per)

def _safe_float(x) -> Optional[float]:
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


# -------------------------------------------------------------------
# Alineación de grilla para doble eje Y
# -------------------------------------------------------------------
def unify_secondary_y_ticks(
    y0_min: float, y0_max: float,
    y1_min: float, y1_max: float,
    target_steps: int = 5
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Dado el rango real (min,max) de cada eje, genera (min, max, dtick)
    para que las líneas de grilla queden alineadas.
    Retorna: (eje_izq_config, eje_der_config), cada uno como (min, max, dtick).

    - target_steps: cantidad de divisiones de referencia (aprox.) para el eje izquierdo.
    """
    if not np.isfinite([y0_min, y0_max, y1_min, y1_max]).all():
        # fallback tonto
        return (y0_min, y0_max, None), (y1_min, y1_max, None)

    # “nice ticks” para eje izquierdo
    span0 = max(1e-9, y0_max - y0_min)
    raw_step0 = span0 / target_steps
    step0 = _nice_step(raw_step0)
    y0_min_a = np.floor(y0_min / step0) * step0
    y0_max_a = np.ceil(y0_max / step0) * step0

    # hacemos coincidir la cantidad de pasos en el derecho
    steps = max(1, int(round((y0_max_a - y0_min_a) / step0)))
    span1 = max(1e-9, y1_max - y1_min)
    raw_step1 = span1 / steps
    step1 = _nice_step(raw_step1)
    y1_min_a = np.floor(y1_min / step1) * step1
    y1_max_a = y1_min_a + steps * step1

    return (y0_min_a, y0_max_a, step0), (y1_min_a, y1_max_a, step1)

def _nice_step(x: float) -> float:
    """
    Redondea un paso a una “escala bonita”: 1, 2, 2.5, 5, 10 * 10^n
    """
    if x <= 0:
        return 1.0
    exp = np.floor(np.log10(x))
    f = x / (10 ** exp)
    for m in [1, 2, 2.5, 5, 10]:
        if f <= m:
            return m * (10 ** exp)
    return 10 ** (exp + 1)
