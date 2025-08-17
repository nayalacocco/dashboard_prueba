# scripts/fetch_bcra.py
import json
import requests
import pandas as pd
from datetime import date
from pathlib import Path

BASE = "https://api.bcra.gob.ar/estadisticas/v3.0"
LISTADO = f"{BASE}/monetarias"

OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = OUT_DIR / "base_monetaria.csv"
JSON_PATH = OUT_DIR / "base_monetaria.json"

session = requests.Session()

def get(url, **kwargs):
    # En GitHub Actions podemos usar verify=False para salvar el SSL del servidor del BCRA
    return session.get(url, timeout=60, verify=False, **kwargs)

def find_base_monetaria_id():
    r = get(LISTADO)
    r.raise_for_status()
    payload = r.json()
    items = payload.get("results", payload)

    # buscar por descripciones típicas
    target = None
    for it in items:
        desc = (it.get("descripcion") or "").lower()
        if "base monetaria total" in desc or "total monetary base" in desc:
            target = it
            break
    # fallback: cualquier "base monetaria"
    if not target:
        for it in items:
            desc = (it.get("descripcion") or "").lower()
            if "base monetaria" in desc:
                target = it
                break

    if not target:
        raise RuntimeError("No encontré 'Base Monetaria' en el listado del BCRA.")
    return target["idVariable"], target["descripcion"]

def fetch_series(id_var):
    url = f"{BASE}/monetarias/{id_var}"
    params = {"desde": "1990-01-01", "hasta": date.today().isoformat(), "limit": 300000}
    r = get(url, params=params)
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("results", payload)
    out = []
    for p in rows:
        fecha = p.get("fecha") or p.get("d")
        valor = p.get("valor") or p.get("v")
        if fecha is None or valor is None:
            continue
        out.append({"fecha": fecha, "valor": valor})
    return out

def main():
    id_var, desc = find_base_monetaria_id()
    serie = fetch_series(id_var)

    # Guardar CSV y JSON
    df = pd.DataFrame(serie)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(serie, f, ensure_ascii=False, indent=2)

    print(f"OK ({len(df)} puntos) -> {CSV_PATH} | {JSON_PATH}  [{desc}]")

if __name__ == "__main__":
    main()
