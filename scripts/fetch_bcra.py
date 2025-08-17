# scripts/fetch_bcra.py
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
    # En GitHub Actions desactivamos verificación SSL (el server del BCRA falla)
    return session.get(url, timeout=60, verify=False, **kw)

def first_ok(urls, **kw):
    """Prueba una lista de URLs hasta que una responda 200."""
    last_exc = None
    for u in urls:
        try:
            r = get(u, **kw)
            if r.status_code == 200:
                return r
            else:
                print(f"→ {u} -> {r.status_code}", flush=True)
        except Exception as e:
            last_exc = e
            print(f"× {u} -> {e}", flush=True)
    if last_exc:
        raise last_exc
    raise RuntimeError("Ningún endpoint respondió 200")

def get_catalogo():
    # Variantes de la ruta (algunos servidores son case sensitive)
    bases = [
        "https://api.bcra.gob.ar/estadisticas/v3.0/Monetarias",
        "https://api.bcra.gob.ar/estadisticas/v3.0/monetarias",
    ]
    r = first_ok(bases)
    payload = r.json()
    items = payload.get("results", payload)
    if not isinstance(items, list):
        raise RuntimeError("Catálogo inesperado (no es lista)")
    print(f"✅ Catálogo monetarias: {len(items)} items")
    return items

def find_base_monetaria_id(items):
    # Prioridad: "Base Monetaria Total"
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria total" in desc or "total monetary base" in desc:
            return it.get("idVariable") or it.get("IdVariable"), desc
    # Fallback: cualquier "Base Monetaria"
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria" in desc:
            return it.get("idVariable") or it.get("IdVariable"), desc
    raise RuntimeError("No encontré 'Base Monetaria' en el catálogo.")

def fetch_serie(id_var: int):
    desde = "1990-01-01"
    hasta = date.today().isoformat()
    # Variantes de endpoint de serie
    urls = [
        f"https://api.bcra.gob.ar/estadisticas/v3.0/Monetarias/{id_var}",
        f"https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/{id_var}",
        # Algunas implementaciones usan /Series
        f"https://api.bcra.gob.ar/estadisticas/v3.0/Monetarias/{id_var}/Series",
        f"https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/{id_var}/series",
    ]
    params = {"desde": desde, "hasta": hasta, "limit": 300000}
    r = first_ok(urls, params=params)
    payload = r.json()
    rows = payload.get("results", payload)
    out = []
    for p in rows if isinstance(rows, list) else []:
        fecha = p.get("fecha") or p.get("d")
        valor = p.get("valor") or p.get("v")
        if fecha is None or valor is None:
            continue
        out.append({"fecha": fecha, "valor": valor})
    if not out:
        raise RuntimeError("La serie vino vacía o en formato inesperado.")
    print(f"✅ Serie descargada: {len(out)} puntos")
    return out

def main():
    try:
        items = get_catalogo()
        id_var, desc = find_base_monetaria_id(items)
        print(f"🔎 Usando idVariable={id_var} ({desc})")
        serie = fetch_serie(id_var)

        # Guardar CSV/JSON
        df = pd.DataFrame(serie)
        df.to_csv(CSV_PATH, index=False, encoding="utf-8")
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(serie, f, ensure_ascii=False, indent=2)

        print(f"💾 Guardado: {CSV_PATH} y {JSON_PATH}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
