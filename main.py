import os
import requests
import feedparser
from deep_translator import GoogleTranslator

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("کلیدهای TELEGRAM_TOKEN یا TELEGRAM_CHAT_ID در گیت‌هاب تنظیم نشده‌اند!")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# لیست منابع خبری معتبر (اولین منبع Google News است که ۱۰۰٪ بدون قطعی عمل می‌کند)
RSS_SOURCES = [
    "https://news.google.com/rss/search?q=forex+market&hl=en-US&gl=US&ceid=US:en",
    "https://www.forexlive.com/feed/news",
    "https://www.dailyfx.com/feeds/forex-market-news"
]

latest_entry = None

# دریافت آخرین خبر
for url in RSS_SOURCES:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            if feed.entries:
                latest_entry = feed.entries[0]
                print(f"خبر با موفقیت از منبع دریافت شد: {url}")
                break
    except Exception as e:
        print(f"خطا در دریافت از {url}: {e}")

if not latest_entry:
    raise Exception("هیچ خبری پیدا نشد!")

title_en = latest_entry.title
link = latest_entry.link
summary_en = getattr(latest_entry, 'summary', title_en)

# کوتاه کردن خلاصه خبر
if len(summary_en) > 300:
    summary_en = summary_en[:300] + "..."

# ترجمه به فارسی
translator = GoogleTranslator(source='auto', target='fa')
try:
    title_fa = translator.translate(title_en)
    summary_fa = translator.translate(summary_en) if summary_en else ""
except Exception as e:
    print("خطا در ترجمه، استفاده از متن اصلی:", e)
    title_fa = title_en
    summary_fa = summary_en

# ساخت متن فارسی بدون فرمت‌های حساس (جهت جلوگیری از خطای تلگرام)
caption = f"📊 بروزرسانی اخبار بازار فارکس\n\n📌 عنوان خبر:\n{title_fa}\n\n📝 خلاصه:\n{summary_fa}\n\n🔗 لینک منبع اصلی:\n{link}\n\n⏰ بروزرسانی خودکار هر ۶ ساعت"

image_url = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"

# ارسال عکس و متن به تلگرام
telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "photo": image_url,
    "caption": caption
}

res = requests.post(telegram_url, data=payload)

# اگر ارسال عکس خطا داد، متن بدون عکس ارسال شود
if res.status_code != 200:
    print(f"خطا در ارسال عکس ({res.text})، در حال ارسال متنی...")
    text_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text_payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption
    }
    res = requests.post(text_url, data=text_payload)

# اگر تلگرام باز هم خطا داد، اجرای گیت‌هاب قرمز می‌شود تا علت دقیق مشخص گردد
if res.status_code != 200:
    raise Exception(f"خطای تلگرام: {res.text}")

print("پیام با موفقیت در کانال منتشر شد!")
