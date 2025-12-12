from flask import Flask, request, jsonify
import os
import requests
import google.generativeai as genai

app = Flask(__name__)

# دریافت تنظیمات از متغیرهای محیطی Vercel
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- پرامپت‌ها ---
PROMPT_TRANSCRIBE = """
Listen explicitly to the audio. 
It contains a mix of English and Persian.
Transcribe exactly what is said. 
Write Persian parts in Persian script, and English parts in English.
Do NOT translate yet.
"""

PROMPT_CORRECT = """
You are a friendly English teacher.
Task:
1. Translate any Persian parts to English.
2. Correct the grammar of the entire sentence.
3. Rewrite the final sentence in simple English (Level A1/A2).
Output Format: English: [Sentence]\nPersian Meaning: [Translation]
"""

# --- توابع کمکی ---
def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{TELEGRAM_API_URL}/editMessageText", json=payload)
    except: pass

def get_file_path(file_id):
    res = requests.post(f"{TELEGRAM_API_URL}/getFile", json={"file_id": file_id}).json()
    return res["result"]["file_path"] if res.get("ok") else None

# --- روت اصلی ---
@app.route('/', methods=['GET', 'POST'])
def handler():
    if request.method == 'GET':
        return "✅ VoxMind Bot is running on Vercel!"

    # مدیریت وب‌هوک (POST)
    try:
        data = request.get_json()
        if not data: return "ok"

        # 1. مدیریت دکمه
        if 'callback_query' in data:
            cb = data['callback_query']
            chat_id = cb['message']['chat']['id']
            msg_id = cb['message']['message_id']
            
            # پایان دادن به حالت لودینگ دکمه
            requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

            if cb['data'].startswith("correct|"):
                # استخراج متن اصلی از خود پیام تلگرام (خط دوم به بعد)
                try:
                    original_text = cb['message']['text'].split("\n\n")[1]
                except:
                    original_text = "Error reading text."

                if not GEMINI_API_KEY:
                    send_message(chat_id, "❌ API Key not set.")
                    return "ok"

                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                res = model.generate_content(f"{PROMPT_CORRECT}\nInput: {original_text}")
                
                edit_message(chat_id, msg_id, f"📝 {original_text}\n\n🎓 {res.text}")
            return "ok"

        # 2. مدیریت پیام
        if 'message' in data:
            msg = data['message']
            chat_id = msg['chat']['id']

            if 'text' in msg and msg['text'] == "/start":
                send_message(chat_id, "👋 سلام! روی سرور Vercel هستم.\nیک ویس بفرستید.")

            elif 'voice' in msg:
                if not GEMINI_API_KEY:
                    send_message(chat_id, "❌ کلید جمینای تنظیم نشده است.")
                    return "ok"
                
                wait = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "⏳..."}).json()
                msg_id = wait['result']['message_id']
                
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                fpath = get_file_path(msg['voice']['file_id'])
                if fpath:
                    # دانلود فایل
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fpath}"
                    audio_content = requests.get(file_url).content
                    
                    # ارسال به جمینای
                    res = model.generate_content([PROMPT_TRANSCRIBE, {"mime_type": "audio/ogg", "data": audio_content}])
                    
                    kb = {"inline_keyboard": [[{"text": "Correct 🇬🇧", "callback_data": "correct|start"}]]}
                    edit_message(chat_id, msg_id, f"📝 <b>متن خام:</b>\n\n{res.text}", reply_markup=kb)

    except Exception as e:
        print(f"Error: {e}")
    
    return "ok"

# برای اجرای لوکال (روی Vercel اجرا نمی‌شود)
if __name__ == '__main__':
    app.run(debug=True)
