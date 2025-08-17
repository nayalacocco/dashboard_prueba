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

BASE = "https://api.bcra.gob.ar/estadisticas/v3.0"
CAT_URLS = [f"{BASE}/Monetarias", f"{BASE}/monetarias"]               # cat monetarias v3
SERIES_TMPL = [f"{BASE}/Monetarias/{{id}}", f"{BASE}/monetarias/{{id}}"]  # serie por id v3

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "gh-actions-bcra-fetch/1.0"
}

session = requests.Session()

def get(url, **kw):
    # verify=False por el certificado del host del BCRA en runner
    return session.get(url, headers=HEADERS, timeout=60, verify=False, **kw)

def first_ok(urls, **kw):
    last = None
    for u in urls:
        r = get(u, **kw)
        print(f"→ {u} -> {r.status_code}", flush=True)
        if r.status_code == 200:
            return r
        last = r
    raise RuntimeError(f"Request failed: last_status={last.status_code if last else 'n/a'}")

def load_catalog():
    r = first_ok(CAT_URLS)
    payload = r.json()
    items = payload.get("results", payload)
    if not isinstance(items, list):
        raise RuntimeError("Catálogo inesperado")
    print(f"✅ Catálogo monetarias: {len(items)} items")
    return items

def pick_base_monetaria(items):
    # prioridad: 'Base Monetaria total'
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria total" in desc or "total monetary base" in desc:
            return (it.get("idVariable") or it.get("IdVariable")), desc
    # fallback: cualquier 'base monetaria'
    for it in items:
        desc = (it.get("descripcion") or it.get("Descripcion") or "").lower()
        if "base monetaria" in desc:
            return (it.get("idVariable") or it.get("IdVariable")), desc
    raise RuntimeError("No encontré 'Base Monetaria' en el catálogo v3")

def fetch_series_v3(id_var, start="1990-01-01", end=None, page=1000):
    if end is None:
        end = date.today().isoformat()
    # v3 espera DATE-TIME
    desde = f"{start}T00:00:00"
    hasta = f"{end}T23:59:59"
    offset = 0
    out = []
    while True:
        params = {"desde": desde, "hasta": hasta, "limit": page, "offset": offset}
        r = None
        for tmpl in SERIES_TMPL:
            r = get(tmpl.format(id=id_var), params=params)
            if r.status_code == 200:
                break
        if r is None or r.status_code != 200:
            raise RuntimeError(f"Serie v3 request failed (status {r.status_code}): {r.text[:200]}")
        payload = r.json()
        rows = payload.get("results", payload)
        if not rows:
            break
        for p in rows:
            fecha = p.get("fecha")
            valor = p.get("valor")
            if fecha is not None and valor is not None:
                out.append({"fecha": fecha, "valor": valor})
        if len(rows) < page:
            break
        offset += page
    print(f"✅ Serie descargada (v3): {len(out)} puntos")
    return out

def main():
    try:
        items = load_catalog()
        id_var, desc = pick_base_monetaria(items)
        print(f"🔎 idVariable={id_var} ({desc})")

        serie = fetch_series_v3(int(id_var))
        df = pd.DataFrame(serie)
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
