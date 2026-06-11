import os
import re
import threading
import requests
import feedparser
from flask import Flask
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)
sent_links = set()

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss",
    "https://cryptoslate.com/feed/",
]

def clean_html(text):
    text = re.sub("<.*?>", "", text or "")
    return text.strip()

def translate_to_fa(text):
    try:
        if not text:
            return "خلاصه‌ای موجود نیست."
        return GoogleTranslator(source="auto", target="fa").translate(text[:1200])
    except Exception:
        return text[:700]

def telegram_send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=15)

@app.route("/")
def home():
    return "Crypto bot is running ✅"

def importance(title):
    t = title.lower()
    words = ["sec", "etf", "hack", "exploit", "binance", "listing", "delisting", "fed", "lawsuit"]
    return "🚨 هشدار مهم" if any(w in t for w in words) else "📰 خبر کریپتو"

def send_news():
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:3]:
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", ""))
            link = entry.get("link", "")

            if not link or link in sent_links:
                continue

            sent_links.add(link)

            fa_title = translate_to_fa(title)
            fa_summary = translate_to_fa(summary)

            msg = f"""
{importance(title)}

🗞 عنوان فارسی:
{fa_title}

📌 عنوان اصلی:
{title}

🇮🇷 خلاصه فارسی:
{fa_summary}

📊 تحلیل کوتاه:
این خبر می‌تواند روی احساسات بازار و نوسانات کوتاه‌مدت اثر بگذارد. برای اسکالپ، واکنش BTC، حجم معاملات و شکست سطوح مهم را بررسی کن.

🔗 لینک خبر:
{link}
"""
            telegram_send(msg)

def send_market():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    text = "📊 وضعیت بازار کریپتو\n\n"

    for symbol in symbols:
        try:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            data = requests.get(url, timeout=10).json()

            if "lastPrice" not in data:
                continue

            price = float(data["lastPrice"])
            change = float(data["priceChangePercent"])

            text += f"🟡 {symbol}\n"
            text += f"قیمت: {price:.2f}\n"
            text += f"تغییر ۲۴ ساعته: {change:.2f}%\n\n"

        except Exception:
            continue

    telegram_send(text)

def run_scheduler():
    telegram_send("✅ ربات اخبار و هشدار کریپتو فعال شد.")
    send_news()
    send_market()

    scheduler = BlockingScheduler()
    scheduler.add_job(send_news, "interval", minutes=10)
    scheduler.add_job(send_market, "interval", hours=1)
    scheduler.start()

if name == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
