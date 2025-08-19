# bcra_utils.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# =========================
# Carga de datos (formato long)
# =========================

def _read_one_csv(path: Path) -> pd.DataFrame:
    """
    Intenta leer un CSV cualquiera del folder data/ y devolverlo en formato:
      fecha (datetime), descripcion (str), valor (float)
    Admite varias formas de columnas y normaliza.
    """
    df = pd.read_csv(path)
    # normalizar nombres
    df.columns = [c.strip().lower() for c in df.columns]

    # identificar columnas posibles
    # fecha: 'fecha' o 'date'
    fcol = None
    for c in df.columns:
        if c in ("fecha", "date"):
            fcol = c
            break

    # descripcion: 'descripcion'/'description'/'variable'/'serie'
    dcol = None
    for c in df.columns:
        if c in ("descripcion", "description", "variable", "serie", "series", "name"):
            dcol = c
            break

    # valor: 'valor'/'value'
    vcol = None
    for c in df.columns:
        if c in ("valor", "value"):
            vcol = c
            break

    # Caso: CSV “wide” (muchas columnas con series). Intentamos stackear.
    if fcol and not dcol and not vcol and len(df.columns) > 1:
        df = df.rename(columns={fcol: "fecha"})
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
        # columnas de series = todo menos fecha
        value_cols = [c for c in df.columns if c != "fecha"]
        long = df.melt(id_vars="fecha", value_vars=value_cols, var_name="descripcion", value_name="valor")
        long["valor"] = pd.to_numeric(long["valor"], errors="coerce")
        long = long.dropna(subset=["fecha", "valor"])
        return long[["fecha", "descripcion", "valor"]].sort_values("fecha")

    # Caso “long” ya bien formado
    if fcol and dcol and vcol:
        out = pd.DataFrame({
            "fecha": pd.to_datetime(df[fcol], errors="coerce", utc=True).dt.tz_localize(None),
            "descripcion": df[dcol].astype(str),
            "valor": pd.to_numeric(df[vcol], errors="coerce"),
        })
        out = out.dropna(subset=["fecha", "valor"])
        return out.sort_values("fecha")

    # Último intento: si aparece 'fecha' y exactamente 2 columnas, usamos la otra como valor
    if fcol and len(df.columns) == 2:
        other = [c for c in df.columns if c != fcol][0]
        out = pd.DataFrame({
            "fecha": pd.to_datetime(df[fcol], errors="coerce", utc=True).dt.tz_localize(None),
            "descripcion": Path(path).stem,
            "valor": pd.to_numeric(df[other], errors="coerce"),
        })
        out = out.dropna(subset=["fecha", "valor"])
        return out.sort_values("fecha")

    # Si no pudimos interpretar, devolvemos vacío para ignorarlo
    return pd.DataFrame(columns=["fecha", "descripcion", "valor"])


def load_bcra_long(data_dir: str | Path = "data") -> pd.DataFrame:
    """
    Carga TODOS los CSV de `data/` y devuelve un DF long con columnas:
      fecha (datetime), descripcion (str), valor (float)
    """
    data_dir = Path(data_dir)
    frames: List[pd.DataFrame] = []
    for p in sorted(data_dir.glob("*.csv")):
        try:
            frames.append(_read_one_csv(p))
        except Exception:
            # Ignoramos CSVs rotos; evitamos romper toda la app
            continue
    if not frames:
        return pd.DataFrame(columns=["fecha", "descripcion", "valor"])
    df = pd.concat(frames, ignore_index=True)
    # limpieza final
    df = df.dropna(subset=["fecha", "valor"])
    df["descripcion"] = df["descripcion"].astype(str)
    df = df.sort_values(["descripcion", "fecha"]).reset_index(drop=True)
    return df


# =========================
# Helpers de búsqueda / resample
# =========================

def _norm(s: str) -> str:
    return str(s).strip().lower()


def find_first(candidates: Iterable[str], *tokens: str) -> Optional[str]:
    """
    Devuelve el primer string en `candidates` que contenga TODOS los tokens (insensible a mayúsculas).
    """
    toks = [_norm(t) for t in tokens if t]
    for c in candidates:
        sc = _norm(c)
        if all(t in sc for t in toks):
            return c
    return None


def resample_series(s: pd.Series, freq: str = "D", how: str = "last") -> pd.Series:
    """
    Re-muestrea una serie (index datetime) a 'D' o 'M', usando 'last' por default.
    """
    if s.empty:
        return s
    if how not in ("last", "mean", "sum", "first"):
        how = "last"
    if freq.upper().startswith("M"):
        r = s.resample("M")
    else:
        r = s.resample("D")
    if how == "mean":
        out = r.mean()
    elif how == "sum":
        out = r.sum()
    elif how == "first":
        out = r.first()
    else:
        out = r.last()
    return out.dropna()


# =========================
# KPIs
# =========================

def compute_kpis(
    serie_full: pd.Series,
    serie_vis: pd.Series,
    d_fin: Optional[pd.Timestamp] = None
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Devuelve (MoM, YoY, Δperiodo) en %.
    - MoM y YoY se calculan SIEMPRE con la serie mensual del histórico (fin de mes).
    - Δperiodo es entre primer y último dato de la serie visible (con su frecuencia actual).
    - d_fin es opcional; si no viene, se toma del último índice visible.
    """
    # Normalizaciones
    sf = serie_full.copy()
    sv = serie_vis.copy()
    sf = pd.to_numeric(sf, errors="coerce").dropna()
    sv = pd.to_numeric(sv, errors="coerce").dropna()

    if sf.index.tz is not None:
        sf.index = sf.index.tz_localize(None)
    if sv.index.tz is not None:
        sv.index = sv.index.tz_localize(None)

    # MoM / YoY con mensual del histórico
    m = sf.resample("M").last().dropna()

    # elegimos d_fin
    if d_fin is None:
        if not sv.empty:
            d_fin = sv.index.max()
        elif not m.empty:
            d_fin = m.index.max()
        else:
            d_fin = None

    # calcular MoM
    mom = None
    if len(m) >= 2:
        m_cut = m.loc[:d_fin] if d_fin is not None else m
        if len(m_cut) >= 2:
            mom = float((m_cut.iloc[-1] / m_cut.iloc[-2] - 1.0) * 100.0)

    # calcular YoY
    yoy = None
    if not m.empty:
        # último mensual <= d_fin
        last_idx = m.index[m.index <= d_fin][-1] if d_fin is not None else m.index[-1]
        ref_date = last_idx - pd.DateOffset(years=1)
        # buscamos el mensual “previo o igual” a ref_date
        m_ref = m.loc[:ref_date]
        if len(m_ref) > 0:
            base = m_ref.iloc[-1]
            if base not in (0, None, np.nan):
                yoy = float((m.loc[last_idx] / base - 1.0) * 100.0)

    # Δ en el período (visible)
    d_per = None
    if len(sv) >= 2:
        first, last = sv.iloc[0], sv.iloc[-1]
        if first not in (0, None, np.nan):
            d_per = float((last / first - 1.0) * 100.0)

    return mom, yoy, d_per


# =========================
# Gobiernos (para select)
# =========================

@dataclass(frozen=True)
class Govt:
    label: str
    start: str
    end: Optional[str]  # None = “hasta hoy”

def list_governments() -> list[Govt]:
    return [
        Govt("Néstor Kirchner (2003–2007)", "2003-05-25", "2007-12-10"),
        Govt("Cristina Fernández I (2007–2011)", "2007-12-10", "2011-12-10"),
        Govt("Cristina Fernández II (2011–2015)", "2011-12-10", "2015-12-10"),
        Govt("Mauricio Macri (2015–2019)", "2015-12-10", "2019-12-10"),
        Govt("Alberto Fernández (2019–2023)", "2019-12-10", "2023-12-10"),
        Govt("Javier Milei (2023– )", "2023-12-10", None),
    ]


# =========================
# Ticks “lindos” y escala alineada al eje derecho
# =========================

def nice_ticks(vmin: float, vmax: float, max_ticks: int = 7) -> list[float]:
    """
    Genera una secuencia de ticks 'lindos' (1/2/2.5/5 * 10^n) cubriendo [vmin, vmax].
    Útil para el eje izquierdo.
    """
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return []
    if vmin == vmax:
        if vmin == 0:
            return [0.0]
        span = abs(vmin) * 0.1
        vmin, vmax = vmin - span, vmin + span

    span = vmax - vmin
    if span <= 0:
        return []

    raw = span / max(1, max_ticks)
    mag = 10 ** np.floor(np.log10(raw))

    # “nice steps”
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = m * mag
        if span / step <= max_ticks:
            break

    start = np.floor(vmin / step) * step
    end   = np.ceil(vmax / step) * step
    ticks = np.arange(start, end + 0.5 * step, step)

    ticks = ticks[(ticks >= vmin - 1e-12) & (ticks <= vmax + 1e-12)]
    return ticks.tolist()


def aligned_right_ticks_round(left_ticks: list[float], rmin: float, rmax: float) -> tuple[list[float], tuple[float, float]]:
    """
    Dado un conjunto de ticks del eje izquierdo (left_ticks) y el rango real del eje derecho (rmin..rmax),
    devuelve (right_ticks, (r0, r1)) tal que:
      - right_ticks cae exactamente sobre las líneas de grilla del eje izquierdo (misma cantidad de ticks)
      - r0..r1 son los límites sugeridos del eje derecho
    La idea es que las líneas de grilla visuales queden alineadas y el eje derecho muestre números “redondos”.
    """
    if not left_ticks or rmin is None or rmax is None or not np.isfinite(rmin) or not np.isfinite(rmax):
        return [], (rmin, rmax)

    l0, l1 = float(left_ticks[0]), float(left_ticks[-1])
    if l1 == l0 or rmax == rmin:
        return [], (rmin, rmax)

    span_l = (l1 - l0)
    span_r = (rmax - rmin)

    # Pequeño pad para que el último tick no quede pegado al borde
    pad = 0.02 * span_r
    r0, r1 = rmin - pad, rmax + pad
    scale = (r1 - r0) / span_l

    rticks = [r0 + (lt - l0) * scale for lt in left_ticks]
    return rticks, (rticks[0], rticks[-1])
