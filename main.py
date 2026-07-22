import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not GROQ_API_KEY:
    raise ValueError("کلیدهای TELEGRAM_TOKEN، TELEGRAM_CHAT_ID یا GROQ_API_KEY در گیت‌هاب تنظیم نشده‌اند!")

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

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "mixtral-8x7b-32768"
]

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

# فیلتر اختصاصی جهت حذف ۱۰۰٪ نام منابع، خبرگزاری‌ها و لینک‌ها
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

# خلاصه‌سازی فوق‌العاده کوتاه و روان با Groq
def summarize_and_translate_with_groq(title, content):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    short_content = content[:350]

    prompt = f"""
خبر فارکس زیر را بخوان و آن را به یک گزارش بسیار کوتاه، فشرده و جذاب به زبان فارسی تبدیل کن.

عنوان: {title}
متن: {short_content}

دستورالعمل‌های حیاتی:
۱. متن خلاصه باید فوق‌العاده کوتاه باشد (حداکثر ۲ الی ۳ جمله کوتاه). کل متن نباید از ۴۰ کلمه بیشتر شود!
۲. هیچ‌گونه اسم منبع، خبرگزاری، وب‌سایت، لینک یا نام برند در خروجی نباشد.
۳. ادبیات خبر کاملاً روان، جذاب و فارسی باشد.

فرمت خروجی (دقیقاً به این شکل):
📌 **عنوان:**
[عنوان کوتاه فارسی]

📝 **خلاصه:**
[۲ جمله بسیار کوتاه و مفید]
"""

    for model_name in GROQ_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 200 # سقف سخت‌گیرانه برای کوتاه ماندن خروجی
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                result = res.json()
                output = result["choices"][0]["message"]["content"].strip()
                return clean_sources(output)
            else:
                print(f"مدل {model_name} پاسخ نداد (کد {res.status_code})")
        except Exception as e:
            print(f"خطا در مدل {model_name}: {e}")

    # سیستم پشتیبان در صورت خطای Groq
    translator = GoogleTranslator(source='auto', target='fa')
    try:
        title_fa = translator.translate(title)
        summary_fa = translator.translate(short_content[:200])
        fallback_text = f"📌 **عنوان:**\n{title_fa}\n\n📝 **خلاصه:**\n{summary_fa}"
        return clean_sources(fallback_text)
    except:
        return None

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

# پردازش و ارسال به تلگرام
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    raw_summary = getattr(entry, 'summary', title_en)
    clean_summary = clean_html(raw_summary)

    persian_news = summarize_and_translate_with_groq(title_en, clean_summary)

    if not persian_news:
        print(f"خبر {idx} پردازش نشد...")
        continue

    message = f"📊 **خبر فارکس ({idx}/10)**\n\n{persian_news}"

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
