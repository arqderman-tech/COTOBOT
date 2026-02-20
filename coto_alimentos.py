"""
Coto Digital — Scraper ALIMENTOS
Categorías: Almacén completo + Frescos + Congelados
N-codes validados contra el catálogo en vivo.

Uso: python coto_alimentos.py
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from coto_base import scrape_categoria, guardar, log, MAX_WORKERS
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# N-codes obtenidos navegando el árbol endeca en vivo
# Solo se obtienen productos con stock vigente (filtro automático del endeca)
CATEGORIAS = [
    # ── ALMACÉN ──────────────────────────────────────────────────────────────
    {"n": "8pub5z",   "nombre": "Almacén"},               # 5145 total (usar como fallback)
    {"n": "1y5dh9i",  "nombre": "Golosinas"},             # 614
    {"n": "s3bf1a",   "nombre": "Panadería"},             # 1047
    {"n": "10kzbyj",  "nombre": "Snacks"},                # 299
    {"n": "ukd5id",   "nombre": "Cereales"},              # 224
    {"n": "1rtbab6",  "nombre": "Endulzantes"},           # 107
    {"n": "rv0frc",   "nombre": "Aderezos Y Salsas"},     # 237
    {"n": "dw58vw",   "nombre": "Infusiones"},            # 595
    {"n": "1t4efca",  "nombre": "Conservas"},             # 172
    {"n": "842qrm",   "nombre": "Harinas"},               # 126
    {"n": "12rkdi1",  "nombre": "Encurtidos"},            # 98
    {"n": "mj4aa8",   "nombre": "Mermeladas Y Dulces"},   # 221
    {"n": "os1anu",   "nombre": "Salsas Y Puré De Tomate"}, # 96
    {"n": "18r69ct",  "nombre": "Aceites Y Condimentos"}, # 335
    {"n": "nnh9fj",   "nombre": "Alimento Bebés Y Niños"},# 50
    {"n": "c0x2yz",   "nombre": "Arroz Y Legumbres"},     # 129
    {"n": "1t0tm80",  "nombre": "Especias"},              # 225
    {"n": "tvb9c7",   "nombre": "Pasta Seca Y Rellenas"}, # 193
    {"n": "a6cxru",   "nombre": "Repostería"},            # 187
    {"n": "10vvk4q",  "nombre": "Sopas Y Saborizantes"},  # 100
    {"n": "mz3nfh",   "nombre": "Rebozador Y Pan Rallado"},# 25
    {"n": "1yw5bwj",  "nombre": "Leche En Polvo"},        # 26
    {"n": "qe3p7f",   "nombre": "Suplementos Dietarios"}, # 31
    # ── FRESCOS ───────────────────────────────────────────────────────────────
    {"n": "1d443r9",  "nombre": "Lácteos"},               # 570
    {"n": "1j6o93y",  "nombre": "Fiambres"},              # 290
    {"n": "1d0721n",  "nombre": "Quesos"},                # 499
    {"n": "176whnp",  "nombre": "Carnicería"},            # 131
    {"n": "6drhk5",   "nombre": "Aves"},                  # 21
    {"n": "1e4im7l",  "nombre": "Pastas Frescas Y Tapas"},# 164
    {"n": "l535ea",   "nombre": "Comidas Elaboradas"},    # 143
    {"n": "zxw18u",   "nombre": "Frutas Y Verduras"},     # 367
    {"n": "yxu4b7",   "nombre": "Pescadería"},            # 16
    {"n": "mtdtw6",   "nombre": "Huevos"},                # 17
    # ── CONGELADOS ────────────────────────────────────────────────────────────
    {"n": "wgo47s",   "nombre": "Pescadería Congelada"},  # 139
    {"n": "uh4qr",    "nombre": "Nuggets Y Bocaditos"},   # 53
    {"n": "15wfcx5",  "nombre": "Hamburguesas Y Milanesas"}, # 163
    {"n": "1vcscvz",  "nombre": "Papas Congeladas"},      # 28
    {"n": "cor40m",   "nombre": "Helados Y Postres"},     # 169
    {"n": "m17c6b",   "nombre": "Comidas Congeladas"},    # 94
    {"n": "8efwh3",   "nombre": "Vegetales Congelados"},  # 29
    {"n": "14w51iy",  "nombre": "Frutas Congeladas"},     # 25
]

OUTPUT_DIR = Path("output_alimentos")

if __name__ == "__main__":
    # Excluir la raíz "Almacén" para no duplicar
    cats_sin_raiz = [c for c in CATEGORIAS if c["n"] != "8pub5z"]

    # ── Todas las categorías en paralelo ─────────────────────────────────────
    resultados = {}   # n_code → lista de productos

    def scrape_cat(cat):
        prods = scrape_categoria(cat["n"], cat["nombre"])
        return cat["n"], prods

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scrape_cat, cat): cat for cat in cats_sin_raiz}
        for future in futures:
            n_code, prods = future.result()
            resultados[n_code] = prods

    # Acumular en el orden original de CATEGORIAS
    todos = []
    for cat in cats_sin_raiz:
        todos.extend(resultados[cat["n"]])
        log.info(f"  acumulado: {len(todos)}")

    # Deduplicar por PLU (puede haber solapamiento entre subcategorías hermanas)
    vistos = set()
    unicos = []
    for p in todos:
        if p["plu"] not in vistos:
            vistos.add(p["plu"])
            unicos.append(p)

    log.info(f"\nTotal alimentos: {len(unicos)} productos únicos ({len(todos)} con duplicados)")
    guardar(unicos, OUTPUT_DIR, "coto_alimentos")
