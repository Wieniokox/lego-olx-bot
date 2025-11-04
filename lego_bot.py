import os
import sys
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask

# Pobieramy token z zmiennej środowiskowej BOT_TOKEN
TOKEN = os.getenv("8204866609:AAEH3iZqii8n6Wlc3KmmuihH2gCKcvCXpn0")
if not TOKEN:
    print("ERROR: BOT_TOKEN environment variable is not set. Exiting.")
    sys.exit(1)

SEARCH_URL = "https://www.olx.pl/oferty/q-lego-kg/"
seen_links = set()
app = Flask(__name__)  # Flask needed for webhook endpoint (Render will call it)


async def fetch_offers():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(SEARCH_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    offers = []
    for offer in soup.select("div[data-cy='l-card']"):
        link_tag = offer.find("a", href=True)
        title_tag = offer.find("h6")
        price_tag = offer.find("p", {"data-testid": "ad-price"})
        location_tag = offer.find("p", {"data-testid": "location-date"})
        if not link_tag or not title_tag:
            continue
        link = link_tag["href"]
        if link.startswith("/"):
            link = "https://www.olx.pl" + link
        title = title_tag.get_text(strip=True)
        price = price_tag.get_text(strip=True) if price_tag else "brak ceny"
        location = location_tag.get_text(strip=True) if location_tag else "brak lokalizacji"
        offers.append((title, price, location, link))
    return offers


async def send_new_offers(context: ContextTypes.DEFAULT_TYPE):
    offers = await fetch_offers()
    for title, price, location, link in offers:
        if link not in seen_links:
            seen_links.add(link)
            msg = f"🧱 *{title}*\n💰 {price}\n📍 {location}\n🔗 [Zobacz ofertę]({link})"
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=msg,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("✅ Bot LEGO KG aktywowany! Sprawdzam oferty co godzinę.")
    # Upewnij się, że job_queue istnieje i zaplanuj powtarzanie
    job_queue = context.application.job_queue
    job_queue.run_repeating(send_new_offers, interval=3600, first=5, chat_id=chat_id)


def main():
    application = Application.builder().token(TOKEN).concurrent_updates(True).build()
    # Force init job_queue (powinno być dostępne po build)
    _ = application.job_queue

    application.add_handler(CommandHandler("start", start))

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if not render_url:
        print("WARNING: RENDER_EXTERNAL_URL not set. Using fallback URL. Webhook may fail.")
        render_url = f"https://{os.getenv('RENDER_SERVICE_ID', 'your-service')}.onrender.com"

    webhook_url = f"{render_url}/webhook/{TOKEN}"
    print(f"🔗 Setting webhook to: {webhook_url}")

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path=f"/webhook/{TOKEN}",
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
