import requests
import time
import json
import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import random
import logging

# Setup basic logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Configuration ---
TOKEN = os.environ.get('BOT_TOKEN', "8397374353:AAEytBiTKCK0wVqZ7-9__aPcPZrzh5iv9Gw")
API_URL = f"https://api.telegram.org/bot{TOKEN}"
USER_DATA_FILE = "user_data.json" # File to store user sessions

# --- User Data Persistence ---
def load_user_data():
    """Loads user data from a JSON file to prevent data loss on restart."""
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()} # Keys must be integers
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Could not load user data: {e}")
    return {}

def save_user_data():
    """Saves the current user data to a JSON file."""
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(user_data, f, indent=4)
    except IOError as e:
        logging.error(f"Could not save user data: {e}")

user_data = load_user_data()

# --- Health Check Web Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logging.info(f"Web server running on port {port}")
    server.serve_forever()

# --- Optimized API Request Functions ---
def send_request(url, data, timeout=20):
    try:
        response = requests.post(url, json=data, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"Request failed: {e}")
    return None

def get_request(url, params, timeout=20):
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"GET Request failed: {e}")
    return None

# --- Telegram Bot Core Functions ---
def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def send_media_group(chat_id, media_list, caption):
    url = f"{API_URL}/sendMediaGroup"
    if media_list:
        media_list[0]['caption'] = caption[:1024]
        media_list[0]['parse_mode'] = "HTML"
    data = {"chat_id": chat_id, "media": json.dumps(media_list)}
    return send_request(url, data)

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"{API_URL}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def answer_callback(callback_query_id, text=None):
    url = f"{API_URL}/answerCallbackQuery"
    data = {"callback_query_id": callback_query_id}
    if text:
        data["text"] = text
    send_request(url, data)

def cleanup_user_session(chat_id):
    if chat_id in user_data:
        del user_data[chat_id]
        save_user_data()

# --- Bot Logic Handlers ---
def handle_start(chat_id):
    user_data[chat_id] = {'step': 'awaiting_media_choice', 'media_list': [], 'title': '', 'links': []}
    save_user_data()
    keyboard = {
        "inline_keyboard": [
            [{"text": "📥 Send from phone", "callback_data": "send_from_phone"}],
            [{"text": "🌐 Add from Online", "callback_data": "add_from_online"}],
            [{"text": "⏩ Skip", "callback_data": "skip_media"}]
        ]
    }
    send_message(chat_id, "<b>স্বাগতম! পোস্ট তৈরি শুরু করা যাক।</b>\n\nপোস্টে মিডিয়া যোগ করার জন্য একটি বিকল্প বেছে নিন:", reply_markup=keyboard)

def add_online_media(chat_id):
    """
    Adds a high-quality, relevant, and safe online image to the user's media list
    using specific keywords.
    """
    # Safe and relevant keywords to get high-quality portraits
    keywords = "portrait,woman,fashion,saree,smile,asian"
    random_seed = random.randint(1, 2000) # Increased range for more variety
    
    # Using a service that allows keyword-based image search
    image_url = f"https://loremflickr.com/1280/720/{keywords}/all?random={random_seed}"
    
    if chat_id in user_data:
        user_data[chat_id]['media_list'].append({'type': 'photo', 'media': image_url})
        save_user_data()
        return len(user_data[chat_id]['media_list'])
    return 0

def handle_callback(chat_id, message_id, callback_data, callback_query_id):
    # Acknowledge callback immediately to make the UI responsive
    answer_callback(callback_query_id)

    if callback_data.startswith('add_'):
        edit_message(chat_id, message_id, "🔎 <i>অনলাইন থেকে ছবি খোঁজা হচ্ছে...</i>")
        
        media_count = add_online_media(chat_id)
        keyboard = {
            "inline_keyboard": [
                [{"text": "➕ Add another", "callback_data": "add_another_online"}],
                [{"text": "✅ Done", "callback_data": "done_media"}]
            ]
        }
        message_text = f"✅ অনলাইন থেকে একটি ছবি যোগ করা হয়েছে। (মোট: {media_count}টি)\n\nআরও যোগ করুন অথবা শেষ করতে <b>Done</b> বাটনে ক্লিক করুন।"
        edit_message(chat_id, message_id, message_text, keyboard)

    elif callback_data == 'send_from_phone':
        user_data[chat_id]['step'] = 'awaiting_media'
        save_user_data()
        keyboard = {"inline_keyboard": [[{"text": "✅ Done", "callback_data": "done_media"}]]}
        edit_message(chat_id, message_id, "এখন আপনার ফোন থেকে ছবি বা ভিডিও পাঠান।\n\nশেষ হলে <b>Done</b> বাটনে ক্লিক করুন।", keyboard)

    elif callback_data == 'done_media' or callback_data == 'skip_media':
        user_data[chat_id]['step'] = 'awaiting_title'
        save_user_data()
        media_count = len(user_data[chat_id].get('media_list', []))
        message = "মিডিয়া যোগ করা বাদ দেওয়া হলো।" if callback_data == 'skip_media' else \
                  f"{media_count}টি মিডিয়া গৃহীত হয়েছে।" if media_count > 0 else "কোনো মিডিয়া যোগ করা হয়নি।"
        keyboard = {"inline_keyboard": [[{"text": "Skip Title", "callback_data": "skip_title"}]]}
        edit_message(chat_id, message_id, f"{message}\n\nএখন পোস্টের জন্য একটি <b>টাইটেল</b> দিন। (ঐচ্ছিক)", keyboard)

    elif callback_data == 'skip_title':
        user_data[chat_id]['step'] = 'awaiting_link_url'
        save_user_data()
        edit_message(chat_id, message_id, "টাইটেল বাদ দেওয়া হলো।\n\nএবার প্রথম <b>লিংকটি</b> দিন:")
    
    elif callback_data == 'skip_label':
        label = f"Link {len(user_data[chat_id]['links']) + 1}"
        process_new_link(chat_id, message_id, label, is_callback=True)
    
    elif callback_data == 'finish_post':
        generate_post(chat_id, message_id, is_callback=True)

def handle_message(chat_id, message):
    if chat_id not in user_data:
        if message.get("text") == "/start": handle_start(chat_id)
        else: send_message(chat_id, "সেশন শেষ হয়ে গেছে। নতুন পোস্ট তৈরি করতে /start চাপুন।")
        return

    step = user_data[chat_id].get('step')
    
    if step == 'awaiting_media':
        media_type, file_id = None, None
        if 'photo' in message: media_type, file_id = 'photo', message['photo'][-1]['file_id']
        elif 'video' in message: media_type, file_id = 'video', message['video']['file_id']
        elif 'animation' in message: media_type, file_id = 'animation', message['animation']['file_id']
        
        if media_type:
            user_data[chat_id]['media_list'].append({'type': media_type, 'media': file_id})
            save_user_data()
            count = len(user_data[chat_id]['media_list'])
            send_message(chat_id, f"✅ মিডিয়া যোগ করা হয়েছে। (মোট: {count}টি)")
        return

    text = message.get('text')
    if not text: return
    
    if step == 'awaiting_title':
        user_data[chat_id]['title'] = text
        user_data[chat_id]['step'] = 'awaiting_link_url'
        save_user_data()
        send_message(chat_id, "টাইটেল গৃহীত হয়েছে। এবার প্রথম <b>লিংকটি</b> দিন:")
    elif step == 'awaiting_link_url':
        user_data[chat_id]['temp_url'] = text
        user_data[chat_id]['step'] = 'awaiting_link_label'
        save_user_data()
        keyboard = {"inline_keyboard": [[{"text": "Skip Label", "callback_data": "skip_label"}]]}
        send_message(chat_id, "লিংকটি গৃহীত হয়েছে। এখন এই লিংকের একটি <b>নাম দিন</b> (ঐচ্ছিক)।", keyboard)
    elif step == 'awaiting_link_label':
        process_new_link(chat_id, message.get('message_id'), text, is_callback=False)

def process_new_link(chat_id, message_id, label, is_callback):
    user_data[chat_id]['links'].append({'url': user_data[chat_id]['temp_url'], 'label': label})
    del user_data[chat_id]['temp_url']
    
    if len(user_data[chat_id]['links']) >= 10:
        generate_post(chat_id, message_id, is_callback)
        return
        
    user_data[chat_id]['step'] = 'awaiting_link_url'
    save_user_data()
    keyboard = {"inline_keyboard": [[{"text": "✅ Finish Post", "callback_data": "finish_post"}]]}
    message = f"লিংকটি যোগ করা হয়েছে। (মোট: {len(user_data[chat_id]['links'])}টি)\n\nএবার পরবর্তী লিংক দিন অথবা <b>Finish Post</b> বাটনে ক্লিক করুন।"
    
    if is_callback and message_id: edit_message(chat_id, message_id, message, keyboard)
    else: send_message(chat_id, message, keyboard)

def generate_post(chat_id, message_id, is_callback):
    data = user_data.get(chat_id, {})
    
    if not data.get('links'):
        message = "❌ <b>আপনি কোনো লিংক যোগ করেননি।</b> পোস্ট তৈরি বাতিল করা হলো।"
        if is_callback and message_id: edit_message(chat_id, message_id, message)
        else: send_message(chat_id, message)
    else:
        title = data.get('title') or "🍀 𝗪𝗮𝘁𝗰𝗵 𝗢𝗻𝗹𝗶𝗻𝗲 𝗢𝗿 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 🌱"
        links_text = "\n\n".join([f"<b>{link['label']}</b> 👉 {link['url']}" for link in data['links']])
        caption = f"{title}\n\n🎬 𝗩𝗜𝗗𝗘𝗢 👇👇\n\n📥 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝 𝐋𝐢𝐧𝐤𝐬 / 👀 𝐖𝐚𝐭𝗰𝗵 𝐎𝐧𝐥𝐢𝐧𝐞\n\n{links_text}"
        
        if media_list := data.get('media_list'):
            send_media_group(chat_id, media_list, caption)
        else:
            send_message(chat_id, caption)
            
        send_message(chat_id, "✅ <b>পোস্ট সফলভাবে তৈরি হয়েছে!</b>\n\nনতুন পোস্ট তৈরি করতে /start চাপুন।")
    
    cleanup_user_session(chat_id)

# --- Main Bot Loop ---
def main():
    logging.info("🤖 Bot starting...")
    Thread(target=run_web_server, daemon=True).start()
    
    offset = None
    while True:
        try:
            updates = get_request(f"{API_URL}/getUpdates", {"timeout": 50, "offset": offset})
            if updates and updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        if "message" in update:
                            handle_message(update["message"]["chat"]["id"], update["message"])
                        elif "callback_query" in update:
                            cb = update["callback_query"]
                            handle_callback(cb["message"]["chat"]["id"], cb["message"]["message_id"], cb["data"], cb["id"])
                    except Exception as e:
                        logging.error(f"Error processing update {update.get('update_id')}: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
