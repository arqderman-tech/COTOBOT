"""
tweetear_resumen.py
===================
Lee data/resumen.json y publica en X (Twitter) el resumen diario
de variacion de precios de Coto.
"""

import os
import json
import tweepy
from datetime import datetime
from pathlib import Path

X_API_KEY       = os.getenv("X_API_KEY")
X_API_SECRET    = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN  = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
X_BEARER_TOKEN  = os.getenv("X_BEARER_TOKEN")

DIR_DATA = Path("data")


def formatear_variacion(pct):
    if pct is None:
        return "sin datos"
    emoji = "📈" if pct > 0 else ("📉" if pct < 0 else "➡️")
    signo = "+" if pct > 0 else ""
    return f"{emoji} {signo}{pct:.2f}%"


def armar_tweet_principal(resumen):
    fecha = datetime.now().strftime("%d/%m/%Y")
    var_dia  = formatear_variacion(resumen.get("variacion_dia"))
    var_mes  = formatear_variacion(resumen.get("variacion_mes"))
    var_anio = formatear_variacion(resumen.get("variacion_anio"))

    sube = resumen.get("productos_subieron_dia", 0)
    baja = resumen.get("productos_bajaron_dia", 0)
    igual = resumen.get("productos_sin_cambio_dia", 0)
    total = resumen.get("total_productos", 0)

    tweet = (
        f"🛒 PRECIOS COTO — {fecha}\n"
        f"{'─'*28}\n"
        f"Variación hoy: {var_dia}\n"
        f"Variación 30d: {var_mes}\n"
        f"Variación 1 año: {var_anio}\n\n"
        f"De {total} productos:\n"
        f"⬆️ Subieron: {sube}\n"
        f"⬇️ Bajaron:  {baja}\n"
        f"➡️ Sin cambio: {igual}\n\n"
        f"Ver ranking completo 👇"
    )
    return tweet[:280]


def armar_tweet_categorias(resumen):
    cats = resumen.get("categorias_dia", [])
    if not cats:
        return None

    lineas = ["📊 Variación por categoría hoy:\n"]
    for cat in cats[:8]:  # max 8 categorias para no superar 280 chars
        pct = cat.get("variacion_pct_promedio", 0)
        signo = "+" if pct > 0 else ""
        emoji = "🔴" if pct > 1 else ("🟡" if pct > 0 else ("🟢" if pct < 0 else "⚪"))
        nombre = cat["categoria"][:22]
        lineas.append(f"{emoji} {nombre}: {signo}{pct:.2f}%")

    tweet = "\n".join(lineas)
    return tweet[:280]


def armar_tweet_ranking(resumen):
    ranking = resumen.get("ranking_sube_dia", [])[:5]
    if not ranking:
        return None

    lineas = ["🔥 Los que más subieron hoy:\n"]
    for i, prod in enumerate(ranking, 1):
        nombre = prod["nombre"][:30]
        pct = prod["diff_pct"]
        lineas.append(f"{i}. {nombre} +{pct:.1f}%")

    tweet = "\n".join(lineas)
    return tweet[:280]


def publicar(tweets_validos):
    try:
        client = tweepy.Client(
            bearer_token=X_BEARER_TOKEN,
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )

        respuesta = client.create_tweet(text=tweets_validos[0])
        tweet_id = respuesta.data["id"]
        print(f"✅ Tweet principal publicado (id: {tweet_id})")

        for texto in tweets_validos[1:]:
            respuesta = client.create_tweet(
                text=texto,
                in_reply_to_tweet_id=tweet_id
            )
            tweet_id = respuesta.data["id"]
            print(f"✅ Hilo publicado (id: {tweet_id})")

    except Exception as e:
        print(f"❌ Error publicando en X: {e}")
        raise


def main():
    print(f"\n{'='*50}")
    print(f"  TWEET COTO — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    archivo = DIR_DATA / "resumen.json"
    if not archivo.exists():
        print("❌ No se encontró data/resumen.json. Ejecutá primero analizar_precios.py")
        return

    with open(archivo, encoding="utf-8") as f:
        resumen = json.load(f)

    tweets = []

    t1 = armar_tweet_principal(resumen)
    tweets.append(t1)
    print(f"Tweet 1 ({len(t1)} chars):\n{t1}\n")

    t2 = armar_tweet_categorias(resumen)
    if t2:
        tweets.append(t2)
        print(f"Tweet 2 ({len(t2)} chars):\n{t2}\n")

    t3 = armar_tweet_ranking(resumen)
    if t3:
        tweets.append(t3)
        print(f"Tweet 3 ({len(t3)} chars):\n{t3}\n")

    # Agregar link a la web
    web_url = os.getenv("WEB_URL", "")
    if web_url:
        tweets.append(f"📊 Dashboard completo con gráficos:\n{web_url}")

    publicar(tweets)
    print("\n✅ Hilo publicado correctamente.")


if __name__ == "__main__":
    main()
