"""
Coto Digital - Scraper BEBIDAS
Categorias: Bebidas Con Alcohol + Bebidas Sin Alcohol
Uso: python coto_bebidas.py
"""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from coto_base import scrape_categoria, guardar, log, MAX_WORKERS

CATEGORIAS = [
    {"n": "4hulsc",  "nombre": "Bebidas Con Alcohol"},
    {"n": "j9f2pv",  "nombre": "Bebidas Sin Alcohol"},
]

OUTPUT_DIR = SCRIPT_DIR / "output_bebidas"

if __name__ == "__main__":
    # Ambas categorías en paralelo
    resultados = {}

    def scrape_cat(cat):
        prods = scrape_categoria(cat["n"], cat["nombre"])
        return cat["n"], prods

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for n_code, prods in ex.map(scrape_cat, CATEGORIAS):
            resultados[n_code] = prods

    # Acumular en orden original
    todos = []
    for cat in CATEGORIAS:
        todos.extend(resultados[cat["n"]])
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
