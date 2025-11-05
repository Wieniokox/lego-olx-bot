import os
import sys
import threading
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set.")
    sys.exit(1)

SEARCH_URL = "https://www.olx.pl/oferty/q-lego-kg/?search%5Bfilter_float_price%3Afrom%5D=1000"
seen_links = set()

# --- Flask serwer (Render wymaga otwartego portu) ---
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ LEGO KG Bot działa na Render!"

# --- Funkcja pobierająca oferty z OLX ---
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
    print(f"✅ Znaleziono {len(offers)} ofert.")
    return offers

async def send_new_offers(context: ContextTypes.DEFAULT_TYPE):
    offers = await fetch_offers()
    bot = context.bot
    for title, price, location, link in offers:
        if link not in seen_links:
            seen_links.add(link)
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown", disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot LEGO KG (od 1000 zł, cała Polska) aktywowany!")
    context.job_queue.run_repeating(send_new_offers, interval=3600, first=5, chat_id=update.effective_chat.id)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sprawdzam oferty LEGO KG (od 1000 zł)...")
    offers = await fetch_offers()
    if not offers:
        await update.message.reply_text("⚠️ Brak ofert lub OLX chwilowo niedostępny.")
    else:
        for title, price, location, link in offers[:5]:
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))).start()
    run_bot()
