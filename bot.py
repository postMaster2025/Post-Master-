import requests
import time
import json
import os

# --- আপনার টেলিগ্রাম বট টোকেনটি এখানে বসান ---
# নিচের লাইনে "YOUR_TELEGRAM_BOT_TOKEN_HERE" এর পরিবর্তে আপনার আসল টোকেনটি দিন।
TOKEN = "8397374353:AAEytBiTKCK0wVqZ7-9__aPcPZrzh5iv9Gw"

# (বিকল্প ও নিরাপদ পদ্ধতি) এনভায়রনমেন্ট ভেরিয়েবল থেকে টোকেন লোড করা
# আপনি যদি উপরের লাইনে সরাসরি টোকেন না বসাতে চান, তাহলে নিচের লাইনটি আনকমেন্ট করুন
# এবং আপনার সিস্টেমে 'BOT_TOKEN' নামে এনভায়রনমেন্ট ভেরিয়েবল সেট করুন।
# TOKEN = os.environ.get('BOT_TOKEN')


API_URL = f"https://api.telegram.org/bot{TOKEN}"
user_data = {}

def send_request(url, data, max_retries=3):
    """POST রিকোয়েস্ট পাঠানোর জন্য ফাংশন, নেটওয়ার্ক সমস্যার জন্য কয়েকবার চেষ্টা করবে।"""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=60)
            return response.json()
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None

def get_request(url, params, max_retries=3):
    """GET রিকোয়েস্ট পাঠানোর জন্য ফাংশন।"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=60)
            return response.json()
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None

def send_message(chat_id, text, reply_markup=None):
    """ব্যবহারকারীকে টেক্সট মেসেজ পাঠায়।"""
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def send_photo(chat_id, photo_id, caption):
    """ক্যাপশনসহ ছবি পাঠায়।"""
    url = f"{API_URL}/sendPhoto"
    data = {"chat_id": chat_id, "photo": photo_id, "caption": caption}
    return send_request(url, data)

def edit_message(chat_id, message_id, text, reply_markup=None):
    """আগের পাঠানো মেসেজ এডিট করে।"""
    url = f"{API_URL}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return send_request(url, data)

def answer_callback(callback_query_id):
    """ইনলাইন বাটনে ক্লিক করার পর লোডিং আইকন বন্ধ করে।"""
    url = f"{API_URL}/answerCallbackQuery"
    send_request(url, {"callback_query_id": callback_query_id})

def handle_start(chat_id):
    """'/start' কমান্ড হ্যান্ডেল করে এবং পোস্ট তৈরির প্রক্রিয়া শুরু করে।"""
    user_data[chat_id] = {'step': 'awaiting_photo', 'photo_id': '', 'title': '', 'links': []}
    # Remove any custom keyboard and show the default one
    remove_keyboard = {"remove_keyboard": True}
    send_message(chat_id, "...", reply_markup=remove_keyboard) # A small trick to remove the keyboard first
    
    keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_photo"}]]}
    send_message(chat_id, "স্বাগতম! পোস্ট তৈরি শুরু করা যাক।\n\nপ্রথমে একটি ছবি পাঠান। (ঐচ্ছিক)", keyboard)

def handle_callback(chat_id, message_id, callback_data, callback_query_id):
    """ইনলাইন কিবোর্ডের বাটন ক্লিক হ্যান্ডেল করে।"""
    answer_callback(callback_query_id)
    if callback_data == 'skip_photo':
        user_data[chat_id]['step'] = 'awaiting_title'
        keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_title"}]]}
        edit_message(chat_id, message_id, "ঠিক আছে, ছবি বাদ দেওয়া হলো।\n\nপোস্টের জন্য একটি টাইটেল দিন। (ঐচ্ছিক)", keyboard)
    elif callback_data == 'skip_title':
        user_data[chat_id]['step'] = 'awaiting_link_url'
        edit_message(chat_id, message_id, "ঠিক আছে, টাইটেল বাদ দেওয়া হলো।\n\nএবার প্রথম লিংকটি দিন:")
    elif callback_data == 'skip_label':
        label = f"Link {len(user_data[chat_id]['links']) + 1}"
        process_new_link(chat_id, message_id, label, True)
    elif callback_data == 'finish_post':
        generate_post(chat_id, message_id, True)

def handle_message(chat_id, message):
    """ব্যবহারকারীর পাঠানো মেসেজ (টেক্সট বা ছবি) হ্যান্ডেল করে।"""
    if chat_id not in user_data:
        # If the user sends a random message without starting a process, guide them to start
        if "text" in message and message["text"] != "/start":
            start_keyboard = {"keyboard": [[{"text": "/start"}]], "resize_keyboard": True}
            send_message(chat_id, "নতুন পোস্ট তৈরি করতে /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
        else: # This handles the /start command itself
            handle_start(chat_id)
        return
    
    step = user_data[chat_id].get('step')
    
    # ছবি হ্যান্ডেল করার অংশ
    if step == 'awaiting_photo':
        if 'photo' in message:
            photo_id = message['photo'][-1]['file_id']
            user_data[chat_id]['photo_id'] = photo_id
            user_data[chat_id]['step'] = 'awaiting_title'
            keyboard = {"inline_keyboard": [[{"text": "Skip", "callback_data": "skip_title"}]]}
            send_message(chat_id, "ছবি গৃহীত হয়েছে।\n\nএখন পোস্টের জন্য একটি টাইটেল দিন। (ঐচ্ছিক)", keyboard)
        else:
            send_message(chat_id, "দয়া করে একটি ছবি পাঠান অথবা Skip বাটনে ক্লিক করুন।")
        return
    
    # টেক্সট মেসেজ হ্যান্ডেল করার অংশ
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
    """নতুন লিংক যোগ করে এবং পরবর্তী ধাপের জন্য প্রস্তুত করে।"""
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
    """সব তথ্য একত্রিত করে চূড়ান্ত পোস্ট তৈরি করে, পাঠায় এবং /start বাটন দেখায়।"""
    data = user_data.get(chat_id, {})
    
    # '/start' বাটনসহ একটি রিপ্লাই কিবোর্ড তৈরি করা
    start_keyboard = {
        "keyboard": [[{"text": "/start"}]],
        "resize_keyboard": True
    }
    
    if not data.get('links'):
        message = "❌ আপনি কোনো লিংক যোগ করেননি। পোস্ট তৈরি বাতিল করা হলো।"
        if is_callback and message_id:
            # আগের মেসেজটি এডিট করে ভুলের কারণ জানানো
            edit_message(chat_id, message_id, message)
        else:
            send_message(chat_id, message)
        # নতুন করে শুরু করার জন্য /start বাটনসহ মেসেজ পাঠানো
        send_message(chat_id, "নতুন পোস্ট তৈরি করতে /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
    else:
        title = data['title'] or "🍀 𝗪𝗮𝘁𝗰𝗵 𝗢𝗻𝗹𝗶𝗻𝗲 𝗢𝗿 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 🌱 ✔️ #desivideos"
        links_text = "\n\n".join([f"{link['label']} 👉 {link['url']}" for link in data['links']])
        caption = f"{title}\n\n🎬 𝗩𝗜𝗗𝗘𝗢 👇👇\n\n📥 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝 𝐋𝐢𝐧𝐤𝐬 / 👀 𝐖𝐚𝘁𝗰𝗵 𝐎𝐧𝐥𝐢𝐧𝐞\n\n{links_text}\n\nFull hd++++8k video 🇽\nRomes hd 4k hd video🇽"
        
        # ছবি থাকলে ক্যাপশনসহ পাঠাবে, না থাকলে শুধু টেক্সট পাঠাবে
        photo_id = data.get('photo_id')
        if photo_id:
            send_photo(chat_id, photo_id, caption)
        else:
            send_message(chat_id, caption)
            
        # পোস্ট সফলভাবে তৈরির মেসেজ এবং /start বাটন পাঠানো
        send_message(chat_id, "✅ পোস্ট সফলভাবে তৈরি হয়েছে!\n\nনতুন পোস্ট তৈরি করতে নিচের /start বাটনে ক্লিক করুন।", reply_markup=start_keyboard)
    
    # প্রক্রিয়া শেষ হওয়ার পর ব্যবহারকারীর ডেটা মুছে ফেলা হয়
    if chat_id in user_data:
        del user_data[chat_id]

def main():
    """বটের প্রধান ফাংশন, যা সবসময় চলতে থাকে এবং টেলিগ্রাম থেকে আপডেট চেক করে।"""
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ ত্রুটি: অনুগ্রহ করে কোডের মধ্যে আপনার টেলিগ্রাম বট টোকেনটি সেট করুন।")
        return
        
    print("🤖 বট চালু হচ্ছে...")
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
                        elif "photo" in message:
                            handle_message(chat_id, message)
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        handle_callback(callback["message"]["chat"]["id"], callback["message"]["message_id"], callback["data"], callback["id"])
            else:
                time.sleep(5)
        except Exception as e:
            print(f"একটি ত্রুটি ঘটেছে: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
