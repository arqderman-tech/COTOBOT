"""
coto_base.py – Motor genérico de scraping para Coto Digital
Requiere: requests, selectolax
"""

import json, csv, time, logging, re
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from pathlib import Path
from datetime import datetime
import ssl
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_BROWSE = "https://www.cotodigital3.com.ar/sitios/cdigi/browse/_"
NRPP  = 50
DELAY = 1.0
DELAY_JITTER = 0.5

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Accept": "application/json",
    "Referer": "https://www.cotodigital3.com.ar/",
}


def get_json(url, retries=3):
    for i in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, context=SSL_CTX, timeout=20) as r:
                return json.loads(r.read())
        except (HTTPError, URLError) as e:
            log.warning(f"  intento {i+1}: {e}  url={url[:80]}")
            time.sleep(2 ** i)
    return None


def _find_results(data):
    """
    Busca recursivamente el dict con 'totalNumRecs' y 'records'
    dentro de data["contents"][0].
    """
    if not data:
        return None

    def _search(obj):
        if isinstance(obj, dict):
            if "totalNumRecs" in obj and "records" in obj:
                return obj
            for v in obj.values():
                r = _search(v)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = _search(item)
                if r is not None:
                    return r
        return None

    try:
        root = data["contents"][0]
    except (KeyError, IndexError):
        return None

    return _search(root)


def _parse_precio(texto):
    """Extrae float de strings como '$1.310,05' -> 1310.05"""
    if not texto:
        return None
    clean = re.sub(r"[^\d,.]", "", str(texto))
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


def extraer_producto(rec_outer, cat_nombre):
    rec   = rec_outer.get("records", [{}])[0]
    attrs = rec.get("attributes", {})

    def get1(key, default=""):
        v = attrs.get(key, [default])
        return v[0] if isinstance(v, list) else v

    plu = get1("product.repositoryId").replace("prod", "")
    ean = get1("product.eanPrincipal")
    nombre = get1("product.displayName")
    marca  = (get1("product.MARCA") or get1("product.brand")).title()

    cat_parts = [c for c in attrs.get("allAncestors.displayName", [])
                 if c not in ("CotoDigital", "")]
    cat_full  = " > ".join(reversed(cat_parts)) if cat_parts else cat_nombre

    record_id = get1("record.id")
    url_prod  = (f"https://www.cotodigital3.com.ar/sitios/cdigi/producto/_/R-{record_id}"
                 if record_id else "")
    imagen    = get1("product.largeImage.url") or get1("product.mediumImage.url")

    desc_unidad = get1("product.unidades.descUnidad")
    c_formato   = get1("product.cFormato", "").strip()
    es_pesable  = get1("product.unidades.esPesable") == "1"

    try:
        precio_regular = float(get1("sku.activePrice") or 0) or None
    except Exception:
        precio_regular = None

    try:
        dp = json.loads(get1("sku.dtoPrice") or "{}")
    except Exception:
        dp = {}
    precio_sin_imp = dp.get("precioSinImp")

    try:
        precio_x_unidad = float(get1("sku.referencePrice") or 0) or None
    except Exception:
        precio_x_unidad = None

    if precio_x_unidad:
        if desc_unidad in ("KGS", "GRM"):
            unidad_label = "por 100 Gramos"
        elif desc_unidad in ("LTS", "LIT"):
            unidad_label = "por Lt"
        else:
            unidad_label = f"por {c_formato or desc_unidad or 'unidad'}"
    else:
        unidad_label = ""

    try:
        descuentos = json.loads(get1("product.dtoDescuentos", "[]"))
    except Exception:
        descuentos = []

    promo_texto = promo_regular = ""
    precio_actual = precio_regular

    if descuentos:
        d = descuentos[0]
        promo_texto   = (d.get("textoDescuento") or d.get("textoLlevando") or "").strip()
        promo_regular = (d.get("textoPrecioRegular") or "").strip()
        precio_dto = _parse_precio(d.get("precioDescuento"))
        if precio_dto:
            precio_actual = precio_dto

    return {
        "supermercado":    "coto",
        "plu":             plu,
        "ean":             ean,
        "nombre":          nombre,
        "marca":           marca,
        "categoria":       cat_full,
        "precio_actual":   precio_actual,
        "precio_regular":  precio_regular,
        "precio_sin_imp":  precio_sin_imp,
        "precio_x_unidad": precio_x_unidad,
        "unidad_label":    unidad_label,
        "unidad":          desc_unidad,
        "es_pesable":      es_pesable,
        "promo_texto":     promo_texto,
        "promo_regular":   promo_regular,
        "imagen":          imagen,
        "url":             url_prod,
        "fecha":           datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def scrape_categoria(n_code, cat_nombre):
    """Scrapea todas las paginas de una categoria usando N-code Endeca."""
    todos  = []
    offset = 0
    log.info(f"-> {cat_nombre} (N-{n_code})")

    while True:
        url  = f"{BASE_BROWSE}/N-{n_code}?Nrpp={NRPP}&No={offset}&format=json"
        data = get_json(url)

        if not data:
            log.warning(f"  WARNING {cat_nombre}: sin respuesta en offset {offset}")
            break

        main = _find_results(data)

        if main is None:
            try:
                claves = list(data["contents"][0].keys())
            except Exception:
                claves = list(data.keys())
            log.warning(f"  WARNING {cat_nombre}: no se encontro bloque de resultados. Claves raiz: {claves}")
            break

        records = main.get("records", [])
        total   = int(main.get("totalNumRecs", 0))

        if not records:
            log.warning(f"  WARNING {cat_nombre}: 0 registros en offset {offset} (totalNumRecs={total})")
            break

        for rec_outer in records:
            todos.append(extraer_producto(rec_outer, cat_nombre))

        log.info(f"  offset {offset} | {len(todos)}/{total}")
        offset += NRPP
        if offset >= total:
            break

        time.sleep(DELAY + random.uniform(0, DELAY_JITTER))

    return todos


CAMPOS = [
    "supermercado", "plu", "ean", "nombre", "marca", "categoria",
    "precio_actual", "precio_regular", "precio_sin_imp",
    "precio_x_unidad", "unidad_label", "unidad", "es_pesable",
    "promo_texto", "promo_regular", "imagen", "url", "fecha",
]


def guardar(todos, output_dir: Path, nombre_archivo: str):
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    ruta_csv  = output_dir / f"{nombre_archivo}_{ts}.csv"
    ruta_json = output_dir / f"{nombre_archivo}_{ts}.json"

    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        writer.writerows(todos)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    log.info(f"OK CSV  -> {ruta_csv}  ({len(todos)} prods)")
    log.info(f"OK JSON -> {ruta_json}")
    return ruta_csv
