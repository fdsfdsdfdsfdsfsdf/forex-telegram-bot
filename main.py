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
    raise ValueError("کلیدهای TELEGRAM_TOKEN، TELEGRAM_CHAT_ID یا GROQ_API_KEY تنظیم نشده‌اند!")

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

# مدل‌های عمومی و آزاد Groq
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "openai/gpt-oss-20b"
]

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

# پاک‌سازی خودکار هرگونه نام منبع یا لینک
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

translator = GoogleTranslator(source='auto', target='fa')

# مترجم پشتیبان پایتون در صورت عدم پاسخگویی هوش مصنوعی
def translate_sentence_by_sentence(text_en):
    sentences = re.split(r'(?<=[.!?])\s+', text_en)
    translated_sentences = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 12:
            continue
        try:
            translated = translator.translate(sent)
            if translated and not translated.endswith("..."):
                translated_sentences.append(translated)
        except:
            pass
    full_persian = " ".join(translated_sentences[:3]) # حداکثر ۳ جمله
    if full_persian and not full_persian.endswith((".", "!", "؟")):
        full_persian += "."
    return full_persian

def get_full_text(entry):
    raw_content = ""
    if hasattr(entry, 'content') and len(entry.content) > 0:
        raw_content = entry.content[0].value
    elif hasattr(entry, 'summary'):
        raw_content = entry.summary
    elif hasattr(entry, 'description'):
        raw_content = entry.description

    text = clean_html(raw_content)

    if (text.endswith("...") or text.endswith("…") or len(text) < 200) and hasattr(entry, 'link'):
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

# پردازش هوش مصنوعی + پشتیبان خودکار
def generate_one_paragraph_news(title, content):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
تو یک خبرنگار و تحلیل‌گر ارشد بازار فارکس هستی.
خبر انگلیسی زیر را بخوان و آن را به یک گزارش خبر بسیار روان، شکیل و «دقیقاً در حد یک پاراگراف کامل» به زبان فارسی بازنویسی کن.

عنوان خبر: {title}
متن خبر: {content}

دستورالعمل‌های حیاتی:
۱. متن گزارش باید «دقیقاً در حد یک پاراگراف روان و جامع» باشد (حدود ۵۰ الی ۷۰ کلمه، نه خیلی کوتاه و نه خیلی طولانی).
۲. نگارش باید کاملاً جذاب و به سبک خبرنگاری حرفه‌ای فارسی باشد (اصلاً ترجمه ماشینی نباشد).
۳. تمام جملات باید کامل بوده و با نقطه تمام شوند.
۴. تحت هیچ شرایطی نام منبع، نام سایت، نام خبرگزاری، لینک یا نام برند را در خروجی قرار نده.

فرمت خروجی (دقیقاً به این شکل):
📌 **عنوان:**
[عنوان جذاب و حرفه‌ای فارسی]

📝 **خلاصه خبر:**
[یک پاراگراف کامل، روان و جذاب فارسی]
"""

    # تست مدل‌های Groq
    for model_name in GROQ_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 350
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                result = res.json()
                output = result["choices"][0]["message"]["content"].strip()
                print(f"خبر با مدل {model_name} پردازش شد.")
                return clean_sources(output)
            else:
                print(f"مدل {model_name} پاسخ نداد (کد {res.status_code})")
        except Exception as e:
            print(f"خطا در مدل {model_name}: {e}")

    # در صورت عدم پاسخگویی Groq، استفاده از سیستم پشتیبان
    print("استفاده از سیستم پشتیبان ترجمه...")
    try:
        title_fa = translator.translate(title)
        body_fa = translate_sentence_by_sentence(content)
        fallback_text = f"📌 **عنوان:**\n{title_fa}\n\n📝 **خلاصه خبر:**\n{body_fa}"
        return clean_sources(fallback_text)
    except Exception as e:
        print("خطا در سیستم پشتیبان:", e)
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
    full_text_en = get_full_text(entry)

    persian_news = generate_one_paragraph_news(title_en, full_text_en)

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
