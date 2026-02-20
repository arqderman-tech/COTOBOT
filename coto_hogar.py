"""
Coto Digital — Scraper HOGAR Y OTROS
Categorías: Limpieza + Perfumería (cuidado personal, farmacia, cosméticos, etc.)
N-codes validados contra el catálogo en vivo.
Uso: python coto_hogar.py
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from coto_base import scrape_categoria, guardar, log, MAX_WORKERS
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

CATEGORIAS = [
    # ── LIMPIEZA ──────────────────────────────────────────────────────────────
    {"n": "t2y8zd",  "nombre": "Lavado"},                        # 252
    {"n": "ohywgy",  "nombre": "Accesorios De Limpieza"},         # 421
    {"n": "1annh67", "nombre": "Desodorantes De Ambiente"},       # 169
    {"n": "pz78zm",  "nombre": "Limpieza De Baño"},               # 63
    {"n": "1lonain", "nombre": "Limpieza De Cocina"},             # 124
    {"n": "bf8h0x",  "nombre": "Limpieza De Pisos Y Superficies"},# 184
    {"n": "1ogrrlx", "nombre": "Lavandinas"},                     # 35
    # ── PERFUMERÍA / CUIDADO PERSONAL ────────────────────────────────────────
    {"n": "1w8xczk", "nombre": "Cuidado Del Cabello"},            # 795
    {"n": "721a4h",  "nombre": "Higiene Personal"},               # 253
    {"n": "2f9qa1",  "nombre": "Desodorantes Y Antitranspirantes"},# 139
    {"n": "1a8xcmp", "nombre": "Pañales E Incontinencia"},        # 111
    {"n": "sstxyh",  "nombre": "Cuidado Personal"},               # 74
    {"n": "iak9sv",  "nombre": "Cuidado Bucal"},                  # 225
    {"n": "1csoql4", "nombre": "Protección Femenina"},            # 124
    {"n": "7d4hhu",  "nombre": "Cuidado De La Piel"},             # 94
    {"n": "14mninw", "nombre": "Accesorios Perfumería"},          # 127
]

OUTPUT_DIR = Path("output_hogar")

if __name__ == "__main__":
    resultados = {}

    def scrape_cat(cat):
        prods = scrape_categoria(cat["n"], cat["nombre"])
        return cat["n"], prods

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for n_code, prods in ex.map(scrape_cat, CATEGORIAS):
            resultados[n_code] = prods

    todos = []
    for cat in CATEGORIAS:
        todos.extend(resultados[cat["n"]])
        log.info(f"  acumulado: {len(todos)}")

    # Deduplicar por PLU
    vistos = set()
    unicos = [p for p in todos if p["plu"] not in vistos and not vistos.add(p["plu"])]

    log.info(f"\nTotal hogar: {len(unicos)} productos únicos")
    guardar(unicos, OUTPUT_DIR, "coto_hogar")
