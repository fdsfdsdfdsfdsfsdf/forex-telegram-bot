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

RSS_SOURCES = [
    "https://www.forexlive.com/feed/news",
    "https://www.dailyfx.com/feeds/forex-market-news",
    "https://news.google.com/rss/search?q=EURUSD+OR+GBPUSD+OR+USDJPY+OR+Fed+OR+Forex+market&hl=en-US&gl=US&ceid=US:en"
]

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

# تابع استخراج متن کامل خبر (حتی اگر در RSS ناقص باشد)
def get_full_article_text(entry):
    raw_content = ""
    if hasattr(entry, 'content') and len(entry.content) > 0:
        raw_content = entry.content[0].value
    elif hasattr(entry, 'summary'):
        raw_content = entry.summary
    elif hasattr(entry, 'description'):
        raw_content = entry.description

    text = clean_html(raw_content)

    # اگر متن به ... ختم شده یا بسیار کوتاه باشد، صفحه اصلی خبر را باز کن و متن کامل را بخوان
    if (text.endswith("...") or text.endswith("…") or len(text) < 200) and hasattr(entry, 'link'):
        try:
            res = requests.get(entry.link, headers=HEADERS, timeout=6, allow_redirects=True)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                paragraphs = soup.find_all("p")
                p_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 35]
                if p_texts:
                    # ترکیب پاراگراف‌ها برای ساخت خبر کاملاً کامل
                    scraped_text = " ".join(p_texts[:5])
                    if len(scraped_text) > len(text):
                        text = scraped_text
        except Exception as e:
            print(f"امکان دریافت صفحه کامل نبود، استفاده از متن موجود: {e}")

    # پاک کردن سه نقطه احتمالی از انتهای متن
    text = text.rstrip(".… ")
    return text

translator = GoogleTranslator(source='auto', target='fa')

entries_to_process = []

# دریافت ۱۰ خبر واقعی
for url in RSS_SOURCES:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            for entry in feed.entries:
                title_lower = entry.title.lower()
                
                if any(kw in title_lower for kw in IGNORE_KEYWORDS):
                    continue
                
                if not any(e.title == entry.title for e in entries_to_process):
                    entries_to_process.append(entry)
                
                if len(entries_to_process) >= 10:
                    break
    except Exception as e:
        print(f"خطا در دریافت از {url}: {e}")

    if len(entries_to_process) >= 10:
        break

print(f"تعداد {len(entries_to_process)} خبر پیدا شد.")

# ترجمه و ارسال اخبار کامل
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    full_text_en = get_full_article_text(entry)

    # کنترل سقف استاندارد تلگرام (تا ۲۵۰۰ کاراکتر)
    if len(full_text_en) > 2500:
        full_text_en = full_text_en[:2500]

    # ترجمه عنوان و متن کامل خبر
    try:
        title_fa = translator.translate(title_en)
        summary_fa = translator.translate(full_text_en) if full_text_en else title_fa
    except Exception as e:
        print(f"خطا در ترجمه خبر {idx}: {e}")
        title_fa = title_en
        summary_fa = full_text_en

    # ساخت قالب پیام نهایی و کامل
    message = f"📊 **خبر فارکس ({idx}/10)**\n\n📌 **عنوان:**\n{title_fa}\n\n📝 **متن کامل خبر:**\n{summary_fa}"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    res = requests.post(telegram_url, data=payload)
    
    if res.status_code != 200:
        payload.pop("parse_mode", None)
        requests.post(telegram_url, data=payload)

    print(f"خبر شماره {idx} با موفقیت ارسال شد.")
    time.sleep(2) # وقفه بین ارسال‌ها
