import os
import sys
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import re

# Pobranie tokena z Render (zmienna środowiskowa)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN environment variable is not set. Exiting.")
    sys.exit(1)

# Szukamy „lego kg” z całej Polski, bez lokalnych filtrów
SEARCH_URL = "https://www.olx.pl/oferty/q-lego-kg/?search%5Bfilter_float_price%3Afrom%5D=1000"
seen_links = set()

async def fetch_offers():
    """Pobiera oferty z OLX (cena >= 1000 zł)"""
    r = requests.get(SEARCH_URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    offers = []

    for offer in soup.select("div[data-cy='l-card']"):
        link_tag = offer.find("a", href=True)
        title_tag = offer.find("h6")
        price_tag = offer.find("p", {"data-testid": "ad-price"})
        location_tag = offer.find("p", {"data-testid": "location-date"})

        if not link_tag or not title_tag or not price_tag:
            continue

        # Link
        link = link_tag["href"]
        if link.startswith("/"):
            link = "https://www.olx.pl" + link

        # Tytuł, cena, lokalizacja
        title = title_tag.get_text(strip=True)
        price_text = price_tag.get_text(strip=True)
        location = location_tag.get_text(strip=True) if location_tag else "brak lokalizacji"

        # Odczytaj cenę liczbę
        price_match = re.search(r"(\d[\d\s]*)", price_text)
        if price_match:
            price_value = int(price_match.group(1).replace(" ", ""))
            if price_value < 1000:
                continue  # pomiń tańsze oferty
        else:
            continue

        offers.append((title, f"{price_value} zł", location, link))

    return offers

async def send_new_offers(context: ContextTypes.DEFAULT_TYPE):
    """Wysyła nowe oferty na Telegram"""
    bot = context.bot
    offers = await fetch_offers()

    for title, price, location, link in offers:
        if link not in seen_links:
            seen_links.add(link)
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown", disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aktywuje bota"""
    await update.message.reply_text("✅ Bot LEGO KG (od 1000 zł, cała Polska) aktywowany! 🧱")
    context.job_queue.run_repeating(send_new_offers, interval=3600, first=5, chat_id=update.effective_chat.id)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ręczne sprawdzenie ofert"""
    await update.message.reply_text("🔍 Sprawdzam oferty LEGO KG (od 1000 zł)...")
    offers = await fetch_offers()
    if not offers:
        await update.message.reply_text("❌ Nie znaleziono żadnych ofert spełniających kryteria.")
    else:
        for title, price, location, link in offers[:5]:  # wysyła max 5 ofert
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.run_polling()

if __name__ == "__main__":
    main()
