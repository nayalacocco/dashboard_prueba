# scripts/fetch_bcra.py
import json, os, sys, datetime as dt
import requests
from pathlib import Path

# --- Config ---
BASE = "https://api.bcra.gob.ar/estadisticas/v3.0"
LISTADO = f"{BASE}/monetarias"
OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Función robusta de GET con certificado ignorado (solo en runner)
def get(url, params=None):
    return requests.get(url, params=params or {}, timeout=30, verify=False)

def main():
    # 1) Traer listado de variables y ubicar "Base Monetaria Total"
    r = get(LISTADO)
    r.raise_for_status()
    payload = r.json()
    results = payload["results"] if isinstance(payload, dict) and "results" in payload else payload

    # Busco por textos típicos
    candidatos = [x for x in results if isinstance(x, dict) and x.get("descripcion")]
    bm = None
    for row in candidatos:
        desc = row["descripcion"].lower()
        if ("base monetaria total" in desc) or ("total monetary base" in desc):
            bm = row
            break

    if not bm:
        print("No se encontró 'Base Monetaria Total' en el listado.", file=sys.stderr)
        sys.exit(1)

    id_var = bm["idVariable"]

    # 2) Traer la serie completa
    desde = "1990-01-01"
    hasta = dt.date.today().isoformat()
    url_serie = f"{BASE}/monetarias/{id_var}"
    r2 = get(url_serie, params={"desde": desde, "hasta": hasta, "limit": 300000})
    r2.raise_for_status()
    serie_payload = r2.json()
    serie = serie_payload["results"] if isinstance(serie_payload, dict) and "results" in serie_payload else serie_payload

    # Normalizo a una lista de {fecha, valor}
    out = []
    for p in serie:
        # API suele devolver 'fecha' y 'valor' o 'd' y 'v'; cubro ambas
        fecha = p.get("fecha") or p.get("d")
        valor = p.get("valor") or p.get("v")
        if fecha is None or valor is None:
            continue
        out.append({"fecha": fecha, "valor": valor})

    # 3) Guardar JSON y CSV versionados en el repo
    json_path = OUT_DIR / "base_monetaria.json"
    csv_path = OUT_DIR / "base_monetaria.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # CSV rápido
    try:
        import pandas as pd
        import io
        import math
        df = pd.DataFrame(out)
        df.to_csv(csv_path, index=False)
    except Exception:
        # fallback mínimo sin pandas
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("fecha,valor\n")
            for row in out:
                f.write(f"{row['fecha']},{row['valor']}\n")

    print(f"OK: {len(out)} puntos guardados en {json_path} y {csv_path}")

if __name__ == "__main__":
    main()
