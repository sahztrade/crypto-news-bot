import os, json, re, time, html
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
CHECK_NEWS_EVERY_SECONDS = int(os.getenv("CHECK_NEWS_EVERY_SECONDS", "600"))
CHECK_MARKET_EVERY_SECONDS = int(os.getenv("CHECK_MARKET_EVERY_SECONDS", "900"))
NEWS_IMPORTANCE_MIN = int(os.getenv("NEWS_IMPORTANCE_MIN", "2"))
MARKET_ALERT_PERCENT = float(os.getenv("MARKET_ALERT_PERCENT", "3.0"))
VOLUME_ALERT_PERCENT = float(os.getenv("VOLUME_ALERT_PERCENT", "80"))
WATCH_SYMBOLS = [s.strip().upper() for s in os.getenv("WATCH_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT").split(",") if s.strip()]
SEND_ANALYST_NEWS = os.getenv("SEND_ANALYST_NEWS", "true").lower() == "true"
SEND_EXCHANGE_ALERTS = os.getenv("SEND_EXCHANGE_ALERTS", "true").lower() == "true"

BASE = Path(__file__).parent
SEEN_FILE = BASE / "seen.json"
STATE_FILE = BASE / "market_state.json"
FEEDS_FILE = BASE / "feeds.json"

HIGH_IMPACT_WORDS = {
    "etf": 4, "sec": 4, "fed": 3, "interest rate": 3, "cpi": 3, "inflation": 3,
    "hack": 5, "exploit": 5, "breach": 5, "lawsuit": 4, "approved": 4, "approval": 4,
    "ban": 4, "regulation": 3, "whale": 2, "blackrock": 4, "microstrategy": 3,
    "binance": 3, "coinbase": 3, "kraken": 2, "okx": 2, "bybit": 2,
    "listing": 3, "delisting": 4, "halt": 4, "outage": 4, "liquidation": 3,
    "bitcoin": 2, "ethereum": 2, "solana": 2, "xrp": 2
}
BULLISH = ["approved", "approval", "inflow", "record high", "surge", "rally", "breakout", "adoption", "buys", "accumulate", "partnership", "listing"]
BEARISH = ["hack", "exploit", "outflow", "lawsuit", "ban", "crash", "plunge", "sell-off", "liquidation", "delisting", "probe", "investigation"]
COIN_NAMES = {
    "BTC": ["bitcoin", "btc"], "ETH": ["ethereum", "ether", "eth"], "SOL": ["solana", "sol"],
    "XRP": ["xrp", "ripple"], "BNB": ["bnb", "binance coin"], "DOGE": ["dogecoin", "doge"],
    "TON": ["toncoin", "ton"], "ADA": ["cardano", "ada"], "AVAX": ["avalanche", "avax"], "LINK": ["chainlink", "link"]
}

def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def clean_text(txt):
    txt = BeautifulSoup(txt or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()

def translate_fa(text):
    text = clean_text(text)[:1200]
    if not text:
        return ""
    if GoogleTranslator:
        try:
            return GoogleTranslator(source="auto", target="fa").translate(text)
        except Exception:
            pass
    return text

def score_news(title, summary):
    text = f"{title} {summary}".lower()
    score = sum(v for k, v in HIGH_IMPACT_WORDS.items() if k in text)
    coins = [coin for coin, words in COIN_NAMES.items() if any(w in text for w in words)]
    bullish = sum(1 for w in BULLISH if w in text)
    bearish = sum(1 for w in BEARISH if w in text)
    if bearish > bullish:
        sentiment = "🔴 فشار منفی / ریسک نزولی"
    elif bullish > bearish:
        sentiment = "🟢 اثر مثبت / احتمال رشد"
    else:
        sentiment = "🟡 خنثی یا نامشخص"
    if score >= 8:
        level = "🚨 بسیار مهم"
    elif score >= 5:
        level = "🔥 مهم"
    elif score >= 2:
        level = "⚠️ قابل توجه"
    else:
        level = "📰 عادی"
    return score, level, sentiment, coins

def load_feeds():
    data = load_json(FEEDS_FILE, {"news": [], "analysts": []})
    feeds = list(data.get("news", []))
    if SEND_ANALYST_NEWS:
        feeds += data.get("analysts", [])
    return list(dict.fromkeys(feeds))

async def check_news(context: ContextTypes.DEFAULT_TYPE):
    seen = set(load_json(SEEN_FILE, []))
    sent = 0
    for url in load_feeds():
        parsed = feedparser.parse(url)
        for e in parsed.entries[:8]:
            link = e.get("link", "")
            uid = e.get("id", link) or link
            if not link or uid in seen:
                continue
            title = clean_text(e.get("title", ""))
            summary = clean_text(e.get("summary", ""))
            score, level, sentiment, coins = score_news(title, summary)
            if score < NEWS_IMPORTANCE_MIN:
                seen.add(uid)
                continue
            fa_title = translate_fa(title)
            fa_summary = translate_fa(summary[:500]) if summary else ""
            coin_line = ", ".join(coins) if coins else "بازار کلی"
            msg = (
                f"{level}\n\n"
                f"🪙 حوزه: {coin_line}\n"
                f"📊 برداشت بازار: {sentiment}\n"
                f"⭐ امتیاز اهمیت: {score}/10+\n\n"
                f"🇮🇷 عنوان فارسی:\n{fa_title}\n\n"
                f"📝 خلاصه:\n{fa_summary or 'خلاصه‌ای در RSS نبود؛ لینک خبر را ببین.'}\n\n"
                f"🔗 منبع:\n{link}"
            )
            await context.bot.send_message(chat_id=CHAT_ID, text=msg[:3900], disable_web_page_preview=True)
            seen.add(uid)
            sent += 1
            if sent >= 5:
                break
        if sent >= 5:
            break
    save_json(SEEN_FILE, list(seen)[-1000:])

async def check_market(context: ContextTypes.DEFAULT_TYPE):
    state = load_json(STATE_FILE, {})
    alerts = []
    try:
        for symbol in WATCH_SYMBOLS:
            r = requests.get("https://api.binance.com/api/v3/ticker/24hr", params={"symbol": symbol}, timeout=15)
            if r.status_code != 200:
                continue
            d = r.json()
            pct = float(d.get("priceChangePercent", 0))
            last = float(d.get("lastPrice", 0))
            volume_quote = float(d.get("quoteVolume", 0))
            old = state.get(symbol, {})
            old_vol = float(old.get("quoteVolume", 0) or 0)
            vol_jump = ((volume_quote - old_vol) / old_vol * 100) if old_vol > 0 else 0
            if abs(pct) >= MARKET_ALERT_PERCENT:
                direction = "🟢 رشد" if pct > 0 else "🔴 ریزش"
                alerts.append(f"{direction} {symbol}: {pct:.2f}% در ۲۴ ساعت | قیمت: {last:g}")
            if old_vol > 0 and vol_jump >= VOLUME_ALERT_PERCENT:
                alerts.append(f"⚡ افزایش حجم {symbol}: حدود {vol_jump:.0f}% نسبت به بررسی قبلی")
            state[symbol] = {"lastPrice": last, "quoteVolume": volume_quote, "ts": int(time.time())}
        save_json(STATE_FILE, state)
    except Exception as ex:
        alerts.append(f"⚠️ خطا در بررسی بازار: {ex}")
    if alerts:
        msg = "📡 هشدار وضعیت بازار / Binance\n\n" + "\n".join(alerts[:15]) + "\n\n⚠️ این پیام توصیه مالی نیست؛ فقط هشدار نوسان و حجم است."
        await context.bot.send_message(chat_id=CHAT_ID, text=msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ربات حرفه‌ای اخبار و هشدار کریپتو فعال است ✅\nدستور /latest برای تست خبر و /market برای وضعیت بازار.")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("در حال بررسی خبرهای مهم...")
    await check_news(context)

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("در حال بررسی بازار...")
    await check_market(context)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✅ وضعیت تنظیمات:\nCHAT_ID={CHAT_ID}\nSymbols={', '.join(WATCH_SYMBOLS)}\nNews each {CHECK_NEWS_EVERY_SECONDS}s\nMarket each {CHECK_MARKET_EVERY_SECONDS}s"
    )

def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN و CHAT_ID را در فایل .env یا Environment Variables تنظیم کن.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CommandHandler("status", status))
    app.job_queue.run_repeating(check_news, interval=CHECK_NEWS_EVERY_SECONDS, first=10)
    app.job_queue.run_repeating(check_market, interval=CHECK_MARKET_EVERY_SECONDS, first=20)
    print("Crypto Alert Pro Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
