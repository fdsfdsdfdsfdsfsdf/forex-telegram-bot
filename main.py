import os
import requests
import feedparser
from deep_translator import GoogleTranslator

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# هدر مرورگر برای دور زدن بلاکی سرورها
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# چند منبع خبری معتبر فارکس (اگر اولی کار نکرد، میره سراغ بعدی)
RSS_SOURCES = [
    "https://www.forexlive.com/feed/news",
    "https://www.dailyfx.com/feeds/forex-market-news",
    "https://news.google.com/rss/search?q=forex+market&hl=en-US&gl=US&ceid=US:en"
]

latest_entry = None

# پیدا کردن آخرین خبر از بین منابع
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

if latest_entry:
    title_en = latest_entry.title
    link = latest_entry.link
    summary_en = getattr(latest_entry, 'summary', title_en)

    # پاکسازی و کوتاه کردن متن انگلیسی
    if len(summary_en) > 400:
        summary_en = summary_en[:400] + "..."

    # ترجمه به فارسی
    translator = GoogleTranslator(source='auto', target='fa')
    try:
        title_fa = translator.translate(title_en)
        summary_fa = translator.translate(summary_en) if summary_en else ""
    except Exception as e:
        print("خطا در ترجمه، استفاده از متن اصلی:", e)
        title_fa = title_en
        summary_fa = summary_en

    # ساخت متن فارسی
    caption = f"📊 **بروزرسانی اخبار بازار فارکس**\n\n" \
              f"📌 **عنوان خبر:**\n{title_fa}\n\n" \
              f"📝 **خلاصه:**\n{summary_fa}\n\n" \
              f"🔗 [مشاهده متن کامل خبر در منبع اصلی]({link})\n\n" \
              f"⏰ **بروزرسانی خودکار هر ۶ ساعت**"

    # عکس باکیفیت
    image_url = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"

    # ارسال به تلگرام
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }

    res = requests.post(telegram_url, data=payload)
    if res.status_code == 200:
        print("خبر فارسی با موفقیت به کانال ارسال شد!")
    else:
        print(f"خطا در ارسال به تلگرام: {res.text}")
else:
    print("هیچ خبری در هیچ‌کدام از منابع پیدا نشد.")
