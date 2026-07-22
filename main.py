import os
import requests
import feedparser
from deep_translator import GoogleTranslator

# دریافت کلیدها از محیط گیت‌هاب
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# خواندن آخرین خبر از منبع RSS فارکس
RSS_URL = "https://www.forexlive.com/rss"
feed = feedparser.parse(RSS_URL)

if feed.entries:
    latest = feed.entries[0]
    title_en = latest.title
    link = latest.link
    summary_en = latest.get("summary", "")

    # محدود کردن طول متن انگلیسی قبل از ترجمه
    if len(summary_en) > 400:
        summary_en = summary_en[:400] + "..."

    # ترجمه خودکار متن خبر به فارسی
    translator = GoogleTranslator(source='auto', target='fa')
    try:
        title_fa = translator.translate(title_en)
        summary_fa = translator.translate(summary_en) if summary_en else ""
    except Exception as e:
        print("خطا در ترجمه، استفاده از متن اصلی انگلیسی:", e)
        title_fa = title_en
        summary_fa = summary_en

    # ساخت متن فارسی برای تلگرام
    caption = f"📊 **بروزرسانی اخبار بازار فارکس**\n\n" \
              f"📌 **عنوان خبر:**\n{title_fa}\n\n" \
              f"📝 **خلاصه:**\n{summary_fa}\n\n" \
              f"🔗 [مشاهده متن کامل خبر در منبع اصلی]({link})\n\n" \
              f"⏰ **بروزرسانی خودکار هر ۶ ساعت**"

    # تصویر باکیفیت برای خبر
    image_url = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"

    # ارسال عکس و متن به کانال تلگرام
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        print("خبر فارسی با موفقیت به کانال ارسال شد!")
    else:
        print(f"خطا در ارسال به تلگرام: {response.text}")
else:
    print("هیچ خبری در RSS پیدا نشد.")
