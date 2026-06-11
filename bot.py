import os
import feedparser
import requests
from telegram import Bot
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss",
    "https://cryptoslate.com/feed/",
]

sent_links = set()

def market_status():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    text = "📊 وضعیت بازار کریپتو\n\n"

    for symbol in symbols:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        data = requests.get(url, timeout=10).json()
        price = float(data["lastPrice"])
        change = float(data["priceChangePercent"])
        volume = float(data["quoteVolume"])

        text += f"🪙 {symbol}\n"
        text += f"قیمت: {price:,.2f}\n"
        text += f"تغییر ۲۴ ساعته: {change:.2f}%\n"
        text += f"حجم: {volume:,.0f}\n\n"

    return text

def importance(title):
    t = title.lower()
    alerts = ["sec", "etf", "hack", "exploit", "binance", "listing", "delisting", "fed", "lawsuit"]
    for word in alerts:
        if word in t:
            return "🚨 هشدار مهم"
    return "📰 خبر معمولی"

def send_news():
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:3]:
            title = entry.get("title", "")
            link = entry.get("link", "")

            if not link or link in sent_links:
                continue

            sent_links.add(link)

            msg = f"""
{importance(title)}

🗞 خبر کریپتو:
{title}

خلاصه فارسی:
این خبر می‌تواند روی احساسات بازار و نوسانات کوتاه‌مدت اثر بگذارد. برای اسکالپ، بهتر است واکنش BTC و حجم معاملات بررسی شود.

🔗 لینک:
{link}
"""
            bot.send_message(chat_id=CHAT_ID, text=msg)

def send_market():
    bot.send_message(chat_id=CHAT_ID, text=market_status())

if __name__ == "__main__":
    bot.send_message(chat_id=CHAT_ID, text="✅ ربات اخبار و هشدار کریپتو فعال شد.")
    scheduler = BlockingScheduler()
    scheduler.add_job(send_news, "interval", minutes=10)
    scheduler.add_job(send_market, "interval", hours=1)
    scheduler.start()
