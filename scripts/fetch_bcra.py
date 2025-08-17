import requests
import pandas as pd
from pathlib import Path
import sys

BASE_URL = "https://api.bcra.gob.ar/estadisticas/v1"

def main():
    try:
        print("🔎 Consultando catálogo...")
        resp = requests.get(f"{BASE_URL}/principalesvariables", verify=False, timeout=30)
        resp.raise_for_status()
        catalogo = resp.json()
        print(f"✅ Catálogo recibido con {len(catalogo)} variables")

        # Mostramos los primeros 10 nombres para debug
        for v in catalogo[:10]:
            print(f"- {v['IdVariable']}: {v['Descripcion']}")

        # Buscamos la base monetaria
        base = next((v for v in catalogo if "base monetaria" in v["Descripcion"].lower()), None)
        if not base:
            print("❌ No se encontró la variable 'Base Monetaria'")
            sys.exit(1)

        print(f"✅ Variable encontrada: {base}")

        # Bajamos la serie
        resp2 = requests.get(f"{BASE_URL}/serie/{base['IdVariable']}", verify=False, timeout=30)
        resp2.raise_for_status()
        data = resp2.json()
        print(f"✅ Serie descargada con {len(data)} puntos")

        df = pd.DataFrame(data)
        OUT = Path("data")
        OUT.mkdir(parents=True, exist_ok=True)
        CSV_PATH = OUT / "base_monetaria.csv"
        df.to_csv(CSV_PATH, index=False)
        print(f"💾 Guardado en {CSV_PATH}")

    except Exception as e:
        print(f"❌ Error en fetch_bcra: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
