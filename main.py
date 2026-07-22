import os
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("کلیدهای تلگرام ست نشده‌اند!")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# منابع اصلی اخبار زنده بازار فارکس
RSS_SOURCES = [
    "https://www.forexlive.com/feed/news",
    "https://www.dailyfx.com/feeds/forex-market-news",
    "https://news.google.com/rss/search?q=EURUSD+OR+GBPUSD+OR+USDJPY+OR+Fed+OR+Forex+market&hl=en-US&gl=US&ceid=US:en"
]

# کلمات کلیدی برای حذف اخبار آموزشی و تبلیغاتی بروکرها
IGNORE_KEYWORDS = [
    "how to", "best time", "what is", "guide", "tutorial", "broker", 
    "tmgm", "top 10", "learn to trade", "strategy", "آموزش", "بهترین زمان"
]

# تابع پاک‌سازی کدهای HTML
def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

translator = GoogleTranslator(source='auto', target='fa')

entries_to_process = []

# جمع‌آوری ۱۰ خبر واقعی و بروز بازار
for url in RSS_SOURCES:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            for entry in feed.entries:
                title_lower = entry.title.lower()
                
                # فیلتر کردن کارهای آموزشی و تبلیغاتی
                if any(kw in title_lower for kw in IGNORE_KEYWORDS):
                    continue
                
                # جلوگیری از ارسال خبر تکراری
                if not any(e.title == entry.title for e in entries_to_process):
                    entries_to_process.append(entry)
                
                if len(entries_to_process) >= 10:
                    break
    except Exception as e:
        print(f"خطا در دریافت از {url}: {e}")

    if len(entries_to_process) >= 10:
        break

print(f"تعداد {len(entries_to_process)} خبر واقعی فارکس پیدا شد.")

image_url = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"

# ارسال ۱۰ خبر به صورت جداگانه
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    summary_raw = getattr(entry, 'summary', title_en)
    summary_clean = clean_html(summary_raw)

    if len(summary_clean) > 350:
        summary_clean = summary_clean[:350] + "..."

    # ترجمه به فارسی
    try:
        title_fa = translator.translate(title_en)
        summary_fa = translator.translate(summary_clean) if summary_clean and summary_clean != title_en else title_fa
    except Exception as e:
        title_fa = title_en
        summary_fa = summary_clean

    # فرمت کاملاً تمیز (بدون لینک و بدون منبع)
    message = f"📊 **خبر فارکس ({idx}/10)**\n\n📌 **عنوان خبر:**\n{title_fa}\n\n📝 **خلاصه خبر:**\n{summary_fa}"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": message,
        "parse_mode": "Markdown"
    }

    res = requests.post(telegram_url, data=payload)
    
    # اگر تلگرام با مارک‌داون مشکل داشت، بدون مارک‌داون بفرست
    if res.status_code != 200:
        payload.pop("parse_mode", None)
        requests.post(telegram_url, data=payload)

    print(f"خبر شماره {idx} با موفقیت ارسال شد.")
    time.sleep(2) # وقفه ۲ ثانیه‌ای برای اسپم نشدن تلگرام
