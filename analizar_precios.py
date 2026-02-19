"""
analizar_precios.py
===================
Lee los CSVs del dia generados por los 3 scrapers de Coto,
los compara con el historico, calcula variaciones y genera:
  - data/historico.csv         (precio promedio diario por categoria)
  - data/ranking_dia.json      (productos que mas subieron/bajaron hoy)
  - data/ranking_mes.json      (productos que mas subieron en 30 dias)
  - data/ranking_anio.json     (productos que mas subieron en el anio)
  - data/resumen.json          (para la web y el tweet)
"""

import os
import json
import glob
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DIR_DATA       = Path("data")
DIR_OUTPUTS    = Path("outputs")  # donde caen los CSVs de los scrapers
HISTORICO_CSV  = DIR_DATA / "historico.csv"
SNAPSHOT_DIR   = DIR_DATA / "snapshots"  # un CSV por dia con todos los productos

CATEGORIAS_GRUPO = {
    "Bebidas Con Alcohol":   "Bebidas",
    "Bebidas Sin Alcohol":   "Bebidas",
    "Almacen":               "Alimentos",
    "Golosinas":             "Alimentos",
    "Panaderia":             "Alimentos",
    "Snacks":                "Alimentos",
    "Cereales":              "Alimentos",
    "Lacteos":               "Alimentos",
    "Fiambres":              "Alimentos",
    "Quesos":                "Alimentos",
    "Carniceria":            "Alimentos",
    "Frutas Y Verduras":     "Alimentos",
    "Lavado":                "Hogar",
    "Limpieza De Bano":      "Hogar",
    "Limpieza De Cocina":    "Hogar",
    "Cuidado Del Cabello":   "Perfumeria",
    "Higiene Personal":      "Perfumeria",
    "Farmacia":              "Perfumeria",
}


def cargar_csvs_hoy():
    """Carga todos los CSVs generados hoy por los scrapers."""
    hoy = datetime.now().strftime("%Y%m%d")
    patrones = [
        f"outputs/output_bebidas/coto_bebidas_{hoy}*.csv",
        f"outputs/output_alimentos/coto_alimentos_{hoy}*.csv",
        f"outputs/output_hogar/coto_hogar_{hoy}*.csv",
    ]
    dfs = []
    for patron in patrones:
        archivos = glob.glob(patron)
        for archivo in archivos:
            try:
                df = pd.read_csv(archivo, encoding="utf-8-sig")
                dfs.append(df)
                print(f"  Cargado: {archivo} ({len(df)} prods)")
            except Exception as e:
                print(f"  ERROR cargando {archivo}: {e}")
    if not dfs:
        print("ERROR: No se encontraron CSVs de hoy.")
        return None
    df_total = pd.concat(dfs, ignore_index=True)
    print(f"  Total productos hoy: {len(df_total)}")
    return df_total


def guardar_snapshot(df, fecha_str):
    """Guarda una copia del catalogo completo del dia."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ruta = SNAPSHOT_DIR / f"snapshot_{fecha_str}.csv"
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"  Snapshot guardado: {ruta}")


def cargar_snapshot_anterior(fecha_str):
    """Carga el snapshot del dia anterior disponible."""
    archivos = sorted(SNAPSHOT_DIR.glob("snapshot_*.csv"), reverse=True)
    for archivo in archivos:
        nombre = archivo.stem  # snapshot_20260219
        fecha_snap = nombre.replace("snapshot_", "")
        if fecha_snap < fecha_str:
            df = pd.read_csv(archivo, encoding="utf-8-sig")
            print(f"  Snapshot anterior: {archivo} ({len(df)} prods)")
            return df, fecha_snap
    return None, None


def cargar_snapshot_hace_n_dias(dias):
    """Carga el snapshot mas cercano a hace N dias."""
    fecha_objetivo = (datetime.now() - timedelta(days=dias)).strftime("%Y%m%d")
    archivos = sorted(SNAPSHOT_DIR.glob("snapshot_*.csv"))
    candidato = None
    for archivo in archivos:
        fecha_snap = archivo.stem.replace("snapshot_", "")
        if fecha_snap <= fecha_objetivo:
            candidato = archivo
    if candidato:
        df = pd.read_csv(candidato, encoding="utf-8-sig")
        print(f"  Snapshot hace ~{dias} dias: {candidato}")
        return df
    return None


def calcular_variacion_productos(df_hoy, df_antes):
    """
    Compara precio_actual entre dos snapshots por PLU.
    Retorna DataFrame con columnas: plu, nombre, marca, categoria,
    precio_antes, precio_hoy, diff_abs, diff_pct
    """
    df_hoy = df_hoy[["plu", "nombre", "marca", "categoria", "precio_actual"]].copy()
    df_hoy.columns = ["plu", "nombre", "marca", "categoria", "precio_hoy"]
    df_hoy["precio_hoy"] = pd.to_numeric(df_hoy["precio_hoy"], errors="coerce")

    df_antes = df_antes[["plu", "precio_actual"]].copy()
    df_antes.columns = ["plu", "precio_antes"]
    df_antes["precio_antes"] = pd.to_numeric(df_antes["precio_antes"], errors="coerce")

    df = pd.merge(df_hoy, df_antes, on="plu", how="inner")
    df = df.dropna(subset=["precio_hoy", "precio_antes"])
    df = df[df["precio_antes"] > 0]

    df["diff_abs"] = df["precio_hoy"] - df["precio_antes"]
    df["diff_pct"] = ((df["diff_abs"] / df["precio_antes"]) * 100).round(2)

    return df


def calcular_variacion_categoria(df_var):
    """Variacion promedio por categoria."""
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
    """Top N productos que mas subieron o bajaron."""
    df = df_var.sort_values("diff_pct", ascending=ascendente).head(n)
    return df[["plu", "nombre", "marca", "categoria", "precio_antes", "precio_hoy", "diff_abs", "diff_pct"]].to_dict("records")


def actualizar_historico(df_hoy, fecha_str):
    """Agrega una fila al historico con el promedio general del dia."""
    DIR_DATA.mkdir(parents=True, exist_ok=True)
    precio_promedio = pd.to_numeric(df_hoy["precio_actual"], errors="coerce").mean()

    # Por categoria
    df_hoy["precio_actual_num"] = pd.to_numeric(df_hoy["precio_actual"], errors="coerce")
    por_cat = df_hoy.groupby("categoria")["precio_actual_num"].mean().reset_index()
    por_cat.columns = ["categoria", "precio_promedio"]
    por_cat["fecha"] = fecha_str
    por_cat["precio_promedio"] = por_cat["precio_promedio"].round(2)

    if HISTORICO_CSV.exists():
        df_hist = pd.read_csv(HISTORICO_CSV)
        # Evitar duplicados del mismo dia
        df_hist = df_hist[df_hist["fecha"] != fecha_str]
        df_hist = pd.concat([df_hist, por_cat], ignore_index=True)
    else:
        df_hist = por_cat

    df_hist.to_csv(HISTORICO_CSV, index=False)
    print(f"  Historico actualizado: {len(df_hist)} filas")
    return precio_promedio


def generar_graficos_data():
    """
    Lee el historico y genera datos para graficos de la web:
    7 dias, 30 dias, 6 meses, 1 anio — por categoria y total.
    """
    if not HISTORICO_CSV.exists():
        return {}

    df = pd.read_csv(HISTORICO_CSV)
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y%m%d")
    df = df.sort_values("fecha")

    hoy = pd.Timestamp.now()
    periodos = {
        "7d":  hoy - timedelta(days=7),
        "30d": hoy - timedelta(days=30),
        "6m":  hoy - timedelta(days=180),
        "1y":  hoy - timedelta(days=365),
    }

    resultado = {}
    for periodo, fecha_inicio in periodos.items():
        df_periodo = df[df["fecha"] >= fecha_inicio].copy()
        df_periodo["fecha_str"] = df_periodo["fecha"].dt.strftime("%Y-%m-%d")

        # Total general (promedio de todas las categorias)
        total = df_periodo.groupby("fecha_str")["precio_promedio"].mean().reset_index()
        total.columns = ["fecha", "precio"]
        total["precio"] = total["precio"].round(2)

        # Por categoria
        categorias = {}
        for cat in df_periodo["categoria"].unique():
            df_cat = df_periodo[df_periodo["categoria"] == cat]
            cat_data = df_cat[["fecha_str", "precio_promedio"]].copy()
            cat_data.columns = ["fecha", "precio"]
            categorias[cat] = cat_data.to_dict("records")

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

    # 1. Cargar datos de hoy
    print("[1/6] Cargando CSVs de hoy ...")
    df_hoy = cargar_csvs_hoy()
    if df_hoy is None:
        return

    # 2. Guardar snapshot del dia
    print("\n[2/6] Guardando snapshot del dia ...")
    guardar_snapshot(df_hoy, fecha_hoy)

    # 3. Actualizar historico
    print("\n[3/6] Actualizando historico ...")
    precio_promedio_hoy = actualizar_historico(df_hoy, fecha_hoy)

    # 4. Calcular variaciones
    print("\n[4/6] Calculando variaciones ...")
    resumen = {
        "fecha": fecha_hoy,
        "total_productos": len(df_hoy),
        "precio_promedio_hoy": round(float(precio_promedio_hoy), 2),
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

    # Variacion diaria
    df_ayer, _ = cargar_snapshot_anterior(fecha_hoy)
    if df_ayer is not None:
        df_var_dia = calcular_variacion_productos(df_hoy, df_ayer)
        if not df_var_dia.empty:
            resumen["variacion_dia"] = round(float(df_var_dia["diff_pct"].mean()), 2)
            resumen["productos_subieron_dia"] = int((df_var_dia["diff_pct"] > 0).sum())
            resumen["productos_bajaron_dia"] = int((df_var_dia["diff_pct"] < 0).sum())
            resumen["productos_sin_cambio_dia"] = int((df_var_dia["diff_pct"] == 0).sum())
            resumen["ranking_sube_dia"] = top_productos(df_var_dia, 20, ascendente=False)
            resumen["ranking_baja_dia"] = top_productos(df_var_dia, 10, ascendente=True)
            cat_dia = calcular_variacion_categoria(df_var_dia)
            resumen["categorias_dia"] = cat_dia.to_dict("records")
            print(f"  Variacion dia: {resumen['variacion_dia']}%")
            # Guardar ranking dia
            with open(DIR_DATA / "ranking_dia.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_dia"], f, ensure_ascii=False, indent=2)

    # Variacion mensual (30 dias)
    df_mes = cargar_snapshot_hace_n_dias(30)
    if df_mes is not None:
        df_var_mes = calcular_variacion_productos(df_hoy, df_mes)
        if not df_var_mes.empty:
            resumen["variacion_mes"] = round(float(df_var_mes["diff_pct"].mean()), 2)
            resumen["ranking_sube_mes"] = top_productos(df_var_mes, 20, ascendente=False)
            print(f"  Variacion mes: {resumen['variacion_mes']}%")
            with open(DIR_DATA / "ranking_mes.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_mes"], f, ensure_ascii=False, indent=2)

    # Variacion anual (365 dias)
    df_anio = cargar_snapshot_hace_n_dias(365)
    if df_anio is not None:
        df_var_anio = calcular_variacion_productos(df_hoy, df_anio)
        if not df_var_anio.empty:
            resumen["variacion_anio"] = round(float(df_var_anio["diff_pct"].mean()), 2)
            resumen["ranking_sube_anio"] = top_productos(df_var_anio, 20, ascendente=False)
            print(f"  Variacion anio: {resumen['variacion_anio']}%")
            with open(DIR_DATA / "ranking_anio.json", "w", encoding="utf-8") as f:
                json.dump(resumen["ranking_sube_anio"], f, ensure_ascii=False, indent=2)

    # 5. Guardar resumen principal
    print("\n[5/6] Guardando resumen.json ...")
    with open(DIR_DATA / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    # 6. Generar datos para graficos
    print("\n[6/6] Generando datos para graficos ...")
    graficos = generar_graficos_data()
    with open(DIR_DATA / "graficos.json", "w", encoding="utf-8") as f:
        json.dump(graficos, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  ANALISIS COMPLETO")
    print(f"  Productos analizados: {resumen['total_productos']}")
    if resumen["variacion_dia"] is not None:
        emoji = "📈" if resumen["variacion_dia"] > 0 else "📉"
        print(f"  Variacion diaria: {emoji} {resumen['variacion_dia']}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
