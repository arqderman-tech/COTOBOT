"""
analizar_precios.py
===================
Lee los CSVs del dia generados por los 3 scrapers de Coto.

Almacenamiento:
  - data/precios_compacto.csv  → guarda TODOS los precios por producto por dia
    columnas: plu, nombre, marca, categoria, precio_actual, precio_regular,
              precio_sin_imp, precio_x_unidad, fecha
  - data/historico.csv         → promedio de precio_regular por categoria por dia

Comparacion y seguimiento:
  - Siempre usa precio_regular (precio de lista, sin promos ni descuentos)

Genera:
  - data/resumen.json
  - data/graficos.json
  - data/ranking_dia.json
  - data/ranking_mes.json
  - data/ranking_anio.json
"""

import json
import glob
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DIR_DATA         = Path("data")
HISTORICO_CSV    = DIR_DATA / "historico.csv"
PRECIOS_COMPACTO = DIR_DATA / "precios_compacto.csv"

# Columnas que guardamos del scraper
COLS_GUARDAR = [
    "plu", "nombre", "marca", "categoria",
    "precio_actual", "precio_regular", "precio_sin_imp", "precio_x_unidad",
]


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
    """
    Extrae las columnas relevantes, convierte precios a numerico,
    descarta productos sin precio_regular valido, deduplica por PLU.
    """
    # Solo tomar columnas que existan
    cols = [c for c in COLS_GUARDAR if c in df_raw.columns]
    df = df_raw[cols].copy()

    # Convertir todos los precios a numerico
    for col in ["precio_actual", "precio_regular", "precio_sin_imp", "precio_x_unidad"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Descartar productos sin precio_regular (unico obligatorio para comparacion)
    df = df.dropna(subset=["precio_regular"])
    df = df[df["precio_regular"] > 0]

    df["fecha"] = fecha_str
    df = df.drop_duplicates(subset=["plu"], keep="first")
    df["plu"] = df["plu"].astype(str)
    return df


def guardar_compacto(df_dia, fecha_str):
    """
    Agrega los datos del dia al archivo compacto acumulativo.
    Si ya existia entrada para esta fecha la reemplaza (re-run seguro).
    """
    DIR_DATA.mkdir(parents=True, exist_ok=True)
    if PRECIOS_COMPACTO.exists():
        df_hist = pd.read_csv(PRECIOS_COMPACTO, dtype={"plu": str})
        df_hist = df_hist[df_hist["fecha"] != fecha_str]
        df_nuevo = pd.concat([df_hist, df_dia], ignore_index=True)
    else:
        df_nuevo = df_dia
    df_nuevo.to_csv(PRECIOS_COMPACTO, index=False)
    kb = PRECIOS_COMPACTO.stat().st_size / 1024
    print(f"  precios_compacto.csv: {len(df_nuevo)} filas | {kb:.0f} KB")
    return df_nuevo


def obtener_fecha_anterior(df_hist, fecha_hoy):
    fechas = sorted(df_hist["fecha"].unique(), reverse=True)
    for f in fechas:
        if f < fecha_hoy:
            df = df_hist[df_hist["fecha"] == f].copy()
            print(f"  Snapshot anterior: {f} ({len(df)} prods)")
            return df
    return None


def obtener_df_hace_n_dias(df_hist, n):
    objetivo = (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")
    fechas = sorted(df_hist["fecha"].unique())
    candidato = None
    for f in fechas:
        if f <= objetivo:
            candidato = f
    if candidato:
        df = df_hist[df_hist["fecha"] == candidato].copy()
        print(f"  Snapshot hace ~{n} dias: {candidato} ({len(df)} prods)")
        return df
    return None


def calcular_variacion(df_hoy, df_antes):
    """
    Compara precio_regular entre dos snapshots.
    Retorna DataFrame con diff_abs y diff_pct.
    """
    df_h = df_hoy[["plu", "nombre", "marca", "categoria",
                   "precio_actual", "precio_regular"]].copy()
    df_h = df_h.rename(columns={
        "precio_regular": "precio_hoy",
        "precio_actual":  "precio_actual_hoy",
    })

    df_a = df_antes[["plu", "precio_regular"]].copy()
    df_a = df_a.rename(columns={"precio_regular": "precio_antes"})

    df = pd.merge(df_h, df_a, on="plu", how="inner")
    df = df.dropna(subset=["precio_hoy", "precio_antes"])
    df = df[df["precio_antes"] > 0]
    df["diff_abs"] = (df["precio_hoy"] - df["precio_antes"]).round(2)
    df["diff_pct"] = ((df["diff_abs"] / df["precio_antes"]) * 100).round(2)
    return df


def calcular_variacion_categoria(df_var):
    resumen = df_var.groupby("categoria").agg(
        variacion_pct_promedio=("diff_pct", "mean"),
        productos_subieron=("diff_pct", lambda x: (x > 0).sum()),
        productos_bajaron=("diff_pct", lambda x: (x < 0).sum()),
        productos_sin_cambio=("diff_pct", lambda x: (x == 0).sum()),
        total_productos=("diff_pct", "count"),
    ).reset_index()
    resumen["variacion_pct_promedio"] = resumen["variacion_pct_promedio"].round(2)
    return resumen.sort_values("variacion_pct_promedio", ascending=False)


def top_productos(df_var, n=20, ascendente=False):
    df = df_var.sort_values("diff_pct", ascending=ascendente).head(n)
    return df[[
        "plu", "nombre", "marca", "categoria",
        "precio_antes", "precio_hoy", "precio_actual_hoy",
        "diff_abs", "diff_pct"
    ]].to_dict("records")


def actualizar_historico(df_dia, fecha_str):
    """Promedio de precio_regular por categoria, acumulado por dia."""
    por_cat = df_dia.groupby("categoria")["precio_regular"].mean().reset_index()
    por_cat.columns = ["categoria", "precio_promedio"]
    por_cat["fecha"] = fecha_str
    por_cat["precio_promedio"] = por_cat["precio_promedio"].round(2)

    if HISTORICO_CSV.exists():
        df_h = pd.read_csv(HISTORICO_CSV)
        df_h = df_h[df_h["fecha"] != fecha_str]
        df_h = pd.concat([df_h, por_cat], ignore_index=True)
    else:
        df_h = por_cat
    df_h.to_csv(HISTORICO_CSV, index=False)
    print(f"  historico.csv: {len(df_h)} filas")
    return float(df_dia["precio_regular"].mean())


def generar_graficos_data():
    if not HISTORICO_CSV.exists():
        return {}
    df = pd.read_csv(HISTORICO_CSV)
    df["fecha_dt"] = pd.to_datetime(df["fecha"], format="%Y%m%d")
    df = df.sort_values("fecha_dt")
    hoy = pd.Timestamp.now()
    periodos = {
        "7d":  hoy - timedelta(days=7),
        "30d": hoy - timedelta(days=30),
        "6m":  hoy - timedelta(days=180),
        "1y":  hoy - timedelta(days=365),
    }
    resultado = {}
    for periodo, fecha_inicio in periodos.items():
        df_p = df[df["fecha_dt"] >= fecha_inicio].copy()
        df_p["fecha_str"] = df_p["fecha_dt"].dt.strftime("%Y-%m-%d")
        total = df_p.groupby("fecha_str")["precio_promedio"].mean().reset_index()
        total.columns = ["fecha", "precio"]
        total["precio"] = total["precio"].round(2)
        categorias = {}
        for cat in df_p["categoria"].unique():
            dc = df_p[df_p["categoria"] == cat][["fecha_str", "precio_promedio"]].copy()
            dc.columns = ["fecha", "precio"]
            categorias[cat] = dc.to_dict("records")
        resultado[periodo] = {
            "total": total.to_dict("records"),
            "categorias": categorias,
        }
    return resultado


def main():
    print(f"\n{'='*60}")
    print(f"  ANALISIS COTO — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    fecha_hoy = datetime.now().strftime("%Y%m%d")
    DIR_DATA.mkdir(parents=True, exist_ok=True)

    print("[1/6] Cargando CSVs de hoy ...")
    df_raw = cargar_csvs_hoy()
    if df_raw is None:
        return

    print("\n[2/6] Guardando datos compactos (todos los precios) ...")
    df_dia = preparar_df_dia(df_raw, fecha_hoy)
    df_hist = guardar_compacto(df_dia, fecha_hoy)

    print("\n[3/6] Actualizando historico (precio_regular) ...")
    precio_promedio_hoy = actualizar_historico(df_dia, fecha_hoy)

    print("\n[4/6] Calculando variaciones (comparacion por precio_regular) ...")
    resumen = {
        "fecha": fecha_hoy,
        "total_productos": len(df_dia),
        "precio_promedio_hoy": round(precio_promedio_hoy, 2),
        "variacion_dia": None,
        "variacion_mes": None,
        "variacion_anio": None,
        "categorias_dia": [],
        "ranking_sube_dia": [],
        "ranking_baja_dia": [],
        "ranking_sube_mes": [],
        "ranking_sube_anio": [],
        "productos_subieron_dia": 0,
        "productos_bajaron_dia": 0,
        "productos_sin_cambio_dia": 0,
    }

    df_ayer = obtener_fecha_anterior(df_hist, fecha_hoy)
    if df_ayer is not None:
        dv = calcular_variacion(df_dia, df_ayer)
        if not dv.empty:
            resumen["variacion_dia"] = round(float(dv["diff_pct"].mean()), 2)
            resumen["productos_subieron_dia"] = int((dv["diff_pct"] > 0).sum())
            resumen["productos_bajaron_dia"]  = int((dv["diff_pct"] < 0).sum())
            resumen["productos_sin_cambio_dia"] = int((dv["diff_pct"] == 0).sum())
            resumen["ranking_sube_dia"] = top_productos(dv, 20, False)
            resumen["ranking_baja_dia"] = top_productos(dv, 10, True)
            resumen["categorias_dia"] = calcular_variacion_categoria(dv).to_dict("records")
            print(f"  Variacion dia: {resumen['variacion_dia']}%")
            with open(DIR_DATA / "ranking_dia.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_dia"], f, ensure_ascii=False, indent=2)

    df_mes = obtener_df_hace_n_dias(df_hist, 30)
    if df_mes is not None:
        dv = calcular_variacion(df_dia, df_mes)
        if not dv.empty:
            resumen["variacion_mes"] = round(float(dv["diff_pct"].mean()), 2)
            resumen["ranking_sube_mes"] = top_productos(dv, 20, False)
            print(f"  Variacion mes: {resumen['variacion_mes']}%")
            with open(DIR_DATA / "ranking_mes.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_mes"], f, ensure_ascii=False, indent=2)

    df_anio = obtener_df_hace_n_dias(df_hist, 365)
    if df_anio is not None:
        dv = calcular_variacion(df_dia, df_anio)
        if not dv.empty:
            resumen["variacion_anio"] = round(float(dv["diff_pct"].mean()), 2)
            resumen["ranking_sube_anio"] = top_productos(dv, 20, False)
            print(f"  Variacion anio: {resumen['variacion_anio']}%")
            with open(DIR_DATA / "ranking_anio.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_anio"], f, ensure_ascii=False, indent=2)

    print("\n[5/6] Guardando resumen.json ...")
    with open(DIR_DATA / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print("\n[6/6] Generando datos para graficos ...")
    graficos = generar_graficos_data()
    with open(DIR_DATA / "graficos.json", "w", encoding="utf-8") as f:
        json.dump(graficos, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  LISTO — {resumen['total_productos']} productos")
    if resumen["variacion_dia"] is not None:
        emoji = "📈" if resumen["variacion_dia"] > 0 else "📉"
        print(f"  Hoy: {emoji} {resumen['variacion_dia']}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
