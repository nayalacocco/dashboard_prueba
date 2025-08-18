# bcra_utils.py
from __future__ import annotations
import os
import glob
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd


# =========================================================
#  CARGA DE DATOS
# =========================================================

DATA_DIR = Path("data")

def _read_csv_any(path: Path) -> pd.DataFrame:
    """Lee un CSV con columnas al menos ['fecha','valor'] y opcional 'descripcion'."""
    df = pd.read_csv(path)
    # normalizamos nombres
    cols = {c: c.strip().lower() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    # fecha
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
    else:
        # si el archivo no tiene 'fecha', no sirve
        return pd.DataFrame(columns=["fecha", "descripcion", "valor"])

    # valor
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    else:
        # puede venir una única columna numérica además de fecha
        num_cols = [c for c in df.columns if c != "fecha"]
        if len(num_cols) == 1:
            df.rename(columns={num_cols[0]: "valor"}, inplace=True)
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        else:
            return pd.DataFrame(columns=["fecha", "descripcion", "valor"])

    # descripcion
    if "descripcion" not in df.columns or df["descripcion"].isna().all():
        # si no vino, inferimos por nombre de archivo
        desc = path.stem.replace("_", " ").strip().title()
        df["descripcion"] = desc

    return df[["fecha", "descripcion", "valor"]]


def load_bcra_long() -> pd.DataFrame:
    """
    Devuelve un DataFrame long: columnas ['fecha','descripcion','valor'].
    Busca primero 'data/bcra_long.csv'. Si no existe, concatena todos los CSVs
    dentro de 'data' y 'data/series' que contengan al menos 'fecha' y 'valor'.
    """
    paths: list[Path] = []

    # preferimos un archivo consolidado si existe
    long_csv = DATA_DIR / "bcra_long.csv"
    if long_csv.exists():
        paths.append(long_csv)
    else:
        # sino, juntamos todo lo que esté en data/ y data/series/
        for p in sorted(glob.glob(str(DATA_DIR / "*.csv"))):
            paths.append(Path(p))
        series_dir = DATA_DIR / "series"
        if series_dir.exists():
            for p in sorted(glob.glob(str(series_dir / "*.csv"))):
                paths.append(Path(p))

    frames = []
    for p in paths:
        try:
            df = _read_csv_any(p)
            if not df.empty:
                frames.append(df)
        except Exception:
            # ignoramos archivos que no cumplan el formato
            continue

    if not frames:
        # como mínimo intentamos base_monetaria.csv
        bm = DATA_DIR / "base_monetaria.csv"
        if bm.exists():
            df = _read_csv_any(bm)
            return df.sort_values("fecha").reset_index(drop=True)
        return pd.DataFrame(columns=["fecha", "descripcion", "valor"])

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["fecha"]).sort_values("fecha").reset_index(drop=True)
    return out


# =========================================================
#  HELPERS
# =========================================================

def find_first(candidates: Iterable[str], *keywords: str) -> Optional[str]:
    """
    Devuelve el primer string en 'candidates' que contenga todos los 'keywords'
    (insensible a mayúsculas/minúsculas). Si no encuentra, None.
    """
    kws = [k.lower() for k in keywords if k]
    for s in candidates:
        s_l = (s or "").lower()
        if all(kw in s_l for kw in kws):
            return s
    return None


def resample_series(s: pd.Series, freq: str = "D", how: str = "last") -> pd.Series:
    """
    Re-muestrea una serie temporal:
      - freq="D" diaria, "M" mensual (fin de mes), etc.
      - how="last" (por defecto) o "mean"/"sum" según convenga.
    """
    if s is None or len(s) == 0:
        return s
    s = pd.Series(s).sort_index()
    if freq.upper().startswith("M"):
        rule = "M"
    else:
        rule = freq
    if how == "mean":
        return s.resample(rule).mean()
    if how == "sum":
        return s.resample(rule).sum()
    return s.resample(rule).last()


# =========================================================
#  TICKS “LINDOS” Y EJE DERECHO ALINEADO
# =========================================================

def _nice_step(span: float, max_ticks: int = 7) -> float:
    """
    Devuelve un “step” agradable (1, 2, 2.5, 5 × 10^n) para cubrir 'span' con ~max_ticks.
    """
    if span <= 0 or not np.isfinite(span):
        return 1.0
    raw = span / max(max_ticks, 2)
    power = 10 ** np.floor(np.log10(raw))
    for mult in [1, 2, 2.5, 5, 10]:
        step = mult * power
        if span / step <= max_ticks:
            return float(step)
    return float(10 * power)


def nice_ticks(vmin: float, vmax: float, max_ticks: int = 7) -> list[float]:
    """
    Genera ticks “redondos” para el eje (incluye bordes expandidos si hace falta).
    """
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return []
    if vmin == vmax:
        if vmin == 0:
            return [0]
        return [vmin, vmax]
    lo, hi = (float(vmin), float(vmax)) if vmin < vmax else (float(vmax), float(vmin))
    span = hi - lo
    step = _nice_step(span, max_ticks=max_ticks)
    start = np.floor(lo / step) * step
    end = np.ceil(hi / step) * step
    ticks = list(np.arange(start, end + 0.5 * step, step))
    return ticks


def aligned_right_ticks_round(
    left_ticks: list[float],
    right_min: float,
    right_max: float,
) -> Tuple[list[float], Tuple[float, float]]:
    """
    Alinea los ticks del eje derecho con las líneas de grilla del izquierdo:

    1) Se calcula el rango lineal equivalente para el eje derecho que mapea
       [min(left_ticks), max(left_ticks)] -> [right_min, right_max].
    2) Se “redondea” el rango resultante a números lindos para evitar etiquetas feas.
    3) Devuelve (right_ticks_alineados, (r0, r1)).

    Nota: la alineación se logra transformando cada tick izquierdo a la escala
    derecha de forma lineal; luego se redondea el rango final para que las
    etiquetas no sean monstruosas.
    """
    if not left_ticks or not np.isfinite(right_min) or not np.isfinite(right_max):
        return [], (right_min, right_max)

    l0, l1 = float(min(left_ticks)), float(max(left_ticks))
    if l0 == l1 or right_min == right_max:
        # no hay nada que alinear; devolvemos ticks “lindos” por la derecha
        rticks = nice_ticks(right_min, right_max)
        return rticks, (rticks[0], rticks[-1]) if rticks else (right_min, right_max)

    # mapeo lineal y = a*x + b
    a = (right_max - right_min) / (l1 - l0)
    b = right_min - a * l0

    raw_rticks = [a * x + b for x in left_ticks]
    rmin_mapped, rmax_mapped = min(raw_rticks), max(raw_rticks)

    # “redondeamos” el rango derecho
    rticks_rounded = nice_ticks(rmin_mapped, rmax_mapped)
    if not rticks_rounded:
        return raw_rticks, (rmin_mapped, rmax_mapped)

    # Ahora volvemos a alinear los ticks a la grilla izquierda pero dentro del rango redondeado
    # Recalculamos a y b con la nueva caja (misma pendiente, distinto intercepto)
    r0, r1 = rticks_rounded[0], rticks_rounded[-1]
    a2 = (r1 - r0) / (l1 - l0)
    b2 = r0 - a2 * l0
    right_ticks_aligned = [a2 * x + b2 for x in left_ticks]

    return right_ticks_aligned, (r0, r1)


# =========================================================
#  MÉTRICAS: MoM / YoY / Δ EN EL PERÍODO
# =========================================================

def _pct(a: float, b: float) -> Optional[float]:
    try:
        if b == 0 or not np.isfinite(a) or not np.isfinite(b):
            return None
        return (a / b - 1.0) * 100.0
    except Exception:
        return None


def compute_kpis(
    serie_full: pd.Series,
    serie_visible: pd.Series,
    end_date: pd.Timestamp,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Calcula:
      - MoM: variación mensual (último dato mensual vs mes previo) usando SIEMPRE el histórico mensual (fin de mes).
      - YoY: variación interanual (último dato mensual vs mismo período de hace 12 meses), mensual fin de mes.
      - Δ en el período: variación entre el primer y el último dato del rango visible,
        respetando la frecuencia que esté usando el gráfico (diaria o mensual).
    Retorna (mom, yoy, d_period) en %, o None si no hay datos suficientes.
    """
    if serie_full is None or len(serie_full) == 0:
        return None, None, None

    # Asegurar series limpias/ordenadas
    s_full = pd.Series(serie_full).sort_index().dropna()
    s_vis  = pd.Series(serie_visible).sort_index().dropna()

    # ---- MoM / YoY sobre mensual (fin de mes) del histórico completo ----
    m = s_full.resample("M").last().dropna()
    if len(m):
        m = m.loc[:end_date]  # evitar mirar futuro si end_date < último

    mom = None
    yoy = None

    if len(m) >= 2:
        last = m.iloc[-1]
        prev = m.iloc[-2]
        mom = _pct(last, prev)

    if len(m) >= 13:
        last = m.iloc[-1]
        ref_date = m.index[-1] - pd.DateOffset(years=1)
        hist = m.loc[:ref_date]
        if len(hist):
            yoy = _pct(last, hist.iloc[-1])

    # ---- Δ en el período (sobre lo visible y frecuencia actual) ----
    d_period = None
    if len(s_vis) >= 2:
        d_period = _pct(s_vis.iloc[-1], s_vis.iloc[0])

    return mom, yoy, d_period
