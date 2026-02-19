"""
Coto Digital - Scraper BEBIDAS
Categorias: Bebidas Con Alcohol + Bebidas Sin Alcohol

Uso: python coto_bebidas.py
"""
import sys
from pathlib import Path

# Directorio del script (funciona sin importar desde donde se ejecute)
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from coto_base import scrape_categoria, guardar, log

CATEGORIAS = [
    {"n": "4hulsc",  "nombre": "Bebidas Con Alcohol"},
    {"n": "j9f2pv",  "nombre": "Bebidas Sin Alcohol"},
]

# Guarda en output_bebidas/ dentro de la misma carpeta que este script
OUTPUT_DIR = SCRIPT_DIR / "output_bebidas"

if __name__ == "__main__":
    todos = []
    for cat in CATEGORIAS:
        prods = scrape_categoria(cat["n"], cat["nombre"])
        todos.extend(prods)
        log.info(f"  acumulado: {len(todos)}")

    # Deduplicar por PLU
    vistos, unicos = set(), []
    for p in todos:
        if p["plu"] not in vistos:
            vistos.add(p["plu"])
            unicos.append(p)

    log.info(f"\nTotal bebidas: {len(unicos)} productos unicos")
    ruta = guardar(unicos, OUTPUT_DIR, "coto_bebidas")
    log.info(f"Archivos guardados en: {OUTPUT_DIR.resolve()}")
