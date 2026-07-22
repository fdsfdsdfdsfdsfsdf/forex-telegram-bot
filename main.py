import os
import time
import requests
import feedparser
from bs4 import BeautifulSoup

# دریافت متغیرهای محیطی از گیت‌هاب
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not GROQ_API_KEY:
    raise ValueError("کلیدهای TELEGRAM_TOKEN، TELEGRAM_CHAT_ID یا GROQ_API_KEY تنظیم نشده‌اند!")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# منابع اصلی اخبار زنده جهان
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

# استخراج متن خبر انگلیسی
def get_full_text(entry):
    raw_content = ""
    if hasattr(entry, 'content') and len(entry.content) > 0:
        raw_content = entry.content[0].value
    elif hasattr(entry, 'summary'):
        raw_content = entry.summary
    elif hasattr(entry, 'description'):
        raw_content = entry.description

    text = clean_html(raw_content)

    if (text.endswith("...") or text.endswith("…") or len(text) < 180) and hasattr(entry, 'link'):
        try:
            res = requests.get(entry.link, headers=HEADERS, timeout=6, allow_redirects=True)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                paragraphs = soup.find_all("p")
                p_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 35]
                if p_texts:
                    text = " ".join(p_texts[:4])
        except Exception as e:
            pass

    return text.rstrip(".… ")

# خلاصه سازی و روان‌سازی خبر توسط Groq API
def summarize_and_translate_with_groq(title, content):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
تو یک تحلیل‌گر و خبرنگار ارشد بازار فارکس هستی.
خبر انگلیسی زیر را بخوان و آن را به یک گزارش خبری بسیار خلاصه، روان، شکیل و جذاب به زبان فارسی تبدیل کن.

عنوان خبر: {title}
متن خبر: {content}

قوانین بسیار مهم:
۱. متن باید خلاصه، جذاب، کاملاً روان و به سبک خبرنگاری حرفه‌ای فارسی باشد (نه ترجمه کلمه‌به‌کلمه).
۲. تمام جملات باید کامل باشند و با نقطه تمام شوند.
۳. به هیچ عنوان و تحت هیچ شرایطی اسم منبع، نام سایت، لینک یا نام خبرگزاری را در متن قرار نده.
۴. خروجی فقط و فقط به فرمت زیر باشد:

📌 **عنوان:**
[عنوان جذاب فارسی]

📝 **خلاصه خبر:**
[متن خلاصه و جذاب فارسی]
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            result = res.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            print(f"خطای Groq API: {res.text}")
    except Exception as e:
        print(f"استثنا در ارتباط با Groq: {e}")

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

# پردازش با Groq و ارسال به تلگرام
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    full_text_en = get_full_text(entry)

    persian_news = summarize_and_translate_with_groq(title_en, full_text_en)

    if not persian_news:
        print(f"خبر {idx} پردازش نشد، رفتن به بعدی...")
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
