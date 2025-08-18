from pathlib import Path
import pandas as pd
import numpy as np
import unicodedata

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

def load_bcra_long():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])

def load_catalog():
    return pd.read_json(CAT_JSON)

def norm(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")
    return s.lower()

def find_first(universe, *keywords):
    kw = [norm(k) for k in keywords]
    for v in universe:
        nv = norm(v)
        if all(k in nv for k in kw):
            return v
    for v in universe:
        nv = norm(v)
        if any(k in nv for k in kw):
            return v
    return None

def resample_series(s: pd.Series, freq: str, how: str):
    if freq == "D":
        return s
    if how == "mean":
        return s.resample(freq).mean().dropna()
    return s.resample(freq).last().dropna()

def pct_change(df, periods=1):
    return df.pct_change(periods=periods)*100.0

def yoy_monthly_from_daily(s: pd.Series):
    m = s.resample("M").last()
    return m.pct_change(12)*100.0

def nice_step(raw_step):
    exp = np.floor(np.log10(raw_step)) if raw_step > 0 else 0
    frac = raw_step / (10 ** exp) if raw_step > 0 else 1
    if frac <= 1: nf = 1
    elif frac <= 2: nf = 2
    elif frac <= 2.5: nf = 2.5
    elif frac <= 5: nf = 5
    else: nf = 10
    return nf * (10 ** exp)

def nice_ticks(vmin, vmax, max_ticks=7):
    if vmin == vmax:
        if vmin == 0: return np.array([0.0])
        vmin *= 0.9; vmax *= 1.1
    rng = vmax - vmin
    raw = rng / max(1, (max_ticks - 1))
    step = nice_step(raw)
    t0 = np.floor(vmin / step) * step
    t1 = np.ceil(vmax / step) * step
    ticks = np.arange(t0, t1 + 0.5*step, step)
    exp = np.floor(np.log10(step)) if step > 0 else 0
    return np.round(ticks, int(max(0, -exp)))

def aligned_right_ticks_round(left_ticks, rmin_data, rmax_data):
    N = len(left_ticks)
    if N <= 1:
        return np.array([rmin_data]), (rmin_data, rmax_data)
    # paso "lindo" para el eje derecho con esa cantidad de marcas
    raw = (rmax_data - rmin_data) / max(1, (N-1))
    step_r = nice_step(raw if raw>0 else 1.0)
    r0 = np.floor(rmin_data / step_r) * step_r
    r_end = r0 + step_r * (N - 1)
    if r_end < rmax_data:
        r_end = np.ceil(rmax_data / step_r) * step_r
        r0 = r_end - step_r * (N - 1)
    ticks_r = r0 + step_r * np.arange(N)
    return ticks_r, (r0, r_end)
