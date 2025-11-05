import os
import re
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Konfiguracja ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set.")
    exit(1)

SEARCH_URL = "https://www.olx.pl/oferty/q-lego-kg/?search%5Bfilter_float_price%3Afrom%5D=1000"
SEEN_FILE = "seen_links.json"
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# --- Wczytanie zapisanych linków ---
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_links = set(json.load(f))
else:
    seen_links = set()

def save_seen_links():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_links), f)

# --- Funkcja pobierająca oferty z OLX ---
def fetch_offers():
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

# --- Funkcja wysyłająca nowe oferty ---
async def send_new_offers(context: ContextTypes.DEFAULT_TYPE):
    offers = fetch_offers()
    new_count = 0
    for title, price, location, link in offers:
        if link not in seen_links:
            seen_links.add(link)
            save_seen_links()  # zapis po każdej nowej ofercie
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown", disable_web_page_preview=True)
            new_count += 1
    if new_count > 0:
        print(f"📬 Wysłano {new_count} nowych ofert.")

# --- Komendy ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot LEGO KG (od 1000 zł, cała Polska) aktywowany!")
    context.job_queue.run_repeating(send_new_offers, interval=3600, first=5, chat_id=update.effective_chat.id)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sprawdzam oferty LEGO KG (od 1000 zł)...")
    offers = fetch_offers()
    new_count = 0
    for title, price, location, link in offers[:10]:
        if link not in seen_links:
            new_count += 1
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    if new_count == 0:
        await update.message.reply_text("⚠️ Brak nowych ofert.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("check", check))

# --- Flask webhook ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def home():
    return "✅ LEGO KG Bot działa!"

# --- Start aplikacji ---
if __name__ == "__main__":
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    application.bot.set_webhook(webhook_url)
    print(f"Webhook ustawiony: {webhook_url}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
