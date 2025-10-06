import requests
import time
import json
import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get('BOT_TOKEN', "8397374353:AAEytBiTKCK0wVqZ7-9__aPcPZrzh5iv9Gw")
API_URL = f"https://api.telegram.org/bot{TOKEN}"
user_data = {}

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
    print(f"Web server running on port {port}")
    server.serve_forever()

def send_request(url, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=60)
            return response.json()
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None

def get_request(url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=60)
            return response.json()
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def send_media_group(chat_id, media_list, caption):
    url = f"{API_URL}/sendMediaGroup"
    # Add caption to first media
    if media_list:
        media_list[0]['caption'] = caption
    data = {"chat_id": chat_id, "media": json.dumps(media_list)}
    return send_request(url, data)

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"{API_URL}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def answer_callback(callback_query_id):
    url = f"{API_URL}/answerCallbackQuery"
    send_request(url, {"callback_query_id": callback_query_id})

def handle_start(chat_id):
    user_data[chat_id] = {'step': 'awaiting_media', 'media_list': [], 'title': '', 'links': []}
    remove_keyboard = {"remove_keyboard": True}
    send_message(chat_id, "...", reply_markup=remove_keyboard)
    
    keyboard = {"inline_keyboard": [[{"text": "Done", "callback_data": "done_media"}]]}
    send_message(chat_id, "স্বাগতম! পোস্ট তৈরি শুরু করা যাক।\n\nছবি, ভিডিও বা GIF পাঠান। একাধিক পাঠাতে পারেন।\n\nশেষ হলে 'Done' বাটনে ক্লিক করুন।", keyboard)

def handle_callback(chat_id, message_id, callback_data, callback_query_id):
    answer_callback(callback_query_id)
    if callback_data == 'done_media':
        user_data[chat_id]['step'] = 'awaiting_title'
        media_count = len(user_data[chat_id]['media_list'])
        if media_count > 0:
            keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_title"}]]}
            edit_message(chat_id, message_id, f"{media_count}টি মিডিয়া গৃহীত হয়েছে।\n\nএখন পোস্টের জন্য একটি টাইটেল দিন। (ঐচ্ছিক)", keyboard)
        else:
            keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_title"}]]}
            edit_message(chat_id, message_id, "কোন মিডিয়া যোগ করা হয়নি।\n\nপোস্টের জন্য একটি টাইটেল দিন। (ঐচ্ছিক)", keyboard)
    elif callback_data == 'skip_title':
        user_data[chat_id]['step'] = 'awaiting_link_url'
        edit_message(chat_id, message_id, "ঠিক আছে, টাইটেল বাদ দেওয়া হলো।\n\nএবার প্রথম লিংকটি দিন:")
    elif callback_data == 'skip_label':
        label = f"Link {len(user_data[chat_id]['links']) + 1}"
        process_new_link(chat_id, message_id, label, True)
    elif callback_data == 'finish_post':
        generate_post(chat_id, message_id, True)

def handle_message(chat_id, message):
    if chat_id not in user_data:
        if "text" in message and message["text"] != "/start":
            start_keyboard = {"keyboard": [[{"text": "/start"}]], "resize_keyboard": True}
            send_message(chat_id, "নতুন পোস্ট তৈরি করতে /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
        else:
            handle_start(chat_id)
        return
    
    step = user_data[chat_id].get('step')
    
    if step == 'awaiting_media':
        media_added = False
        if 'photo' in message:
            media_id = message['photo'][-1]['file_id']
            user_data[chat_id]['media_list'].append({
                'type': 'photo',
                'media': media_id
            })
            media_added = True
        elif 'video' in message:
            media_id = message['video']['file_id']
            user_data[chat_id]['media_list'].append({
                'type': 'video',
                'media': media_id
            })
            media_added = True
        elif 'animation' in message:
            media_id = message['animation']['file_id']
            user_data[chat_id]['media_list'].append({
                'type': 'animation',
                'media': media_id
            })
            media_added = True
        
        if media_added:
            count = len(user_data[chat_id]['media_list'])
            keyboard = {"inline_keyboard": [[{"text": "Done", "callback_data": "done_media"}]]}
            send_message(chat_id, f"✅ মিডিয়া যোগ করা হয়েছে। (মোট: {count}টি)\n\nআরও যোগ করুন অথবা 'Done' বাটনে ক্লিক করুন।", reply_markup=keyboard)
        return
    
    if 'text' not in message:
        return
    
    text = message['text']
    
    if step == 'awaiting_title':
        user_data[chat_id]['title'] = text
        user_data[chat_id]['step'] = 'awaiting_link_url'
        send_message(chat_id, "দারুণ! এবার প্রথম লিংকটি দিন:")
    elif step == 'awaiting_link_url':
        user_data[chat_id]['temp_url'] = text
        user_data[chat_id]['step'] = 'awaiting_link_label'
        keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_label"}]]}
        send_message(chat_id, "লিংকটি গৃহীত হয়েছে। এখন এই লিংকের একটি নাম দিন (ঐচ্ছিক)।", keyboard)
    elif step == 'awaiting_link_label':
        process_new_link(chat_id, None, text, False)

def process_new_link(chat_id, message_id, label, is_callback):
    user_data[chat_id]['links'].append({'url': user_data[chat_id]['temp_url'], 'label': label})
    del user_data[chat_id]['temp_url']
    if len(user_data[chat_id]['links']) >= 10:
        message = "আপনি সর্বোচ্চ ১০টি লিংক যোগ করেছেন। পোস্টটি এখন তৈরি করা হচ্ছে..."
        if is_callback:
            edit_message(chat_id, message_id, message)
        else:
            send_message(chat_id, message)
        generate_post(chat_id, message_id, is_callback)
        return
    user_data[chat_id]['step'] = 'awaiting_link_url'
    keyboard = {"inline_keyboard": [[{"text": "Finish Post", "callback_data": "finish_post"}]]}
    message = f"লিংকটি যোগ করা হয়েছে। (মোট: {len(user_data[chat_id]['links'])}টি)\n\nএবার পরবর্তী লিংকটি দিন অথবা শেষ করতে বাটনে ক্লিক করুন।"
    if is_callback:
        edit_message(chat_id, message_id, message, keyboard)
    else:
        send_message(chat_id, message, keyboard)

def generate_post(chat_id, message_id, is_callback):
    data = user_data.get(chat_id, {})
    start_keyboard = {"keyboard": [[{"text": "/start"}]], "resize_keyboard": True}
    
    if not data.get('links'):
        message = "❌ আপনি কোনো লিংক যোগ করেননি। পোস্ট তৈরি বাতিল করা হলো।"
        if is_callback and message_id:
            edit_message(chat_id, message_id, message)
        else:
            send_message(chat_id, message)
        send_message(chat_id, "নতুন পোস্ট তৈরি করতে /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
    else:
        title = data['title'] or "🍀 𝗪𝗮𝘁𝗰𝗵 𝗢𝗻𝗹𝗶𝗻𝗲 𝗢𝗿 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 🌱 ✔️ #desivideos"
        links_text = "\n\n".join([f"{link['label']} 👉 {link['url']}" for link in data['links']])
        caption = f"{title}\n\n🎬 𝗩𝗜𝗗𝗘𝗢 👇👇\n\n📥 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝 𝐋𝐢𝐧𝐤𝐬 / 👀 𝐖𝐚𝐭𝐜𝗵 𝐎𝐧𝐥𝐢𝐧𝐞\n\n{links_text}\n\nFull hd++++8k video 🇽\nRomes hd 4k hd video🇽"
        
        media_list = data.get('media_list', [])
        
        if media_list:
            send_media_group(chat_id, media_list, caption)
        else:
            send_message(chat_id, caption)
            
        send_message(chat_id, "✅ পোস্ট সফলভাবে তৈরি হয়েছে!\n\nনতুন পোস্ট তৈরি করতে নিচের /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
    
    if chat_id in user_data:
        del user_data[chat_id]

def main():
    print("🤖 Bot starting...")
    
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    offset = None
    while True:
        try:
            url = f"{API_URL}/getUpdates"
            updates = get_request(url, {"timeout": 50, "offset": offset})
            if updates and updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        message = update["message"]
                        chat_id = message["chat"]["id"]
                        if "text" in message:
                            text = message["text"]
                            if text in ["/start", "/newpost"]:
                                handle_start(chat_id)
                            else:
                                handle_message(chat_id, message)
                        elif "photo" in message or "video" in message or "animation" in message:
                            handle_message(chat_id, message)
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        handle_callback(callback["message"]["chat"]["id"], callback["message"]["message_id"], callback["data"], callback["id"])
            else:
                time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
