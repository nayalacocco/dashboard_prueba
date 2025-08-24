# scripts/debug_raw_headers.py
import os, glob, pandas as pd

RAW_DIR = "data/raw"

def read_try(path):
    # Intento 1: coma
    try:
        df = pd.read_csv(path, nrows=2, dtype=str, sep=",", encoding="utf-8", on_bad_lines="skip")
        return ",", df
    except Exception:
        pass
    # Intento 2: punto y coma
    try:
        df = pd.read_csv(path, nrows=2, dtype=str, sep=";", encoding="utf-8", on_bad_lines="skip")
        return ";", df
    except Exception:
        pass
    # Intento 3: autodetección (engine python)
    try:
        df = pd.read_csv(path, nrows=2, dtype=str, sep=None, engine="python", encoding="utf-8", on_bad_lines="skip")
        return "auto", df
    except Exception as e:
        return None, str(e)

def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))
    if not files:
        print("[debug] No hay CSV en data/raw")
        return
    for f in files:
        sep, res = read_try(f)
        print("="*80)
        print(f"Archivo: {f}")
        if sep is None:
            print(f"  ❌ No pude leerlo. Error: {res}")
            continue
        print(f"  ✓ Separador detectado: {sep}")
        if isinstance(res, pd.DataFrame):
            cols = [c for c in res.columns]
            print(f"  Columnas (sample): {cols}")
        else:
            print("  ❌ No pude obtener columnas")

if __name__ == "__main__":
    main()
