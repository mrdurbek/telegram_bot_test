# -*- coding: utf-8 -*-
import telebot
import sqlite3
from telebot import types
import json
import random
import datetime
import os
import threading
import time

# Try to import Flask (optional for health checks)
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Simple HTTP server fallback
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"PUBG UC Bot is running")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# ---------------- Configuration ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# You can keep @username here or numeric id; code will try to resolve to numeric id.
CHANNEL_ID = "@mypubgbot_test"
GROUP_ID = "@mypubg_test"
YOUTUBE_LINK = "https://youtube.com/@swkombat?si=5vVIGfj_NYx-yJLK"
ADMIN_IDS = [6322816106, 1401881769, 6072785933]
DB_NAME = "bot.db"

bot = telebot.TeleBot(BOT_TOKEN)

# numeric resolved ids (will be set in resolve_chat_ids())
CHAT_CHANNEL_ID = None
CHAT_GROUP_ID = None

# ---------------- Helpers for JSON / DB ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

for file in ["users.json", "competitions.json", "devices.json"]:
    if not os.path.exists(file):
        save_json(file, {})

# ---------------- Utility: Resolve chat ids ----------------
def resolve_chat_ids():
    global CHAT_CHANNEL_ID, CHAT_GROUP_ID
    # Resolve channel
    try:
        if isinstance(CHANNEL_ID, str) and CHANNEL_ID.startswith("@"):
            chat = bot.get_chat(CHANNEL_ID)
            CHAT_CHANNEL_ID = chat.id
        else:
            CHAT_CHANNEL_ID = int(CHANNEL_ID)
        print(f"Resolved CHANNEL_ID -> {CHAT_CHANNEL_ID}")
    except Exception as e:
        print(f"Warning: failed to resolve CHANNEL_ID {CHANNEL_ID}: {e}")
        CHAT_CHANNEL_ID = CHANNEL_ID  # keep original; sends will likely fail but at least we tried

    # Resolve group
    try:
        if isinstance(GROUP_ID, str) and GROUP_ID.startswith("@"):
            chat = bot.get_chat(GROUP_ID)
            CHAT_GROUP_ID = chat.id
        else:
            CHAT_GROUP_ID = int(GROUP_ID)
        print(f"Resolved GROUP_ID -> {CHAT_GROUP_ID}")
    except Exception as e:
        print(f"Warning: failed to resolve GROUP_ID {GROUP_ID}: {e}")
        CHAT_GROUP_ID = GROUP_ID

# ---------------- Menus & subscription ----------------
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        "📨 Referal havola",
        "📊 Referal reyting",
        "💰 UC balans",
        "💸 UC yechish"
    ]
    if user_id in ADMIN_IDS:
        buttons.insert(3, "🎁 Konkurslar")
    if len(buttons) >= 4:
        markup.row(buttons[0], buttons[1])
        markup.row(buttons[2], buttons[3])
    else:
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.row(*row)
    if len(buttons) > 4:
        markup.row(buttons[4])
    return markup

def send_main_menu(user_id, text="Asosiy menyu:"):
    markup = main_menu(user_id)
    bot.send_message(user_id, text, reply_markup=markup)

def check_subscription(user_id):
    try:
        # If CHAT_CHANNEL_ID/GROUP_ID not resolved yet, try using original strings
        ch = CHAT_CHANNEL_ID if CHAT_CHANNEL_ID is not None else CHANNEL_ID
        gr = CHAT_GROUP_ID if CHAT_GROUP_ID is not None else GROUP_ID
        channel = bot.get_chat_member(ch, user_id)
        group = bot.get_chat_member(gr, user_id)
        ok = (channel.status in ["member", "administrator", "creator"] and
              group.status in ["member", "administrator", "creator"])
        return ok
    except Exception as e:
        print(f"Subscription check error for user {user_id}: {e}")
        return False

def send_subscription_prompt(user_id):
    markup = types.InlineKeyboardMarkup()
    # Use direct t.me links built from usernames (strip @) if they exist
    channel_username = CHANNEL_ID[1:] if isinstance(CHANNEL_ID, str) and CHANNEL_ID.startswith("@") else None
    group_username = GROUP_ID[1:] if isinstance(GROUP_ID, str) and GROUP_ID.startswith("@") else None

    if channel_username:
        markup.add(types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{channel_username}"))
    else:
        # fallback to chat id link not always possible; still show text
        markup.add(types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url="https://t.me/"))

    if group_username:
        markup.add(types.InlineKeyboardButton("👥 Guruhga obuna bo'lish", url=f"https://t.me/{group_username}"))
    else:
        markup.add(types.InlineKeyboardButton("👥 Guruhga obuna bo'lish", url="https://t.me/"))

    markup.add(types.InlineKeyboardButton("📺 YouTube kanalga obuna bo'lish", url=YOUTUBE_LINK))
    markup.add(types.InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_sub"))

    text = (
        "🔒 Botdan foydalanish uchun quyidagilarga obuna bo'ling:\n\n"
        f"{CHANNEL_ID} - Telegram kanal\n"
        f"{GROUP_ID} - Telegram guruh\n"
        f"{YOUTUBE_LINK} - YouTube kanal\n\n"
        "Obuna bo'lgach, '✅ Obuna bo'ldim' tugmasini bosing."
    )
    bot.send_message(user_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    if check_subscription(call.from_user.id):
        bot.send_message(call.from_user.id, "✅ Obuna tasdiqlandi!")
        send_main_menu(call.from_user.id)
    else:
        bot.send_message(call.from_user.id, "❌ Obuna aniqlanmadi. Iltimos, tekshirib qayta urinib ko'ring.")

# ---------------- Referral & rating ----------------
def add_user(user_id, ref_id=None):
    users = load_json("users.json")
    if str(user_id) not in users:
        users[str(user_id)] = {
            "uc": 0,
            "ref": str(ref_id) if ref_id else None,
            "refs": [],
            "joined": str(datetime.date.today())
        }
        if ref_id and str(ref_id) in users:
            users[str(ref_id)]["refs"].append(str(user_id))
            users[str(ref_id)]["uc"] += 3
        save_json("users.json", users)

@bot.message_handler(func=lambda msg: msg.text == "📨 Referal havola")
def send_ref_link(message):
    try:
        username = bot.get_me().username
    except Exception:
        username = None
    if username:
        link = f"https://t.me/{username}?start={message.from_user.id}"
    else:
        link = f"https://t.me/{bot.get_me().id}?start={message.from_user.id}"
    bot.send_message(message.chat.id, f"🔗 Referal havolangiz:\n{link}")

@bot.message_handler(func=lambda msg: msg.text == "💰 UC balans")
def send_uc(message):
    users = load_json("users.json")
    uc = users.get(str(message.from_user.id), {}).get("uc", 0)
    bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {uc} UC")

# (Referral rating functions unchanged; omitted here for brevity in commentary)

# ---------------- Competitions core ----------------
def check_expired_competitions():
    competitions = load_json("competitions.json")
    now = datetime.datetime.now()
    for comp_id, comp in list(competitions.items()):
        try:
            dl_str = comp.get("deadline")
            if not dl_str:
                continue
            try:
                deadline = datetime.datetime.fromisoformat(dl_str)
            except Exception:
                # try common fallback format
                try:
                    deadline = datetime.datetime.strptime(dl_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    # second fallback: try without seconds
                    deadline = datetime.datetime.strptime(dl_str, "%Y-%m-%d %H:%M")
            if now >= deadline and not comp.get("winners_announced", False):
                print(f"[Checker] finishing comp {comp_id} (now {now} >= {deadline})")
                finish_competition(comp_id)
        except Exception as e:
            print(f"Error processing competition {comp_id}: {e}")

def finish_competition(comp_id):
    competitions = load_json("competitions.json")
    comp = competitions.get(comp_id)
    if not comp:
        print(f"finish_competition: competition {comp_id} not found")
        return

    if comp.get("winners_announced"):
        print(f"finish_competition: competition {comp_id} already processed")
        return

    participants = comp.get("participants") or []
    winners_count = comp.get("winners", 1)

    if not participants:
        announcement = f"⚠️ #{comp_id} konkursi yakunlandi. Ishtirokchilar bo'lmadi."
        _send_to_group_and_channel(announcement, comp_id)
        comp["winners_announced"] = True
        competitions[comp_id] = comp
        save_json("competitions.json", competitions)
        return

    try:
        winners_count = max(1, int(winners_count))
    except Exception:
        winners_count = 1

    winners_count = min(winners_count, len(participants))
    try:
        winners = random.sample(participants, winners_count)
    except Exception as e:
        print(f"Error sampling winners for comp {comp_id}: {e}")
        winners = participants[:winners_count]

    winner_mentions = []
    for winner_id in winners:
        mention = None
        try:
            uid_int = int(winner_id)
            try:
                user = bot.get_chat(uid_int)
                if getattr(user, "username", None):
                    mention = f"@{user.username}"
                else:
                    name = getattr(user, "first_name", "") or "User"
                    mention = f"{name} (ID:{uid_int})"
            except Exception as e:
                print(f"Could not get chat for winner {winner_id}: {e}")
                mention = f"ID:{winner_id}"
        except Exception:
            mention = f"ID:{winner_id}"
        winner_mentions.append(mention)

    winners_text = "\n".join([f"🏆 {i+1}. {w}" for i, w in enumerate(winner_mentions)])
    announcement = (
        f"🎊 Konkurs #{comp_id} yakunlandi! 🎊\n\n"
        f"G'oliblar ({len(winners)} ta):\n{winners_text}\n\n"
        "Tabriklaymiz! 🎉 Adminlar tez orada siz bilan bog'lanishadi."
    )

    # Send to group & channel and capture send errors
    send_errors = _send_to_group_and_channel(announcement, comp_id)

    # Notify winners privately (best-effort)
    for winner_id in winners:
        try:
            uid_int = int(winner_id)
            try:
                bot.send_message(uid_int, f"🎉 Tabriklaymiz! Siz #{comp_id} konkursining g'oliblaridan bo'ldingiz!\nAdminlar tez orada bog'lanadi.")
            except Exception as e:
                print(f"Could not send private message to winner {winner_id}: {e}")
        except Exception as e:
            print(f"Invalid winner id {winner_id}: {e}")

    # Always mark as finished and save winners
    comp["winners"] = winners
    comp["winners_announced"] = True
    competitions[comp_id] = comp
    save_json("competitions.json", competitions)

    # Notify admins
    admins_msg = f"🏆 #{comp_id} konkurs yakunlandi. G'oliblar:\n" + "\n".join([f"- {w}" for w in winner_mentions])
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, admins_msg)
        except Exception as e:
            print(f"Could not notify admin {admin_id}: {e}")

    if send_errors:
        print(f"finish_competition {comp_id} had send errors: {send_errors}")

def _send_to_group_and_channel(text, comp_id=None):
    """
    Helper: try to send `text` to group and channel using resolved numeric ids.
    Returns list of error strings (empty if all ok).
    """
    errors = []
    ch = CHAT_CHANNEL_ID if CHAT_CHANNEL_ID is not None else CHANNEL_ID
    gr = CHAT_GROUP_ID if CHAT_GROUP_ID is not None else GROUP_ID

    # Send to group
    try:
        bot.send_message(gr, text)
    except Exception as e:
        err = f"group:{e}"
        print(f"Error sending announcement to group for comp {comp_id}: {e}")
        errors.append(err)

    # Send to channel
    try:
        bot.send_message(ch, text)
    except Exception as e:
        err = f"channel:{e}"
        print(f"Error sending announcement to channel for comp {comp_id}: {e}")
        errors.append(err)

    return errors

# ---------------- Competition creation & posting ----------------
def process_comp_winners_count(message, file_id, deadline):
    try:
        winners = int(message.text)
        if winners <= 0:
            raise ValueError

        competitions = load_json("competitions.json")
        comp_id = str(len(competitions) + 1)

        # Store deadline as ISO format
        # We'll store without timezone to keep format consistent
        deadline_iso = deadline.isoformat()

        competitions[comp_id] = {
            "file_id": file_id,
            "deadline": deadline_iso,
            "winners": winners,
            "participants": []
        }

        save_json("competitions.json", competitions)
        bot.send_message(message.chat.id, f"Konkurs №{comp_id} yaratildi. Endi e'lon qilinadi.")
        post_competition(comp_id)

    except ValueError:
        bot.send_message(message.chat.id, "Iltimos, 0 dan katta butun son kiriting:")

def post_competition(comp_id):
    competitions = load_json("competitions.json")
    comp = competitions.get(comp_id)
    if not comp:
        print(f"post_competition: comp {comp_id} not found")
        return

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("✅ Qatnashish", callback_data=f"join_{comp_id}"))

    caption = (
        f"🎉 Yangi konkurs #{comp_id}! 🎉\n\n"
        f"⏳ Tugash vaqti: {comp['deadline']}\n"
        f"🏆 G'oliblar soni: {comp['winners']}\n\n"
        "Ishtirok etish uchun quyidagi tugmani bosing!"
    )

    ch = CHAT_CHANNEL_ID if CHAT_CHANNEL_ID is not None else CHANNEL_ID
    gr = CHAT_GROUP_ID if CHAT_GROUP_ID is not None else GROUP_ID

    try:
        bot.send_photo(ch, comp["file_id"], caption=caption, reply_markup=keyboard)
    except Exception as e:
        print(f"Error posting competition {comp_id} to channel: {e}")

    try:
        bot.send_photo(gr, comp["file_id"], caption=caption, reply_markup=keyboard)
    except Exception as e:
        print(f"Error posting competition {comp_id} to group: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("join_"))
def join_competition(call):
    comp_id = call.data.split("_")[1]
    competitions = load_json("competitions.json")
    comp = competitions.get(comp_id)
    if not comp:
        return bot.answer_callback_query(call.id, "Konkurs topilmadi.")
    uid = str(call.from_user.id)

    if uid in comp.get("participants", []):
        return bot.answer_callback_query(call.id, "Siz allaqachon qatnashgansiz.")

    if not check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "❗ Obuna bo'ling", show_alert=True)
        send_subscription_prompt(call.from_user.id)
        return

    comp.setdefault("participants", []).append(uid)
    competitions[comp_id] = comp
    save_json("competitions.json", competitions)
    bot.answer_callback_query(call.id, "✅ Siz tanlov ishtirokchisiga aylandingiz!")

# ---------------- Withdraw and admin flows (unchanged) ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_"))
def handle_withdraw(call):
    amount = int(call.data.split("_")[1])
    msg = bot.send_message(call.from_user.id, f"🔢 PUBG ID raqamingizni yuboring:")
    bot.register_next_step_handler(msg, confirm_withdraw, amount)

def confirm_withdraw(message, amount):
    pubg_id = message.text.strip()
    user_id = message.from_user.id
    users = load_json("users.json")

    if users.get(str(user_id), {}).get("uc", 0) < amount:
        bot.send_message(user_id, "❌ Sizda yetarli UC mavjud emas.")
        return

    users[str(user_id)]["uc"] -= amount
    save_json("users.json", users)

    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, f"📥 @{message.from_user.username if message.from_user.username else message.from_user.first_name} ({user_id})\n💸 {amount} UC so'radi.\n🔢 PUBG ID: {pubg_id}")
        except Exception as e:
            print(f"Could not notify admin {admin}: {e}")

    bot.send_message(user_id, f"✅ So'rovingiz qabul qilindi. Tez orada UC yuboriladi.")

@bot.message_handler(func=lambda m: m.text == "🔙 Ortga")
def handle_back(message):
    if message.from_user.id in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🆕 Yangi konkurs yaratish")
        markup.row("🔙 Asosiy menyu")
        bot.send_message(message.chat.id, "Admin menyusi:", reply_markup=markup)
        return
    send_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🎁 Konkurslar" and m.from_user.id in ADMIN_IDS)
def handle_competitions_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🆕 Yangi konkurs yaratish")
    markup.row("🔙 Asosiy menyu")
    bot.send_message(message.chat.id, "Admin: konkurslar boshqaruvi", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🆕 Yangi konkurs yaratish" and m.from_user.id in ADMIN_IDS)
def ask_competition_image(message):
    msg = bot.send_message(message.chat.id, "Konkurs uchun rasm yuboring:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_comp_image)

def process_comp_image(message):
    if not message.photo:
        return bot.send_message(message.chat.id, "Iltimos, rasm yuboring:")
    file_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "Konkurs tugash vaqtini yuboring (YYYY-MM-DD HH:MM):")
    bot.register_next_step_handler(msg, process_comp_deadline, file_id)

def process_comp_deadline(message, file_id):
    try:
        deadline = datetime.datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except Exception:
        return bot.send_message(message.chat.id, "Formati noto'g'ri. YYYY-MM-DD HH:MM tarzda yozing:")
    msg = bot.send_message(message.chat.id, "G'oliblar sonini kiriting:")
    bot.register_next_step_handler(msg, process_comp_winners_count, file_id, deadline)

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    ref_id = None
    parts = message.text.split()
    if len(parts) > 1:
        ref_id = parts[1]
    add_user(user_id, ref_id)
    if not check_subscription(user_id):
        send_subscription_prompt(user_id)
    else:
        send_main_menu(user_id, "🎮 Botga xush kelibsiz!")

# ---------------- Main ----------------
if __name__ == "__main__":
    try:
        init_db()
        print("Database initialized")

        # Resolve channel and group ids (attempt)
        try:
            resolve_chat_ids()
        except Exception as e:
            print(f"resolve_chat_ids failed: {e}")

        # Start competition checker loop thread
        def competition_checker_loop():
            while True:
                try:
                    check_expired_competitions()
                    time.sleep(10)  # change to 60 in production
                except Exception as e:
                    print(f"Error in competition checker: {e}")
                    time.sleep(10)

        checker_thread = threading.Thread(target=competition_checker_loop, daemon=True)
        checker_thread.start()
        print("Competition checker started")

        # Start health check server
        if FLASK_AVAILABLE:
            app = Flask(__name__)
            @app.route('/')
            def health_check():
                return "PUBG UC Bot is running", 200
            flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False))
        else:
            flask_thread = threading.Thread(target=run_server)

        flask_thread.daemon = True
        flask_thread.start()
        print("Health check server started")

        print("Starting bot polling...")
        bot.infinity_polling()

    except Exception as e:
        print(f"Bot crashed: {e}")
        for admin in ADMIN_IDS:
            try:
                bot.send_message(admin, f"Bot crashed: {e}")
            except:
                pass
