from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, Dispatcher
import os, asyncio, requests, re
from bs4 import BeautifulSoup

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

seen_links = set()
SEARCH_URL = "https://www.olx.pl/oferty/q-lego-kg/?search%5Bfilter_float_price%3Afrom%5D=1000"

async def fetch_offers():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(SEARCH_URL, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Błąd OLX: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    offers = []
    for offer in soup.select("div[data-cy='l-card']"):
        link_tag = offer.find("a", href=True)
        title_tag = offer.find("h6")
        price_tag = offer.find("p", {"data-testid": "ad-price"})
        location_tag = offer.find("p", {"data-testid": "location-date"})
        if not link_tag or not title_tag or not price_tag:
            continue
        link = link_tag["href"]
        if link.startswith("/"):
            link = "https://www.olx.pl" + link
        title = title_tag.get_text(strip=True)
        price_text = price_tag.get_text(strip=True)
        location = location_tag.get_text(strip=True) if location_tag else "brak lokalizacji"
        price_match = re.search(r"(\d[\d\s]*)", price_text)
        if price_match:
            price_value = int(price_match.group(1).replace(" ", ""))
            if price_value < 1000:
                continue
        offers.append((title, f"{price_value} zł", location, link))
    return offers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot LEGO KG aktywowany!")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sprawdzam oferty LEGO KG...")
    offers = await fetch_offers()
    if not offers:
        await update.message.reply_text("⚠️ Brak ofert lub OLX chwilowo niedostępny.")
    else:
        for title, price, location, link in offers[:5]:
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("check", check))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    asyncio.run(dispatcher.process_update(update))
    return "ok"

@app.route("/")
def home():
    return "✅ LEGO KG Bot działa!"

if __name__ == "__main__":
    bot.set_webhook(f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
