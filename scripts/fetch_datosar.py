# scripts/fetch_datosar.py
from datosar_utils import fetch_datosar_to_disk, load_datosar_long

# 🔎 IDS INICIALES (poné los que quieras de Tesoro/INDEC/etc.)
# Sugerencia: agregá/edita estos con tus IDs reales desde datos.gob.ar/series
DATOSAR_IDS = [
    # Ejemplos (cámbialos por tus objetivos):
    # "75.1_IHLFP_0_A_42",      # exportaciones hortalizas (ejemplo)
    # "143.3_TCRZE_0_M_36",     # (ejemplo de tipo de cambio real, si existe en catálogo)
]

if __name__ == "__main__":
    fetch_datosar_to_disk(DATOSAR_IDS)
    df = load_datosar_long()
    print(df.head())
    print(f"Series: {df['id'].nunique()}  |  Filas: {len(df):,}")
