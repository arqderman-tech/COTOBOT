"""
analizar_precios.py
===================
Lógica correcta de almacenamiento y comparación de precios.

ALMACENAMIENTO (formato nuevo, comprimido + normalizado):
  data/precios_compacto.csv.gz
    → Fact table: una fila por producto por día
    → Columnas: plu, precio_actual, precio_regular, fecha
  data/productos_meta.json
    → Metadata: plu → {nombre, marca, categoria, cat_principal}
    → Se actualiza con cada corrida (último valor gana)

ÍNDICE % (graficos.json):
    - Por cada día, para cada categoría principal:
      calcular el % de variación promedio de todos los productos
      que existían el día anterior.
    - Acumular esos % día a día (suma acumulada).
    - El primer día siempre es 0%.

COMPARACIONES (resumen.json, rankings):
    - vs día anterior
    - vs ~7 días atrás
    - vs ~30 días atrás
    - vs ~180 días atrás
    - vs ~365 días atrás
    → Producto a producto, categoría a categoría

CATEGORÍAS PRINCIPALES:
    Mapeadas desde la categoría scrapeada al grupo principal
    (Almacén, Frescos, Congelados, Bebidas Con Alcohol,
     Bebidas Sin Alcohol, Limpieza, Cuidado Personal)
"""

import json
import glob
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DIR_DATA             = Path("data")
PRECIOS_COMPACTO     = DIR_DATA / "precios_compacto.csv.gz"
PRECIOS_COMPACTO_OLD = DIR_DATA / "precios_compacto.csv"
PRODUCTOS_META       = DIR_DATA / "productos_meta.json"

# Columnas de la fact table (lo único que crece día a día)
COLS_FACT = ["plu", "precio_actual", "precio_regular", "fecha"]

# ── MAPEO DE CATEGORÍA PRINCIPAL ─────────────────────────────────────────────
CATEGORIA_PRINCIPAL = {
    "Golosinas":                       "Almacén",
    "Panadería":                       "Almacén",
    "Snacks":                          "Almacén",
    "Cereales":                        "Almacén",
    "Endulzantes":                     "Almacén",
    "Aderezos Y Salsas":               "Almacén",
    "Infusiones":                      "Almacén",
    "Conservas":                       "Almacén",
    "Harinas":                         "Almacén",
    "Encurtidos":                      "Almacén",
    "Mermeladas Y Dulces":             "Almacén",
    "Salsas Y Puré De Tomate":         "Almacén",
    "Aceites Y Condimentos":           "Almacén",
    "Alimento Bebés Y Niños":          "Almacén",
    "Arroz Y Legumbres":               "Almacén",
    "Especias":                        "Almacén",
    "Pasta Seca Y Rellenas":           "Almacén",
    "Repostería":                      "Almacén",
    "Sopas Y Saborizantes":            "Almacén",
    "Rebozador Y Pan Rallado":         "Almacén",
    "Leche En Polvo":                  "Almacén",
    "Suplementos Dietarios":           "Almacén",
    "Lácteos":                         "Frescos",
    "Fiambres":                        "Frescos",
    "Quesos":                          "Frescos",
    "Carnicería":                      "Frescos",
    "Aves":                            "Frescos",
    "Pastas Frescas Y Tapas":          "Frescos",
    "Comidas Elaboradas":              "Frescos",
    "Frutas Y Verduras":               "Frescos",
    "Pescadería":                      "Frescos",
    "Huevos":                          "Frescos",
    "Pescadería Congelada":            "Congelados",
    "Nuggets Y Bocaditos":             "Congelados",
    "Hamburguesas Y Milanesas":        "Congelados",
    "Papas Congeladas":                "Congelados",
    "Helados Y Postres":               "Congelados",
    "Comidas Congeladas":              "Congelados",
    "Vegetales Congelados":            "Congelados",
    "Frutas Congeladas":               "Congelados",
    "Bebidas Con Alcohol":             "Bebidas Con Alcohol",
    "Bebidas Sin Alcohol":             "Bebidas Sin Alcohol",
    "Lavado":                          "Limpieza",
    "Accesorios De Limpieza":          "Limpieza",
    "Desodorantes De Ambiente":        "Limpieza",
    "Limpieza De Baño":                "Limpieza",
    "Limpieza De Cocina":              "Limpieza",
    "Limpieza De Pisos Y Superficies": "Limpieza",
    "Lavandinas":                      "Limpieza",
    "Cuidado Del Cabello":             "Cuidado Personal",
    "Higiene Personal":                "Cuidado Personal",
    "Desodorantes Y Antitranspirantes":"Cuidado Personal",
    "Pañales E Incontinencia":         "Cuidado Personal",
    "Cuidado Personal":                "Cuidado Personal",
    "Cuidado Bucal":                   "Cuidado Personal",
    "Protección Femenina":             "Cuidado Personal",
    "Cuidado De La Piel":              "Cuidado Personal",
    "Accesorios Perfumería":           "Cuidado Personal",
}

ORDEN_CATS = [
    "Almacén", "Frescos", "Congelados",
    "Bebidas Con Alcohol", "Bebidas Sin Alcohol",
    "Limpieza", "Cuidado Personal",
]

PERIODOS = {
    "7d":  7,
    "30d": 30,
    "6m":  180,
    "1y":  365,
}


def a_principal(cat):
    cat = str(cat).strip()
    for segmento in cat.split('>'):
        segmento = segmento.strip()
        if segmento in CATEGORIA_PRINCIPAL:
            return CATEGORIA_PRINCIPAL[segmento]
    return cat


# ── METADATA (plu → nombre/marca/categoria) ──────────────────────────────────
def cargar_meta():
    if PRODUCTOS_META.exists():
        with open(PRODUCTOS_META, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_meta(meta):
    with open(PRODUCTOS_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def enriquecer(df, meta):
    """Agrega nombre/marca/categoria/cat_principal desde meta, mapeando por plu."""
    df = df.copy()
    if df.empty:
        for c in ("nombre", "marca", "categoria", "cat_principal"):
            df[c] = ""
        return df
    plu_str = df["plu"].astype(str)
    df["nombre"]        = plu_str.map(lambda p: meta.get(p, {}).get("nombre", ""))
    df["marca"]         = plu_str.map(lambda p: meta.get(p, {}).get("marca", ""))
    df["categoria"]     = plu_str.map(lambda p: meta.get(p, {}).get("categoria", ""))
    df["cat_principal"] = plu_str.map(lambda p: meta.get(p, {}).get("cat_principal", ""))
    return df


def cargar_compacto_enriquecido():
    """Lee la fact table comprimida, deduplica (plu, fecha) y agrega metadata."""
    if not PRECIOS_COMPACTO.exists():
        return pd.DataFrame(columns=COLS_FACT + ["nombre", "marca", "categoria", "cat_principal"])
    df = pd.read_csv(PRECIOS_COMPACTO, dtype={"plu": str, "fecha": str})
    # Sanidad: si por corridas viejas quedaron duplicados (plu, fecha), nos quedamos
    # con el último registro de cada par.
    df = df.drop_duplicates(subset=["plu", "fecha"], keep="last")
    return enriquecer(df, cargar_meta())


def migrar_si_hace_falta():
    """Convierte el CSV viejo (schema completo, sin comprimir) al nuevo formato.
    Corre una sola vez: la primera vez que se ejecute después del deploy."""
    if PRECIOS_COMPACTO_OLD.exists() and not PRECIOS_COMPACTO.exists():
        print("  [MIGRACIÓN] precios_compacto.csv → precios_compacto.csv.gz ...")
        df_old = pd.read_csv(PRECIOS_COMPACTO_OLD, dtype={"plu": str, "fecha": str})
        df_old = df_old.drop_duplicates(subset=["plu", "fecha"], keep="last")

        # Metadata: última aparición de cada PLU
        df_meta = df_old.sort_values("fecha").drop_duplicates("plu", keep="last")
        meta = {}
        for row in df_meta.itertuples(index=False):
            cat = str(getattr(row, "categoria", "") or "")
            cat_p = str(getattr(row, "cat_principal", "") or "") or a_principal(cat)
            meta[str(row.plu)] = {
                "nombre":        str(getattr(row, "nombre", "") or ""),
                "marca":         str(getattr(row, "marca", "") or ""),
                "categoria":     cat,
                "cat_principal": cat_p,
            }
        guardar_meta(meta)

        # Fact table reducida y comprimida
        cols = [c for c in COLS_FACT if c in df_old.columns]
        df_old[cols].to_csv(PRECIOS_COMPACTO, index=False, compression="gzip")

        PRECIOS_COMPACTO_OLD.unlink()
        print(f"  [MIGRACIÓN] OK: {len(df_old)} filas, {len(meta)} productos")


# ── CARGA DE CSVs DEL DÍA ────────────────────────────────────────────────────
def cargar_csvs_hoy():
    hoy = datetime.now().strftime("%Y%m%d")
    patrones = [
        f"outputs/output_bebidas/coto_bebidas_{hoy}*.csv",
        f"outputs/output_alimentos/coto_alimentos_{hoy}*.csv",
        f"outputs/output_hogar/coto_hogar_{hoy}*.csv",
    ]
    dfs = []
    for patron in patrones:
        for archivo in glob.glob(patron):
            try:
                df = pd.read_csv(archivo, encoding="utf-8-sig")
                dfs.append(df)
                print(f"  Cargado: {archivo} ({len(df)} prods)")
            except Exception as e:
                print(f"  ERROR cargando {archivo}: {e}")
    if not dfs:
        print("ERROR: No se encontraron CSVs de hoy.")
        return None
    df = pd.concat(dfs, ignore_index=True)
    print(f"  Total productos hoy: {len(df)}")
    return df


def preparar_df_dia(df_raw, fecha_str):
    cols = ["plu", "nombre", "marca", "categoria", "precio_actual", "precio_regular"]
    cols = [c for c in cols if c in df_raw.columns]
    df = df_raw[cols].copy()

    for col in ["precio_actual", "precio_regular"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["precio_regular"])
    df = df[df["precio_regular"] > 0]
    df = df.drop_duplicates(subset=["plu"], keep="first")
    df["plu"] = df["plu"].astype(str)
    df["fecha"] = fecha_str
    df["cat_principal"] = df["categoria"].apply(a_principal)
    return df


# ── ALMACENAMIENTO ───────────────────────────────────────────────────────────
def guardar_compacto(df_dia, fecha_str):
    """Fact table (4 cols, gzip) + metadata (dict plu→info). Re-run seguro."""
    DIR_DATA.mkdir(parents=True, exist_ok=True)

    # 1) Actualizar metadata con los productos de hoy
    meta = cargar_meta()
    for row in df_dia.itertuples(index=False):
        plu = str(row.plu)
        meta[plu] = {
            "nombre":        str(getattr(row, "nombre", "") or ""),
            "marca":         str(getattr(row, "marca", "") or ""),
            "categoria":     str(getattr(row, "categoria", "") or ""),
            "cat_principal": str(getattr(row, "cat_principal", "") or ""),
        }
    guardar_meta(meta)

    # 2) Guardar fact table comprimida
    df_guardar = df_dia[[c for c in COLS_FACT if c in df_dia.columns]].copy()
    df_guardar["plu"] = df_guardar["plu"].astype(str)

    if PRECIOS_COMPACTO.exists():
        df_hist = pd.read_csv(PRECIOS_COMPACTO, dtype={"plu": str, "fecha": str})
        df_hist = df_hist[df_hist["fecha"] != fecha_str]
        df_nuevo = pd.concat([df_hist, df_guardar], ignore_index=True)
    else:
        df_nuevo = df_guardar

    df_nuevo.to_csv(PRECIOS_COMPACTO, index=False, compression="gzip")
    kb = PRECIOS_COMPACTO.stat().st_size / 1024
    print(f"  precios_compacto.csv.gz: {len(df_nuevo)} filas | {kb:.0f} KB")
    print(f"  productos_meta.json: {len(meta)} productos")

    # 3) Devolver enriquecido (para snapshots y gráficos aguas abajo)
    return enriquecer(df_nuevo, meta)


# ── COMPARACIÓN ──────────────────────────────────────────────────────────────
def snapshot_en_fecha(df_hist, fecha_objetivo_str):
    """Snapshot más reciente <= fecha_objetivo."""
    fechas = sorted(df_hist["fecha"].unique())
    candidato = None
    for f in fechas:
        if f <= fecha_objetivo_str:
            candidato = f
    if candidato is None:
        return None
    df = df_hist[df_hist["fecha"] == candidato].copy()
    print(f"  Snapshot para {fecha_objetivo_str}: {candidato} ({len(df)} prods)")
    return df


def snapshot_anterior(df_hist, fecha_hoy):
    """El snapshot inmediatamente anterior a hoy."""
    fechas = sorted(df_hist["fecha"].unique(), reverse=True)
    for f in fechas:
        if f < fecha_hoy:
            df = df_hist[df_hist["fecha"] == f].copy()
            print(f"  Snapshot anterior: {f} ({len(df)} prods)")
            return df
    return None


def calcular_variacion(df_hoy, df_antes):
    """Producto a producto: diff_pct de precio_regular."""
    df_h = df_hoy[["plu", "nombre", "marca", "categoria", "cat_principal",
                    "precio_actual", "precio_regular"]].copy()
    df_h = df_h.rename(columns={
        "precio_regular": "precio_hoy",
        "precio_actual":  "precio_actual_hoy",
    })
    df_a = df_antes[["plu", "precio_regular"]].rename(
        columns={"precio_regular": "precio_antes"})

    df = pd.merge(df_h, df_a, on="plu", how="inner")
    df = df.dropna(subset=["precio_hoy", "precio_antes"])
    df = df[df["precio_antes"] > 0]
    df["diff_abs"] = (df["precio_hoy"] - df["precio_antes"]).round(2)
    df["diff_pct"] = ((df["diff_abs"] / df["precio_antes"]) * 100).round(2)
    return df


def calcular_variacion_cats(df_var):
    """Variación promedio por categoría principal, ordenada."""
    resumen = df_var.groupby("cat_principal").agg(
        variacion_pct_promedio=("diff_pct", "mean"),
        productos_subieron=("diff_pct", lambda x: (x > 0).sum()),
        productos_bajaron=("diff_pct", lambda x: (x < 0).sum()),
        productos_sin_cambio=("diff_pct", lambda x: (x == 0).sum()),
        total_productos=("diff_pct", "count"),
    ).reset_index()
    resumen = resumen.rename(columns={"cat_principal": "categoria"})
    resumen["variacion_pct_promedio"] = resumen["variacion_pct_promedio"].round(2)
    orden = {cat: i for i, cat in enumerate(ORDEN_CATS)}
    resumen["_ord"] = resumen["categoria"].map(lambda x: orden.get(x, 999))
    return resumen.sort_values("_ord").drop(columns="_ord")


def top_productos(df_var, n=20, ascendente=False):
    df = df_var.sort_values("diff_pct", ascending=ascendente).head(n)
    return df[[
        "plu", "nombre", "marca", "categoria",
        "precio_antes", "precio_hoy", "precio_actual_hoy",
        "diff_abs", "diff_pct"
    ]].to_dict("records")


# ── GRÁFICOS EN % ACUMULADO ──────────────────────────────────────────────────
def generar_graficos_data(df_hist):
    """
    Para cada período construye índices % acumulados.

    Día 0 (primer día del período) = 0%
    Día N = acumulado[N-1] + promedio(diff_pct de productos que existían el día N-1)
    """
    if df_hist.empty:
        return {}

    df_hist = df_hist.copy()
    df_hist["fecha_dt"] = pd.to_datetime(df_hist["fecha"], format="%Y%m%d")
    df_hist = df_hist.sort_values(["fecha_dt", "plu"])

    hoy = pd.Timestamp.now().normalize()
    resultado = {}

    for periodo, dias in PERIODOS.items():
        fecha_inicio = hoy - timedelta(days=dias)
        df_p = df_hist[df_hist["fecha_dt"] >= fecha_inicio].copy()
        fechas = sorted(df_p["fecha_dt"].unique())

        if not fechas:
            resultado[periodo] = {"total": [], "categorias": {}}
            continue

        fecha_str_0 = fechas[0].strftime("%Y-%m-%d")

        # ── Total ────────────────────────────────────────────────────────────
        serie_total = [{"fecha": fecha_str_0, "pct": 0.0}]
        acum = 0.0
        for i in range(1, len(fechas)):
            dv = calcular_variacion(
                df_p[df_p["fecha_dt"] == fechas[i]],
                df_p[df_p["fecha_dt"] == fechas[i - 1]]
            )
            var = float(dv["diff_pct"].mean()) if not dv.empty else 0.0
            acum = round(acum + var, 2)
            serie_total.append({"fecha": fechas[i].strftime("%Y-%m-%d"), "pct": acum})

        # ── Por categoría principal ───────────────────────────────────────────
        series_cats = {}
        for cat in ORDEN_CATS:
            df_cat = df_p[df_p["cat_principal"] == cat]
            if df_cat.empty:
                continue
            serie = [{"fecha": fecha_str_0, "pct": 0.0}]
            acum_cat = 0.0
            for i in range(1, len(fechas)):
                dv = calcular_variacion(
                    df_cat[df_cat["fecha_dt"] == fechas[i]],
                    df_cat[df_cat["fecha_dt"] == fechas[i - 1]]
                )
                var = float(dv["diff_pct"].mean()) if not dv.empty else 0.0
                acum_cat = round(acum_cat + var, 2)
                serie.append({"fecha": fechas[i].strftime("%Y-%m-%d"), "pct": acum_cat})
            series_cats[cat] = serie

        resultado[periodo] = {"total": serie_total, "categorias": series_cats}

    return resultado


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    import sys
    solo_graficos = "--solo-graficos" in sys.argv

    print(f"\n{'='*60}")
    print(f"  ANALISIS COTO — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if solo_graficos:
        print(f"  MODO: solo gráficos (sin scraping)")
    print(f"{'='*60}\n")

    fecha_hoy = datetime.now().strftime("%Y%m%d")
    DIR_DATA.mkdir(parents=True, exist_ok=True)

    # Migración una sola vez del CSV viejo al nuevo formato
    migrar_si_hace_falta()

    if solo_graficos:
        if not PRECIOS_COMPACTO.exists():
            print("ERROR: No existe precios_compacto.csv.gz")
            return
        df_hist = cargar_compacto_enriquecido()
        fecha_hoy = sorted(df_hist["fecha"].unique())[-1]
        df_dia = df_hist[df_hist["fecha"] == fecha_hoy].copy()
        print(f"  Usando fecha más reciente: {fecha_hoy} ({len(df_dia)} prods)")
    else:
        print("[1/5] Cargando CSVs de hoy ...")
        df_raw = cargar_csvs_hoy()
        if df_raw is None:
            return
        df_dia = preparar_df_dia(df_raw, fecha_hoy)
        print("\n[2/5] Guardando precios_compacto (1 fila/producto/día) ...")
        df_hist = guardar_compacto(df_dia, fecha_hoy)

    print("\n[3/5] Calculando variaciones ...")
    resumen = {
        "fecha": fecha_hoy,
        "total_productos": len(df_dia),
        "variacion_dia":  None,
        "variacion_7d":   None,
        "variacion_mes":  None,
        "variacion_6m":   None,
        "variacion_anio": None,
        "categorias_dia": [],
        "ranking_baja_dia": [],
        "productos_subieron_dia": 0,
        "productos_bajaron_dia":  0,
        "productos_sin_cambio_dia": 0,
    }

    # Día anterior
    df_ayer = snapshot_anterior(df_hist, fecha_hoy)
    if df_ayer is not None:
        dv = calcular_variacion(df_dia, df_ayer)
        if not dv.empty:
            resumen["variacion_dia"]            = round(float(dv["diff_pct"].mean()), 2)
            resumen["productos_subieron_dia"]   = int((dv["diff_pct"] > 0).sum())
            resumen["productos_bajaron_dia"]    = int((dv["diff_pct"] < 0).sum())
            resumen["productos_sin_cambio_dia"] = int((dv["diff_pct"] == 0).sum())
            resumen["ranking_baja_dia"]         = top_productos(dv, 10, True)
            resumen["categorias_dia"]           = calcular_variacion_cats(dv).to_dict("records")
            print(f"  Variación día: {resumen['variacion_dia']}%")
            with open(DIR_DATA / "ranking_dia.json", "w", encoding="utf-8") as f:
                json.dump(top_productos(dv, 20, False), f, ensure_ascii=False, indent=2)

    # 7 días
    f7 = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    df_7d = snapshot_en_fecha(df_hist, f7)
    if df_7d is not None:
        dv = calcular_variacion(df_dia, df_7d)
        if not dv.empty:
            resumen["variacion_7d"] = round(float(dv["diff_pct"].mean()), 2)
            print(f"  Variación 7d: {resumen['variacion_7d']}%")
            with open(DIR_DATA / "ranking_7d.json", "w", encoding="utf-8") as f:
                json.dump(top_productos(dv, 20, False), f, ensure_ascii=False, indent=2)

    # 30 días
    f30 = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    df_mes = snapshot_en_fecha(df_hist, f30)
    if df_mes is not None:
        dv = calcular_variacion(df_dia, df_mes)
        if not dv.empty:
            resumen["variacion_mes"] = round(float(dv["diff_pct"].mean()), 2)
            print(f"  Variación 30d: {resumen['variacion_mes']}%")
            with open(DIR_DATA / "ranking_mes.json", "w", encoding="utf-8") as f:
                json.dump(top_productos(dv, 20, False), f, ensure_ascii=False, indent=2)

    # 6 meses
    f6m = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
    df_6m = snapshot_en_fecha(df_hist, f6m)
    if df_6m is not None:
        dv = calcular_variacion(df_dia, df_6m)
        if not dv.empty:
            resumen["variacion_6m"] = round(float(dv["diff_pct"].mean()), 2)
            print(f"  Variación 6m: {resumen['variacion_6m']}%")

    # 1 año
    f1y = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    df_1y = snapshot_en_fecha(df_hist, f1y)
    if df_1y is not None:
        dv = calcular_variacion(df_dia, df_1y)
        if not dv.empty:
            resumen["variacion_anio"] = round(float(dv["diff_pct"].mean()), 2)
            print(f"  Variación 1y: {resumen['variacion_anio']}%")
            with open(DIR_DATA / "ranking_anio.json", "w", encoding="utf-8") as f:
                json.dump(top_productos(dv, 20, False), f, ensure_ascii=False, indent=2)

    print("\n[4/5] Guardando resumen.json ...")
    with open(DIR_DATA / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print("\n[5/5] Generando graficos.json (índices % acumulados) ...")
    graficos = generar_graficos_data(df_hist)
    with open(DIR_DATA / "graficos.json", "w", encoding="utf-8") as f:
        json.dump(graficos, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  LISTO — {resumen['total_productos']} productos")
    for k, v in [("Día",  resumen["variacion_dia"]),
                 ("7d",   resumen["variacion_7d"]),
                 ("30d",  resumen["variacion_mes"]),
                 ("6m",   resumen["variacion_6m"]),
                 ("1año", resumen["variacion_anio"])]:
        if v is not None:
            emoji = "📈" if v > 0 else "📉"
            print(f"  {k}: {emoji} {v}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
