"""
generar_web.py
==============
Lee los JSONs en data/ y genera docs/index.html
para GitHub Pages con graficos, rankings y resumen.

Cambios:
- Graficos en % (base 100 = primer punto = 0%)
- Categorias principales solamente (no subcategorias)
- Tabla de variacion por categoria principal
"""

import json
from pathlib import Path
from datetime import datetime

DIR_DATA = Path("data")
DIR_DOCS = Path("docs")

# Mapeo de subcategoria → categoria principal
# Cualquier categoria que no esté acá se muestra tal cual
CATEGORIA_PRINCIPAL = {
    # ALIMENTOS
    "Golosinas":                  "Almacén",
    "Panadería":                  "Almacén",
    "Snacks":                     "Almacén",
    "Cereales":                   "Almacén",
    "Endulzantes":                "Almacén",
    "Aderezos Y Salsas":          "Almacén",
    "Infusiones":                 "Almacén",
    "Conservas":                  "Almacén",
    "Harinas":                    "Almacén",
    "Encurtidos":                 "Almacén",
    "Mermeladas Y Dulces":        "Almacén",
    "Salsas Y Puré De Tomate":   "Almacén",
    "Aceites Y Condimentos":      "Almacén",
    "Alimento Bebés Y Niños":     "Almacén",
    "Arroz Y Legumbres":          "Almacén",
    "Especias":                   "Almacén",
    "Pasta Seca Y Rellenas":      "Almacén",
    "Repostería":                 "Almacén",
    "Sopas Y Saborizantes":       "Almacén",
    "Rebozador Y Pan Rallado":    "Almacén",
    "Leche En Polvo":             "Almacén",
    "Suplementos Dietarios":      "Almacén",
    # FRESCOS
    "Lácteos":                    "Frescos",
    "Fiambres":                   "Frescos",
    "Quesos":                     "Frescos",
    "Carnicería":                 "Frescos",
    "Aves":                       "Frescos",
    "Pastas Frescas Y Tapas":     "Frescos",
    "Comidas Elaboradas":         "Frescos",
    "Frutas Y Verduras":          "Frescos",
    "Pescadería":                 "Frescos",
    "Huevos":                     "Frescos",
    # CONGELADOS
    "Pescadería Congelada":       "Congelados",
    "Nuggets Y Bocaditos":        "Congelados",
    "Hamburguesas Y Milanesas":   "Congelados",
    "Papas Congeladas":           "Congelados",
    "Helados Y Postres":          "Congelados",
    "Comidas Congeladas":         "Congelados",
    "Vegetales Congelados":       "Congelados",
    "Frutas Congeladas":          "Congelados",
    # BEBIDAS
    "Bebidas Con Alcohol":        "Bebidas Con Alcohol",
    "Bebidas Sin Alcohol":        "Bebidas Sin Alcohol",
    # LIMPIEZA
    "Lavado":                     "Limpieza",
    "Accesorios De Limpieza":     "Limpieza",
    "Desodorantes De Ambiente":   "Limpieza",
    "Limpieza De Baño":           "Limpieza",
    "Limpieza De Cocina":         "Limpieza",
    "Limpieza De Pisos Y Superficies": "Limpieza",
    "Lavandinas":                 "Limpieza",
    # PERFUMERIA / CUIDADO PERSONAL
    "Cuidado Del Cabello":        "Cuidado Personal",
    "Higiene Personal":           "Cuidado Personal",
    "Desodorantes Y Antitranspirantes": "Cuidado Personal",
    "Pañales E Incontinencia":    "Cuidado Personal",
    "Cuidado Personal":           "Cuidado Personal",
    "Cuidado Bucal":              "Cuidado Personal",
    "Protección Femenina":        "Cuidado Personal",
    "Cuidado De La Piel":         "Cuidado Personal",
    "Accesorios Perfumería":      "Cuidado Personal",
}

# Orden de display de categorías principales
ORDEN_CATS = [
    "Almacén", "Frescos", "Congelados",
    "Bebidas Con Alcohol", "Bebidas Sin Alcohol",
    "Limpieza", "Cuidado Personal",
]


def leer_json(nombre):
    ruta = DIR_DATA / nombre
    if ruta.exists():
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


def a_principal(cat):
    """Devuelve la categoría principal para una subcategoría."""
    return CATEGORIA_PRINCIPAL.get(cat, cat)


def agrupar_graficos_por_principal(graficos):
    """
    El nuevo analizar_precios.py ya genera graficos.json con:
    - categorías principales (no subcategorías)
    - campo "pct" (no "precio")
    Esta función simplemente reordena según ORDEN_CATS.
    """
    resultado = {}
    for periodo, datos in graficos.items():
        resultado[periodo] = {"total": [], "categorias": {}}

        # Serie total — ya tiene "pct"
        serie_total = datos.get("total", [])
        if serie_total and "pct" in serie_total[0]:
            resultado[periodo]["total"] = serie_total
        else:
            # Compatibilidad con formato viejo que tenía "precio"
            resultado[periodo]["total"] = _a_pct(serie_total)

        # Categorías — ya son principales con "pct"
        cats_raw = datos.get("categorias", {})
        cats_ordenadas = {}

        # Si no hay categorías (primer día), crear punto 0% para cada cat principal
        # usando la fecha del total
        if not cats_raw and serie_total:
            fecha_0 = serie_total[0]["fecha"]
            for cat in ORDEN_CATS:
                cats_ordenadas[cat] = [{"fecha": fecha_0, "pct": 0.0}]
        else:
            for cat in ORDEN_CATS:
                if cat in cats_raw:
                    serie = cats_raw[cat]
                    if serie and "pct" in serie[0]:
                        cats_ordenadas[cat] = serie
                    else:
                        cats_ordenadas[cat] = _a_pct(serie)
            # Las que no están en ORDEN_CATS
            for cat, serie in cats_raw.items():
                if cat not in cats_ordenadas:
                    if serie and "pct" in serie[0]:
                        cats_ordenadas[cat] = serie
                    else:
                        cats_ordenadas[cat] = _a_pct(serie)

        resultado[periodo]["categorias"] = cats_ordenadas

    return resultado


def _a_pct(serie):
    """Convierte una serie [{fecha, precio}] a índice % donde el primer punto = 0%."""
    if not serie:
        return []
    base = serie[0].get("precio")
    if not base or base == 0:
        return [{"fecha": p["fecha"], "pct": 0} for p in serie]
    return [
        {"fecha": p["fecha"], "pct": round((p.get("precio", base) / base - 1) * 100, 2)}
        for p in serie
    ]


def agrupar_cats_dia(cats_dia):
    """Agrupa la tabla de categorías del día en categorías principales."""
    acum = {}
    for cat in cats_dia:
        nombre = cat.get("categoria", "")
        principal = a_principal(nombre)
        if principal not in acum:
            acum[principal] = {
                "categoria": principal,
                "variacion_sum": 0,
                "count": 0,
                "productos_subieron": 0,
                "productos_bajaron": 0,
                "total_productos": 0,
            }
        pct = cat.get("variacion_pct_promedio", 0) or 0
        acum[principal]["variacion_sum"] += pct
        acum[principal]["count"] += 1
        acum[principal]["productos_subieron"] += cat.get("productos_subieron", 0)
        acum[principal]["productos_bajaron"] += cat.get("productos_bajaron", 0)
        acum[principal]["total_productos"] += cat.get("total_productos", 0)

    resultado = []
    for principal in ORDEN_CATS:
        if principal in acum:
            d = acum[principal]
            d["variacion_pct_promedio"] = d["variacion_sum"] / d["count"] if d["count"] else 0
            resultado.append(d)
    # Las que no están en ORDEN_CATS
    for principal, d in acum.items():
        if principal not in ORDEN_CATS:
            d["variacion_pct_promedio"] = d["variacion_sum"] / d["count"] if d["count"] else 0
            resultado.append(d)
    return resultado


def main():
    DIR_DOCS.mkdir(exist_ok=True)

    resumen   = leer_json("resumen.json") or {}
    graficos  = leer_json("graficos.json") or {}
    rank_dia  = leer_json("ranking_dia.json") or []
    rank_mes  = leer_json("ranking_mes.json") or []
    rank_anio = leer_json("ranking_anio.json") or []

    # Agrupar graficos por categoría principal y convertir a %
    graficos_agrupados = agrupar_graficos_por_principal(graficos)

    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    var_dia   = resumen.get("variacion_dia")
    var_mes   = resumen.get("variacion_mes")
    var_anio  = resumen.get("variacion_anio")
    total     = resumen.get("total_productos", 0)
    sube      = resumen.get("productos_subieron_dia", 0)
    baja      = resumen.get("productos_bajaron_dia", 0)
    igual     = resumen.get("productos_sin_cambio_dia", 0)
    cats_dia  = resumen.get("categorias_dia", [])

    # Agrupar tabla de categorías
    cats_dia_agrupadas = agrupar_cats_dia(cats_dia)

    def fmt_pct(v):
        if v is None: return "—"
        signo = "+" if v > 0 else ""
        return f"{signo}{v:.2f}%"

    def color_pct(v):
        if v is None: return "#888"
        if v > 0: return "#ef4444"
        if v < 0: return "#22c55e"
        return "#888"

    # Serializar datos para JS
    graficos_js  = json.dumps(graficos_agrupados, ensure_ascii=False)
    rank_dia_js  = json.dumps(rank_dia[:20], ensure_ascii=False)
    rank_mes_js  = json.dumps(rank_mes[:20], ensure_ascii=False)
    rank_anio_js = json.dumps(rank_anio[:20], ensure_ascii=False)

    # Generar filas de categorias (ya agrupadas)
    filas_cats = ""
    for cat in cats_dia_agrupadas:
        pct = cat.get("variacion_pct_promedio", 0)
        color = color_pct(pct)
        filas_cats += f"""
        <tr>
          <td>{cat['categoria']}</td>
          <td style="color:{color};font-weight:700">{fmt_pct(pct)}</td>
          <td style="color:#ef4444">⬆ {cat.get('productos_subieron',0)}</td>
          <td style="color:#22c55e">⬇ {cat.get('productos_bajaron',0)}</td>
          <td>{cat.get('total_productos',0)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Precios Coto – Tracker Diario</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;600;700&display=swap');

  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --accent: #f59e0b;
    --red: #ef4444;
    --green: #22c55e;
    --text: #e2e8f0;
    --muted: #64748b;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; }}

  header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
  }}
  header h1 {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; color: var(--accent); }}
  header .fecha {{ font-size: 0.8rem; color: var(--muted); font-family: 'IBM Plex Mono', monospace; }}

  .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }}

  .hero {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }}
  .stat-card .label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.5rem; }}
  .stat-card .value {{ font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 700; }}
  .stat-card .sub {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.3rem; }}

  .section {{ margin-bottom: 2.5rem; }}
  .section-title {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--muted);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
  }}

  .tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .tab {{
    padding: 0.4rem 1rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    transition: all 0.2s;
  }}
  .tab.active, .tab:hover {{
    background: var(--accent);
    color: #000;
    border-color: var(--accent);
  }}

  .chart-container {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    position: relative;
    height: 320px;
  }}

  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th {{
    background: var(--surface);
    padding: 0.7rem 1rem;
    text-align: left;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}
  td {{ padding: 0.65rem 1rem; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .rank-num {{ font-family: 'IBM Plex Mono', monospace; color: var(--muted); font-size: 0.75rem; }}

  .rank-tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; }}
  .rank-tab {{
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.2s;
  }}
  .rank-tab.active {{ background: var(--surface); color: var(--text); border-color: var(--accent); }}

  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  @media (max-width: 700px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}

  footer {{
    text-align: center;
    padding: 2rem;
    color: var(--muted);
    font-size: 0.75rem;
    border-top: 1px solid var(--border);
    font-family: 'IBM Plex Mono', monospace;
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>🛒 COTO PRICE TRACKER</h1>
    <div style="color:var(--muted);font-size:0.8rem;margin-top:0.2rem">Seguimiento diario de precios del supermercado</div>
  </div>
  <div class="fecha">Última actualización: {fecha_str}</div>
</header>

<div class="container">

  <div class="hero" style="margin-top:1.5rem">
    <div class="stat-card">
      <div class="label">Variación Hoy</div>
      <div class="value" style="color:{color_pct(var_dia)}">{fmt_pct(var_dia)}</div>
      <div class="sub">{total} productos relevados</div>
    </div>
    <div class="stat-card">
      <div class="label">Variación 30 días</div>
      <div class="value" style="color:{color_pct(var_mes)}">{fmt_pct(var_mes)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Variación 1 año</div>
      <div class="value" style="color:{color_pct(var_anio)}">{fmt_pct(var_anio)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Movimiento Hoy</div>
      <div style="display:flex;justify-content:center;gap:1rem;margin-top:0.5rem">
        <div><div style="color:#ef4444;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">⬆ {sube}</div><div style="font-size:0.7rem;color:var(--muted)">Subieron</div></div>
        <div><div style="color:#22c55e;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">⬇ {baja}</div><div style="font-size:0.7rem;color:var(--muted)">Bajaron</div></div>
        <div><div style="color:#888;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">➡ {igual}</div><div style="font-size:0.7rem;color:var(--muted)">Igual</div></div>
      </div>
    </div>
  </div>

  <!-- GRAFICO HISTORICO EN % -->
  <div class="section">
    <div class="section-title">📈 Evolución de precios</div>
    <div class="tabs">
      <button class="tab active" onclick="cambiarPeriodo('7d', this)">7 días</button>
      <button class="tab" onclick="cambiarPeriodo('30d', this)">30 días</button>
      <button class="tab" onclick="cambiarPeriodo('6m', this)">6 meses</button>
      <button class="tab" onclick="cambiarPeriodo('1y', this)">1 año</button>
    </div>
    <div class="chart-container">
      <canvas id="chartGeneral"></canvas>
    </div>
  </div>

  <!-- GRAFICO POR CATEGORIA PRINCIPAL EN % -->
  <div class="section">
    <div class="section-title">📊 Evolución por categoría</div>
    <div id="selectorCat" style="margin-bottom:1rem;display:flex;gap:0.5rem;flex-wrap:wrap"></div>
    <div class="chart-container">
      <canvas id="chartCat"></canvas>
    </div>
  </div>

  <!-- TABLA CATEGORIAS PRINCIPALES -->
  <div class="section">
    <div class="section-title">🗂 Variación por categoría — hoy</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Categoría</th>
            <th>Variación %</th>
            <th>Subieron</th>
            <th>Bajaron</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {filas_cats}
        </tbody>
      </table>
    </div>
  </div>

  <!-- RANKINGS -->
  <div class="section">
    <div class="section-title">🏆 Rankings de productos</div>
    <div class="rank-tabs">
      <button class="rank-tab active" onclick="mostrarRanking('dia', this)">📅 Hoy</button>
      <button class="rank-tab" onclick="mostrarRanking('mes', this)">📆 30 días</button>
      <button class="rank-tab" onclick="mostrarRanking('anio', this)">📅 1 año</button>
    </div>
    <div class="grid2">
      <div>
        <div style="font-size:0.8rem;color:var(--muted);margin-bottom:0.7rem">🔥 Los que más SUBIERON</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Producto</th><th>Var %</th><th>Precio</th></tr></thead>
            <tbody id="tabla-sube"></tbody>
          </table>
        </div>
      </div>
      <div>
        <div style="font-size:0.8rem;color:var(--muted);margin-bottom:0.7rem">📉 Los que más BAJARON hoy</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Producto</th><th>Var %</th><th>Precio</th></tr></thead>
            <tbody id="tabla-baja"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

</div>

<footer>
  Datos relevados de cotodigital3.com.ar · Actualización automática diaria via GitHub Actions<br>
  Los precios pueden variar según sucursal y disponibilidad
</footer>

<script>
const GRAFICOS = {graficos_js};
const RANK_DIA  = {rank_dia_js};
const RANK_MES  = {rank_mes_js};
const RANK_ANIO = {rank_anio_js};
const RANK_BAJA = {json.dumps(resumen.get('ranking_baja_dia', [])[:10], ensure_ascii=False)};

let periodoActual = '7d';
let chartGeneral = null;
let chartCat = null;
let catActual = null;

// ── GRAFICO GENERAL EN % ─────────────────────────────────────────────────────
function cambiarPeriodo(periodo, btn) {{
  periodoActual = periodo;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderChartGeneral(periodo);
  renderSelectorCats(periodo);
}}

function renderChartGeneral(periodo) {{
  const datos = GRAFICOS[periodo]?.total || [];
  const labels = datos.map(d => d.fecha);
  const values = datos.map(d => d.pct);          // YA en %

  if (chartGeneral) chartGeneral.destroy();
  const ctx = document.getElementById('chartGeneral').getContext('2d');
  chartGeneral = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: 'Variación acumulada %',
        data: values,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.08)',
        borderWidth: 2,
        pointRadius: labels.length > 60 ? 0 : 3,
        tension: 0.3,
        fill: true,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#2a2d3a' }} }},
        y: {{
          ticks: {{
            color: '#64748b',
            callback: v => (v > 0 ? '+' : '') + v.toFixed(1) + '%'
          }},
          grid: {{ color: '#2a2d3a' }},
          // Línea de base en 0
          afterDataLimits: axis => {{
            if (axis.min > 0) axis.min = 0;
            if (axis.max < 0) axis.max = 0;
          }}
        }}
      }}
    }}
  }});
}}

// ── GRAFICO POR CATEGORIA PRINCIPAL EN % ─────────────────────────────────────
function renderSelectorCats(periodo) {{
  // Usar categorías del JSON; si no hay, mostrar las 7 principales igual
  const CATS_DEFAULT = ['Almacén','Frescos','Congelados','Bebidas Con Alcohol','Bebidas Sin Alcohol','Limpieza','Cuidado Personal'];
  const catsJSON = Object.keys(GRAFICOS[periodo]?.categorias || {{}});
  const cats = catsJSON.length ? catsJSON : CATS_DEFAULT;
  const cont = document.getElementById('selectorCat');
  cont.innerHTML = '';
  if (!catActual || !cats.includes(catActual)) catActual = cats[0];
  cats.forEach(cat => {{
    const btn = document.createElement('button');
    btn.className = 'tab' + (cat === catActual ? ' active' : '');
    btn.textContent = cat;
    btn.onclick = () => {{
      catActual = cat;
      document.querySelectorAll('#selectorCat .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderChartCat(periodo, cat);
    }};
    cont.appendChild(btn);
  }});
  renderChartCat(periodo, catActual);
}}

function renderChartCat(periodo, cat) {{
  const datos = GRAFICOS[periodo]?.categorias?.[cat] || [];
  const labels = datos.map(d => d.fecha);
  const values = datos.map(d => d.pct);          // YA en %

  if (chartCat) chartCat.destroy();
  const ctx = document.getElementById('chartCat').getContext('2d');
  chartCat = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: cat + ' — variación %',
        data: values,
        borderColor: '#60a5fa',
        backgroundColor: 'rgba(96,165,250,0.08)',
        borderWidth: 2,
        pointRadius: labels.length > 60 ? 0 : 3,
        tension: 0.3,
        fill: true,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#2a2d3a' }} }},
        y: {{
          ticks: {{
            color: '#64748b',
            callback: v => (v > 0 ? '+' : '') + v.toFixed(1) + '%'
          }},
          grid: {{ color: '#2a2d3a' }},
          afterDataLimits: axis => {{
            if (axis.min > 0) axis.min = 0;
            if (axis.max < 0) axis.max = 0;
          }}
        }}
      }}
    }}
  }});
}}

// ── RANKINGS ─────────────────────────────────────────────────────────────────
function mostrarRanking(periodo, btn) {{
  document.querySelectorAll('.rank-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const mapas = {{ dia: RANK_DIA, mes: RANK_MES, anio: RANK_ANIO }};
  const data = mapas[periodo] || [];
  renderTablaRanking('tabla-sube', data, false);
  if (periodo === 'dia') renderTablaRanking('tabla-baja', RANK_BAJA, true);
  else document.getElementById('tabla-baja').innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:1rem">Solo disponible para hoy</td></tr>';
}}

function renderTablaRanking(id, data, esBaja) {{
  const tbody = document.getElementById(id);
  if (!data.length) {{
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:1rem">Sin datos aún</td></tr>';
    return;
  }}
  tbody.innerHTML = data.slice(0, 20).map((p, i) => {{
    const pct = p.diff_pct;
    const color = esBaja ? '#22c55e' : '#ef4444';
    const signo = pct > 0 ? '+' : '';
    const nombre = (p.nombre || '').substring(0, 35);
    const precio = p.precio_hoy ? '$' + Number(p.precio_hoy).toLocaleString('es-AR') : '—';
    return `<tr>
      <td class="rank-num">${{i+1}}</td>
      <td title="${{p.nombre}}"><div>${{nombre}}</div><div style="font-size:0.7rem;color:var(--muted)">${{p.marca || ''}} · ${{(p.categoria||'').substring(0,20)}}</div></td>
      <td style="color:${{color}};font-weight:700;font-family:'IBM Plex Mono',monospace">${{signo}}${{pct?.toFixed(1)}}%</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:0.82rem">${{precio}}</td>
    </tr>`;
  }}).join('');
}}

// ── INIT ─────────────────────────────────────────────────────────────────────
renderChartGeneral('7d');
renderSelectorCats('7d');
mostrarRanking('dia', document.querySelector('.rank-tab'));
</script>
</body>
</html>"""

    ruta = DIR_DOCS / "index.html"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Web generada: {ruta}")


if __name__ == "__main__":
    main()
