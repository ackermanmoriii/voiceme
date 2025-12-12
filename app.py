import os
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# --- تنظیمات (همه چیز از Environment خوانده می‌شود) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # تغییر مهم: کلید جمینای از تنظیمات خوانده می‌شود

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
4. Provide a brief explanation in Persian if needed.

Output Format (No Markdown, just plain text):
English: [Corrected Sentence]
Persian Meaning: [Persian Translation]
"""

# --- توابع ---
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

# --- روت‌ها ---
@app.route('/')
def home():
    return "✅ VoxMind Bot is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data: return "ok"

        # 1. دکمه
        if 'callback_query' in data:
            cb = data['callback_query']
            chat_id = cb['message']['chat']['id']
            msg_id = cb['message']['message_id']
            
            if cb['data'].startswith("correct|"):
                # دریافت متن از دکمه (چون حافظه نداریم، متن خام را کوتاه‌سازی کرده یا دوباره پردازش می‌کنیم)
                # اما روش بهتر: متن اصلی در پیام تلگرام هست. آن را برمی‌داریم.
                original_text = cb['message']['text'].split("\n\n")[1] # فرض بر اینکه فرمت پیام رعایت شده
                
                requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id'], "text": "Wait..."})
                
                if not GEMINI_API_KEY:
                    send_message(chat_id, "❌ کلید جمینای تنظیم نشده است.")
                    return "ok"

                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                res = model.generate_content(f"{PROMPT_CORRECT}\nInput: {original_text}")
                
                edit_message(chat_id, msg_id, f"📝 {original_text}\n\n🎓 {res.text}")
            return "ok"

        # 2. پیام
        if 'message' in data:
            msg = data['message']
            chat_id = msg['chat']['id']

            if 'text' in msg and msg['text'] == "/start":
                send_message(chat_id, "👋 سلام! من آماده‌ام.\nفقط کافیست یک <b>ویس (Voice)</b> بفرستید.")

            elif 'voice' in msg:
                if not GEMINI_API_KEY:
                    send_message(chat_id, "❌ خطای تنظیمات: کلید GEMINI_API_KEY در سرور ست نشده است.")
                    return "ok"
                
                wait = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "⏳..."}).json()
                msg_id = wait['result']['message_id']
                
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                fpath = get_file_path(msg['voice']['file_id'])
                if fpath:
                    audio = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fpath}").content
                    res = model.generate_content([PROMPT_TRANSCRIBE, {"mime_type": "audio/ogg", "data": audio}])
                    
                    # دکمه را ساده می‌کنیم
                    kb = {"inline_keyboard": [[{"text": "Correct 🇬🇧", "callback_data": "correct|start"}]]}
                    edit_message(chat_id, msg_id, f"📝 <b>متن خام:</b>\n\n{res.text}", reply_markup=kb)

    except Exception as e:
        print(f"Error: {e}")
    return "ok"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
