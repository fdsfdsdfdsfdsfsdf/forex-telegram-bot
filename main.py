import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("کلیدهای TELEGRAM_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده‌اند!")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ENGLISH_RSS_SOURCES = [
    "https://www.forexlive.com/feed/news",
    "https://www.dailyfx.com/feeds/forex-market-news",
    "https://news.google.com/rss/search?q=EURUSD+OR+GBPUSD+OR+USDJPY+OR+Fed+OR+Forex+market&hl=en-US&gl=US&ceid=US:en"
]

IGNORE_KEYWORDS = [
    "how to", "best time", "what is", "guide", "tutorial", "broker", 
    "tmgm", "top 10", "learn to trade", "strategy", "promo"
]

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

# پاک‌سازی اسم منابع، لینک‌ها و سایت‌ها
def clean_sources(text):
    if not text:
        return ""
    patterns = [
        r'\(?\s*(منبع|خبرگزاری|سایت|Reuters|Bloomberg|ForexLive|DailyFX|Google News|رویترز|بلومبرگ|فارکس لایو)\s*:[^\)]*\)?',
        r'-\s*(ForexLive|DailyFX|Bloomberg|Reuters|Google News|رویترز|بلومبرگ|فارکس لایو).*$',
        r'منبع:\s*.*$',
        r'http[s]?://\S+'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

# استخراج «لید خبر» (۲ یا ۳ جمله اول مقاله که اصل خلاصه خبر است)
def extract_lead_summary(entry):
    raw_content = ""
    if hasattr(entry, 'summary'):
        raw_content = entry.summary
    elif hasattr(entry, 'description'):
        raw_content = entry.description

    text = clean_html(raw_content)

    # اگر فید کوتاهی داد، پاراگراف اول صفحه اصلی خبر را بردار
    if len(text) < 100 and hasattr(entry, 'link'):
        try:
            res = requests.get(entry.link, headers=HEADERS, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                paragraphs = soup.find_all("p")
                p_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
                if p_texts:
                    text = p_texts[0]
        except Exception as e:
            pass

    # جدا کردن ۲ تا ۳ جمله اول (اصل خلاصه خبر)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    lead_sentences = sentences[:3]
    summary_en = " ".join(lead_sentences).strip()
    
    return summary_en

translator = GoogleTranslator(source='auto', target='fa')

entries_to_process = []

# جمع‌آوری ۱۰ خبر برتر
for url in ENGLISH_RSS_SOURCES:
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

print(f"تعداد {len(entries_to_process)} خبر برتر پیدا شد.")

# ترجمه لید خبرها به فارسی و ارسال
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    lead_summary_en = extract_lead_summary(entry)

    try:
        title_fa = translator.translate(title_en)
        summary_fa = translator.translate(lead_summary_en)
    except Exception as e:
        print(f"خطا در ترجمه خبر {idx}: {e}")
        continue

    title_fa = clean_sources(title_fa)
    summary_fa = clean_sources(summary_fa)

    if not summary_fa.endswith((".", "!", "؟")):
        summary_fa += "."

    message = f"📊 **خبر فارکس ({idx}/10)**\n\n📌 **عنوان:**\n{title_fa}\n\n📝 **خلاصه خبر:**\n{summary_fa}"

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
    time.sleep(2)
