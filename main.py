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
    raise ValueError("کلیدهای تلگرام ست نشده‌اند!")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# معتبرترین منابع خبری زنده فارکس در دنیا
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

    # اگر متن خیلی کوتاه بود، کل پاراگراف‌های صفحه خبر را استخراج کن
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

translator = GoogleTranslator(source='auto', target='fa')

# ترجمه جمله‌به‌جمله جهت جلوگیری از ناقص ماندن جملات
def translate_sentence_by_sentence(text_en):
    # تفکیک متن انگلیسی بر اساس نقطه و علامت سوال (جملات کامل)
    sentences = re.split(r'(?<=[.!?])\s+', text_en)
    translated_sentences = []
    
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 12: # حذف کلمات کوتاه یا تبلیغاتی
            continue
        try:
            translated = translator.translate(sent)
            if translated and not translated.endswith("..."):
                translated_sentences.append(translated)
        except Exception as e:
            print("خطا در ترجمه جمله:", e)

    full_persian = " ".join(translated_sentences)
    
    # اضافه کردن نقطه پایان در صورتی که نباشد
    if full_persian and not full_persian.endswith((".", "!", "؟")):
        full_persian += "."
        
    return full_persian

entries_to_process = []

# جمع‌آوری ۱۰ خبر برتر انگلیسی
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
        print(f"خطا در دریافت خبر از {url}: {e}")

    if len(entries_to_process) >= 10:
        break

print(f"تعداد {len(entries_to_process)} خبر برتر انگلیسی پیدا شد.")

# ترجمه و ارسال اخبار به تلگرام
for idx, entry in enumerate(entries_to_process[:10], 1):
    title_en = entry.title
    full_text_en = get_full_text(entry)

    # ترجمه عنوان
    try:
        title_fa = translator.translate(title_en)
    except:
        title_fa = title_en

    # ترجمه متن به صورت جمله‌به‌جمله و کامل
    summary_fa = translate_sentence_by_sentence(full_text_en)

    if not summary_fa:
        summary_fa = title_fa

    # ساخت قالب نهایی متنی
    message = f"📊 **خبر فارکس ({idx}/10)**\n\n📌 **عنوان:**\n{title_fa}\n\n📝 **متن خبر:**\n{summary_fa}"

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
