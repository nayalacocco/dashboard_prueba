# scripts/build_macro_core.py
# Lee data/monetarias_long.csv (y el catálogo) generado por scripts/fetch_bcra.py
# y arma series “core” derivadas en data/macro_core_long.parquet / .csv

from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

# ------------------------------
# Entradas (de TU fetch_bcra.py)
# ------------------------------
DATA_DIR = Path("data")
BCRA_LONG_CSV = DATA_DIR / "monetarias_long.csv"
BCRA_CAT_JSON = DATA_DIR / "monetarias_catalogo.json"

# ------------------------------
# Salidas
# ------------------------------
OUT_PARQUET = DATA_DIR / "macro_core_long.parquet"
OUT_CSV     = DATA_DIR / "macro_core_long.csv"

# ------------------------------
# Helpers
# ------------------------------
def _ensure_inputs():
    missing = []
    if not BCRA_LONG_CSV.exists():
        missing.append(str(BCRA_LONG_CSV))
    if not BCRA_CAT_JSON.exists():
        missing.append(str(BCRA_CAT_JSON))
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada del BCRA.\n"
            + "\n".join(f" - {m}" for m in missing)
            + "\nCorré primero: scripts/fetch_bcra.py (o el workflow de fetch del BCRA)."
        )

def _load_bcra_long() -> pd.DataFrame:
    df = pd.read_csv(BCRA_LONG_CSV, dtype={"id": str, "descripcion": str})
    # normalizo tipos
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["fecha", "valor"]).sort_values(["descripcion", "fecha"])
    return df

def _load_catalog() -> pd.DataFrame:
    with open(BCRA_CAT_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return pd.DataFrame(raw)

def _find_desc(options: list[str], *tokens: str) -> str | None:
    """
    Devuelve la primera descripción cuyo string incluye TODOS los tokens (case-insensitive).
    """
    toks = [t.lower() for t in tokens if t]
    for name in options:
        s = (name or "").lower()
        if all(tok in s for tok in toks):
            return name
    return None

# ------------------------------
# Core builder
# ------------------------------
def build_series() -> pd.DataFrame:
    _ensure_inputs()
    df = _load_bcra_long()
    cat = _load_catalog()

    # universo de descripciones disponibles
    descs = sorted(df["descripcion"].dropna().unique().tolist())

    # 1) Reservas internacionales brutas del BCRA (en millones de USD)
    #    (hay varias descripciones; tratamos de agarrar la más estándar)
    reservas_desc = (
        _find_desc(descs, "reservas", "internacionales", "dólar")
        or _find_desc(descs, "reservas", "internacionales", "usd")
        or _find_desc(descs, "reservas", "brutas")
        or _find_desc(descs, "reservas")
    )

    # 2) Pasivos remunerados del BCRA (Pases pasivos, en millones de $)
    pases_desc = (
        _find_desc(descs, "pases", "pasivos")
        or _find_desc(descs, "stock", "pases", "pasivos")
        or _find_desc(descs, "pases")  # fallback
    )

    # 3) Tipo de cambio mayorista para convertir $ -> USD
    tc_desc = (
        _find_desc(descs, "tipo", "cambio", "comunicación", "3500")
        or _find_desc(descs, "tipo", "cambio", "mayorista")
        or _find_desc(descs, "tipo", "cambio", "referencia")
        or _find_desc(descs, "ars/usd")
        or _find_desc(descs, "usd", "oficial")
    )

    missing = []
    if not reservas_desc: missing.append("Reservas internacionales (no encontré descripción)")
    if not pases_desc:    missing.append("Pases pasivos / Pasivos remunerados (no encontré descripción)")
    if not tc_desc:       missing.append("Tipo de cambio mayorista/ref. (no encontré descripción)")
    if missing:
        raise RuntimeError("No pude identificar las siguientes series base:\n- " + "\n- ".join(missing))

    # Pivot base
    wide = (
        df[df["descripcion"].isin([reservas_desc, pases_desc, tc_desc])]
        .pivot(index="fecha", columns="descripcion", values="valor")
        .sort_index()
    )

    # renombres cortos
    wide = wide.rename(columns={
        reservas_desc: "reservas_usd_mill",
        pases_desc:    "pases_mill_ars",
        tc_desc:       "tc_ars_por_usd",
    })

    # Derivados
    out = []

    # Reservas (ya en millones de USD, asumimos)
    if "reservas_usd_mill" in wide:
        s = wide["reservas_usd_mill"].dropna()
        out.append(pd.DataFrame({
            "fecha": s.index,
            "serie": "Reservas brutas del BCRA – millones de USD",
            "valor": s.values,
            "fuente": "BCRA (Monetarias)",
            "nota": "Serie del API 'Reservas internacionales'; nivel en millones de USD.",
        }))

    # Pasivos remunerados en millones de USD = pases (mill. ARS) / tipo de cambio (ARS/USD)
    if {"pases_mill_ars", "tc_ars_por_usd"}.issubset(wide.columns):
        s = (wide["pases_mill_ars"] / wide["tc_ars_por_usd"]).dropna()
        out.append(pd.DataFrame({
            "fecha": s.index,
            "serie": "Pasivos remunerados del BCRA – millones de USD",
            "valor": s.values,
            "fuente": "BCRA (Monetarias)",
            "nota": "Pases pasivos en millones de ARS convertidos a USD con TC mayorista de referencia.",
        }))

    if not out:
        raise RuntimeError("No se pudo construir ninguna serie derivada (out vacío).")

    long = pd.concat(out, ignore_index=True).sort_values(["serie", "fecha"])
    return long

def main():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        long = build_series()
        # Guardamos
        long.to_parquet(OUT_PARQUET, index=False)
        long.to_csv(OUT_CSV, index=False, encoding="utf-8")
        print(f"✅ Guardado: {OUT_PARQUET} ({len(long):,} filas)")
        print(f"✅ Guardado: {OUT_CSV} ({len(long):,} filas)")
        # Resumen por serie
        resumen = long.groupby("serie")["valor"].last().to_frame("último").reset_index()
        print("\nSeries derivadas y último valor:")
        for _, r in resumen.iterrows():
            print(f" - {r['serie']}: {r['último']:.2f}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
