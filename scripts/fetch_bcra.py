import json
import sys
from pathlib import Path
from datetime import date
import requests
import pandas as pd

OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = OUT_DIR / "base_monetaria.csv"
JSON_PATH = OUT_DIR / "base_monetaria.json"

session = requests.Session()

def get(url, **kw):
    # En GitHub Actions permitimos verify=False por el SSL del host del BCRA
    return session.get(url, timeout=60, verify=False, **kw)

def first_ok(urls, **kw):
    last_exc = None
    for u in urls:
        try:
            r = get(u, **kw)
            print(f"→ {u} -> {r.status_code}", flush=True)
            if r.status_code == 200:
                return r
        except Exception as e:
            last_exc = e
            print(f"× {u} -> {e}", flush=True)
    if last_exc:
        raise last_exc
    raise RuntimeError("Ningún endpoint respondió 200")

def get_catalogo_v3():
    # El catálogo monetario funciona en v3.0
    urls = [
        "https://api.bcra.gob.ar/estadisticas/v3.0/monetarias",
        "https://api.bcra.gob.ar/estadisticas/v3.0/Monetarias",
    ]
    r = first_ok(urls)
    payload = r.json()
    items = payload.get("results", payload)
    if not isinstance(items, list):
        raise RuntimeError("Catálogo inesperado (no es lista)")
    print(f"✅ Catálogo monetarias: {len(items)} items")
    return items

def find_base_monetaria(items):
    # Busco Base Monetaria TOTAL si está; si no, cualquier "Base Monetaria"
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria total" in desc or "total monetary base" in desc:
            return (it.get("idVariable") or it.get("IdVariable")), desc
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria" in desc:
            return (it.get("idVariable") or it.get("IdVariable")), desc
    raise RuntimeError("No encontré 'Base Monetaria' en el catálogo v3.")

def fetch_serie_by_id(id_var: int):
    """La serie histórica responde en v1 (/serie/{id})."""
    urls = [
        f"https://api.bcra.gob.ar/estadisticas/v1/serie/{id_var}",
        f"https://api.bcra.gob.ar/estadisticas/v1/Series/{id_var}",
    ]
    r = first_ok(urls)
    rows = r.json()
    # Estructura típica v1: lista de dicts con 'd' (fecha) y 'v' (valor)
    out = []
    if isinstance(rows, list):
        for p in rows:
            fecha = p.get("fecha") or p.get("d")
            valor = p.get("valor") or p.get("v")
            if fecha is not None and valor is not None:
                out.append({"fecha": fecha, "valor": valor})
    if not out:
        raise RuntimeError("La serie vino vacía o en formato inesperado (v1).")
    print(f"✅ Serie descargada: {len(out)} puntos")
    return out

def main():
    try:
        items = get_catalogo_v3()
        id_var, desc = find_base_monetaria(items)
        print(f"🔎 idVariable={id_var} ({desc})")
        serie = fetch_serie_by_id(int(id_var))

        df = pd.DataFrame(serie)
        # normalizo tipos por las dudas
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna().sort_values("fecha")

        df.to_csv(CSV_PATH, index=False, encoding="utf-8")
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(serie, f, ensure_ascii=False, indent=2)

        print(f"💾 Guardado: {CSV_PATH} y {JSON_PATH} ({len(df)} puntos válidos)")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
