# scripts/fetch_bcra.py
import json, sys, time
from pathlib import Path
from datetime import date
import requests
import pandas as pd

OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAT_JSON = OUT_DIR / "monetarias_catalogo.json"
ALL_CSV  = OUT_DIR / "monetarias_long.csv"   # formato largo: id, descripcion, fecha, valor

BASE = "https://api.bcra.gob.ar/estadisticas/v3.0"
CAT_URLS = [f"{BASE}/Monetarias", f"{BASE}/monetarias"]                  # catálogo
SERIES_TMPL = [f"{BASE}/Monetarias/{{id}}", f"{BASE}/monetarias/{{id}}"] # serie por id

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "gh-actions-bcra-fetch/1.1"
}

session = requests.Session()

def get(url, **kw):
    # verify=False por el certificado del host del BCRA en runners
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
        raise RuntimeError("Catálogo inesperado (no es lista)")
    # normalizamos campos que vamos a usar
    norm = []
    for it in items:
        norm.append({
            "id": it.get("idVariable") or it.get("IdVariable"),
            "descripcion": (it.get("descripcion") or it.get("Descripcion") or "").strip(),
            "unidad": it.get("unidad") or it.get("Unidad") or "",
        })
    print(f"✅ Catálogo monetarias: {len(norm)} items")
    return norm

def fetch_series_v3(id_var, start="1990-01-01", end=None, page=1000, pause=0.15):
    if end is None:
        end = date.today().isoformat()
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
            raise RuntimeError(f"Serie v3 {id_var} failed (status {r.status_code})")
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
        time.sleep(pause)  # ser amable con el API
    return out

def main():
    try:
        catalogo = load_catalog()

        # Guardamos catálogo para que el front muestre nombres prolijos
        with open(CAT_JSON, "w", encoding="utf-8") as f:
            json.dump(catalogo, f, ensure_ascii=False, indent=2)

        # Descargamos TODAS las series y armamos un CSV largo
        registros = []
        for i, item in enumerate(catalogo, 1):
            idv = item["id"]
            desc = item["descripcion"]
            try:
                serie = fetch_series_v3(int(idv))
                for p in serie:
                    registros.append({
                        "id": idv,
                        "descripcion": desc,
                        "fecha": p["fecha"],
                        "valor": p["valor"],
                    })
                print(f"[{i}/{len(catalogo)}] OK id={idv} ({desc}) -> {len(serie)} pts")
            except Exception as e:
                print(f"[{i}/{len(catalogo)}] ERR id={idv} ({desc}): {e}")

        if not registros:
            raise RuntimeError("No se descargó ninguna serie.")

        df = pd.DataFrame(registros)
        # normalizamos tipos
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna().sort_values(["descripcion", "fecha"])

        df.to_csv(ALL_CSV, index=False, encoding="utf-8")

        print(f"💾 Guardado catálogo: {CAT_JSON}")
        print(f"💾 Guardado series (formato largo): {ALL_CSV} ({len(df)} filas)")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
