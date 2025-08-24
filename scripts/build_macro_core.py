# scripts/build_macro_core.py
import os, sys, math
from datetime import timedelta

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, "data")
BCRA_LONG = os.path.join(DATA, "bcra_long.parquet")
OUT_LONG  = os.path.join(DATA, "macro_core_long.parquet")

def _load_bcra():
    if not os.path.exists(BCRA_LONG):
        raise FileNotFoundError(f"No existe {BCRA_LONG}. Corré el fetch del BCRA primero.")
    df = pd.read_parquet(BCRA_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"])
    # normalizo descripciones
    df["descripcion_norm"] = df["descripcion"].str.strip().str.lower()
    return df

def _find_first(descs, *tokens):
    """Devuelve la primer descripción que contenga TODOS los tokens (case-insensitive)."""
    toks = [t.lower() for t in tokens]
    for d in descs:
        s = (d or "").lower()
        if all(t in s for t in toks):
            return d
    return None

def _nearest_merge(a: pd.Series, b: pd.Series, tolerance_days=2) -> pd.DataFrame:
    """Join por fecha con tolerancia (en días). Toma el valor más reciente anterior."""
    a = a.dropna().sort_index()
    b = b.dropna().sort_index()
    # reindex a diario para facilitar merge_asof
    a_d = a.asfreq("D").ffill()
    b_d = b.asfreq("D").ffill()
    df = pd.merge_asof(
        a_d.reset_index().rename(columns={"index":"fecha", a.name: "a"}),
        b_d.reset_index().rename(columns={"index":"fecha", b.name: "b"}),
        on="fecha",
        direction="backward",
        tolerance=pd.Timedelta(days=tolerance_days),
    ).set_index("fecha")
    return df.dropna()

def _maybe_to_usd_mn(series_name: str, s: pd.Series, fx_mep: pd.Series|None, fx_ref: pd.Series|None) -> tuple[pd.Series, str]:
    """
    Intenta adivinar si la serie está en millones de USD o millones de ARS.
    Si parece ARS, convierte a USD usando fx_ref (A3500) si existe.
    Devuelve (serie_en_millones_de_usd, nota_unidad)
    """
    name = (series_name or "").lower()
    # pistas:
    if "millones de dólares" in name or "millones de dolares" in name or "millones de usd" in name:
        return s, "millones de USD"
    if "millones de $" in name or "millones de pesos" in name:
        # convertir ARS -> USD con A3500 si está
        if fx_ref is None or fx_ref.empty:
            return pd.Series(dtype=float), "(no pude convertir ARS→USD: falta A3500)"
        pair = _nearest_merge(s, fx_ref)  # columnas a, b
        usd = (pair["a"] / pair["b"]).rename(s.name)
        return usd, "millones de USD (ARS/A3500)"
    # por defecto: no sabemos
    return pd.Series(dtype=float), "(unidad desconocida)"

def build_series():
    df = _load_bcra()
    descs = df["descripcion"].dropna().unique().tolist()

    # ➊ Reservas brutas BCRA (ya viene en millones de USD)
    reservas_name = _find_first(descs, "reservas", "brutas") or _find_first(descs, "reservas internacionales")
    reservas = None
    if reservas_name:
        reservas = (
            df[df["descripcion"] == reservas_name]
            .set_index("fecha")["valor"].astype(float).dropna().sort_index()
        )

    # ➋ Stock de pasivos remunerados (LELIQ + Pases pasivos) en millones de USD
    #    Leliq ya no existe, pero si hubiera serie, la sumamos.
    pases_name  = _find_first(descs, "stock", "pases", "pasivos")
    leliq_name  = _find_first(descs, "stock", "leliq")
    fx_name     = _find_first(descs, "tipo de cambio", "3500") or _find_first(descs, "comunicación", "a 3500")

    s_pases = s_leliq = fx_ref = None
    if pases_name:
        s_pases = df[df["descripcion"] == pases_name].set_index("fecha")["valor"].astype(float).dropna().sort_index()
    if leliq_name:
        s_leliq = df[df["descripcion"] == leliq_name].set_index("fecha")["valor"].astype(float).dropna().sort_index()
    if fx_name:
        fx_ref = df[df["descripcion"] == fx_name].set_index("fecha")["valor"].astype(float).dropna().sort_index()

    pasivos_usd = None
    if s_pases is not None:
        p_mn, _ = _maybe_to_usd_mn(pases_name, s_pases, fx_mep=None, fx_ref=fx_ref)  # en millones de USD
        if s_leliq is not None and not s_leliq.empty:
            l_mn, _ = _maybe_to_usd_mn(leliq_name, s_leliq, fx_mep=None, fx_ref=fx_ref)
            pasivos_usd = (p_mn.align(l_mn, join="outer")[0].fillna(0) + l_mn.fillna(0)).dropna()
        else:
            pasivos_usd = p_mn.dropna()

    # Salida unificada en formato long
    rows = []

    def push(serie: pd.Series|None, key: str, titulo: str, unidad: str, scale_to_bn=False):
        if serie is None or serie.empty:
            return
        s = serie.copy()
        if scale_to_bn:
            s = s / 1000.0  # millones → miles de millones (bn)
            u = "miles de millones de USD"
        else:
            u = unidad
        tmp = pd.DataFrame({
            "fecha": s.index,
            "indicador": key,
            "titulo": titulo,
            "valor": s.values,
            "unidad": u,
        })
        rows.append(tmp)

    if reservas is not None:
        # viene en millones de USD, muestro como miles de millones en el dashboard
        push(reservas, "reservas_brutas_bcra_usd_bn", "Reservas brutas BCRA", "miles de millones de USD", scale_to_bn=True)

    if pasivos_usd is not None and not pasivos_usd.empty:
        push(pasivos_usd, "pasivos_remunerados_bcra_usd_bn", "Pasivos remunerados (LELIQ+Pases) – BCRA", "miles de millones de USD", scale_to_bn=True)

    # placeholders (quedan con cero filas hasta que enchufemos DatosAR/INDEC)
    placeholders = [
        ("resultado_fiscal_financiero_pct_pib", "Resultado fiscal financiero (% del PIB)"),
        ("inflacion_nucleo_tna", "Inflación núcleo (TNA)"),
        ("pobreza_pct", "Pobreza (%)"),
        ("deuda_publica_usd_bn", "Deuda pública consolidada (USD bn)"),
        ("riesgo_pais_pb", "Riesgo país (p.b.)"),
    ]
    for key, titulo in placeholders:
        pass  # se completarán cuando sumemos el catálogo externo

    if not rows:
        raise RuntimeError("No pude construir ninguna serie macro core. ¿Faltan variables BCRA?")
    out = pd.concat(rows, ignore_index=True).sort_values("fecha")
    out.to_parquet(OUT_LONG, index=False)
    print(f"[macro_core] Guardado {OUT_LONG}  (rows={len(out):,})")

if __name__ == "__main__":
    build_series()
