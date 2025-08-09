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

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = "@mypubgbot_test"
GROUP_ID = "@mypubg_test"
YOUTUBE_LINK = "https://youtube.com/@swkombat?si=5vVIGfj_NYx-yJLK"
ADMIN_IDS = [6322816106,1401881769,6072785933]
DB_NAME = "bot.db"

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE INIT ---
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

# --- JSON FILES HANDLING ---
def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize JSON files if they don't exist
for file in ["users.json", "competitions.json", "devices.json"]:
    if not os.path.exists(file):
        save_json(file, {})

def send_main_menu(user_id, text="Asosiy menyu:"):
    """Send appropriate menu based on user role"""
    markup = main_menu(user_id)
    bot.send_message(user_id, text, reply_markup=markup)

def main_menu(user_id):
    """Generate menu based on user role"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Common buttons for all users
    buttons = [
        "📨 Referal havola",
        "📊 Referal reyting",
        "💰 UC balans",
        "💸 UC yechish"
    ]

    # Add admin-only button if user is admin
    if user_id in ADMIN_IDS:
        buttons.insert(3, "🎁 Konkurslar")  # Insert at position 3

    # Add buttons in rows
    # If there are at least 4 buttons, show two rows
    if len(buttons) >= 4:
        markup.row(buttons[0], buttons[1])  # First row
        markup.row(buttons[2], buttons[3])  # Second row
    else:
        # fallback layout
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.row(*row)

    # Add third row only if needed (admin)
    if len(buttons) > 4:
        markup.row(buttons[4])  # Third row for admin

    return markup

# --- SUBSCRIPTION CHECK ---
def check_subscription(user_id):
    try:
        channel = bot.get_chat_member(CHANNEL_ID, user_id)
        group = bot.get_chat_member(GROUP_ID, user_id)
        return channel.status in ["member", "administrator", "creator"] and group.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Subscription check error: {e}")
        return False

def send_subscription_prompt(user_id):
    markup = types.InlineKeyboardMarkup()
    # Use direct t.me links built from usernames (strip @)
    channel_username = CHANNEL_ID[1:] if CHANNEL_ID.startswith("@") else CHANNEL_ID
    group_username = GROUP_ID[1:] if GROUP_ID.startswith("@") else GROUP_ID
    markup.add(types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{channel_username}"))
    markup.add(types.InlineKeyboardButton("👥 Guruhga obuna bo'lish", url=f"https://t.me/{group_username}"))
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

# --- REFERRAL SYSTEM ---
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

# --- REFERRAL LINK ---
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

# --- UC BALANCE ---
@bot.message_handler(func=lambda msg: msg.text == "💰 UC balans")
def send_uc(message):
    users = load_json("users.json")
    uc = users.get(str(message.from_user.id), {}).get("uc", 0)
    bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {uc} UC")

# --- REFERRAL RATING SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "📊 Referal reyting")
def handle_referral_rating(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🔄 Oxirgi 7 kun", "📅 Boshqa davr")
    markup.add("🔙 Ortga")
    bot.send_message(
        message.chat.id,
        "Referal reyting uchun davrni tanlang:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🔄 Oxirgi 7 kun")
def last_7_days_rating(message):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=7)
    show_referral_rating(message.chat.id, start_date, end_date)

@bot.message_handler(func=lambda m: m.text == "📅 Boshqa davr")
def ask_custom_dates(message):
    msg = bot.send_message(
        message.chat.id,
        "Boshlanish sanasini yuboring (YYYY-MM-DD):\nMasalan: 2023-12-01"
    )
    bot.register_next_step_handler(msg, process_start_date)

def process_start_date(message):
    if message.text == "🔙 Ortga":
        return send_main_menu(message.chat.id)

    try:
        start_date = datetime.datetime.strptime(message.text, "%Y-%m-%d").date()
        msg = bot.send_message(
            message.chat.id,
            "Tugash sanasini yuboring (YYYY-MM-DD):\nMasalan: 2023-12-31"
        )
        bot.register_next_step_handler(msg, process_end_date, start_date)
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Noto'g'ri format. Iltimos quyidagi formatda yuboring: YYYY-MM-DD"
        )
        ask_custom_dates(message)

def process_end_date(message, start_date):
    if message.text == "🔙 Ortga":
        return send_main_menu(message.chat.id)

    try:
        end_date = datetime.datetime.strptime(message.text, "%Y-%m-%d").date()
        if end_date < start_date:
            bot.send_message(
                message.chat.id,
                "❌ Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas."
            )
            ask_custom_dates(message)
        else:
            show_referral_rating(message.chat.id, start_date, end_date)
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Noto'g'ri format. Iltimos quyidagi formatda yuboring: YYYY-MM-DD"
        )
        ask_custom_dates(message)

def show_referral_rating(chat_id, start_date, end_date):
    users = load_json("users.json")
    rating = []

    for user_id, user_data in users.items():
        try:
            join_date = datetime.datetime.strptime(
                user_data.get("joined", "2000-01-01"),
                "%Y-%m-%d"
            ).date()

            if start_date <= join_date <= end_date:
                ref_count = len(user_data.get("refs", []))
                uc_balance = user_data.get("uc", 0)
                rating.append((int(user_id), ref_count, uc_balance))
        except Exception as e:
            print(f"Error processing user {user_id}: {e}")

    if not rating:
        bot.send_message(
            chat_id,
            f"⚠️ {start_date} dan {end_date} gacha bo'lgan davrda hech qanday referal topilmadi."
        )
        return

    rating.sort(key=lambda x: x[1], reverse=True)

    # Build message without Markdown formatting
    message = f"🏆 Referal reyting ({start_date} - {end_date}):\n\n"
    message += "┌──────────┬──────────────────────┬──────────┬───────┐\n"
    message += "│ Reyting  │ Foydalanuvchi        │ Do'stlar │ UC    │\n"
    message += "├──────────┼──────────────────────┼──────────┼───────┤\n"

    for idx, (user_id, ref_count, uc_balance) in enumerate(rating[:10], 1):
        try:
            user_chat = bot.get_chat(user_id)
            username = f"@{user_chat.username}" if user_chat.username else f"ID:{user_id}"
        except:
            username = f"ID:{user_id}"

        # Remove any Markdown special characters
        username = username.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

        message += f"│ #{idx:<7} │ {username[:20]:<20} │ {ref_count:<7} │ {uc_balance:<5} │\n"

    message += "└──────────┴──────────────────────┴─────────┴───────┘\n\n"
    message += f"📊 Jami referallar: {sum([x[1] for x in rating])}"

    # Send as plain text without Markdown
    try:
        bot.send_message(chat_id, message)
    except Exception as e:
        print(f"Failed to send rating message: {e}")
        # Fallback to simpler message if still failing
        try:
            simple_lines = []
            for idx, (user_id, ref_count, uc_balance) in enumerate(rating[:10], 1):
                try:
                    user_chat = bot.get_chat(user_id)
                    uname = f"@{user_chat.username}" if user_chat.username else f"ID:{user_id}"
                except:
                    uname = f"ID:{user_id}"
                simple_lines.append(f"{idx}. {uname}: {ref_count} do'st - {uc_balance} UC")
            bot.send_message(chat_id, f"Referal reyting ({start_date} - {end_date}):\n" + "\n".join(simple_lines))
        except Exception as e2:
            print(f"Fallback failed: {e2}")

# --- COMPETITIONS HELPER FUNCTIONS ---
def check_expired_competitions():
    competitions = load_json("competitions.json")
    now = datetime.datetime.now()
    for comp_id, comp in list(competitions.items()):
        try:
            # load deadline; if missing/invalid skip
            dl_str = comp.get("deadline")
            if not dl_str:
                continue
            # fromisoformat expects same format we saved (YYYY-MM-DDTHH:MM:SS)
            try:
                deadline = datetime.datetime.fromisoformat(dl_str)
            except Exception:
                # Try parsing as fallback
                deadline = datetime.datetime.strptime(dl_str, "%Y-%m-%d %H:%M:%S")
            if now >= deadline and not comp.get("winners_announced", False):
                finish_competition(comp_id)
        except Exception as e:
            print(f"Error processing competition {comp_id}: {e}")

def finish_competition(comp_id):
    """
    Finalize competition: choose winners, announce in GROUP and CHANNEL,
    notify winners privately and admins, and save state regardless of errors.
    """
    competitions = load_json("competitions.json")
    comp = competitions.get(comp_id)
    if not comp:
        print(f"finish_competition: competition {comp_id} not found")
        return

    if comp.get("winners_announced"):
        print(f"finish_competition: competition {comp_id} already processed")
        return

    participants = comp.get("participants", []) or []
    winners_count = comp.get("winners", 1)

    # If no participants: announce no participants and mark as announced
    if not participants:
        announcement = f"⚠️ #{comp_id} konkursi yakunlandi. Ishtirokchilar bo'lmadi."
        try:
            bot.send_message(GROUP_ID, announcement)
            bot.send_message(CHANNEL_ID, announcement)
        except Exception as e:
            print(f"Error announcing no participants for comp {comp_id}: {e}")
        # mark completed and save
        comp["winners_announced"] = True
        competitions[comp_id] = comp
        save_json("competitions.json", competitions)
        return

    # choose winners safely
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

    # Build mentions list (prefer @username if available)
    winner_mentions = []
    for winner_id in winners:
        try:
            uid_int = int(winner_id)
        except:
            # store as str fallback
            uid_int = None

        mention = None
        if uid_int:
            try:
                user = bot.get_chat(uid_int)
                if getattr(user, "username", None):
                    mention = f"@{user.username}"
                else:
                    # Use display name without special characters
                    name = getattr(user, "first_name", "") or "User"
                    name = name.replace("\n", " ").strip()
                    mention = f"{name} (ID:{uid_int})"
            except Exception as e:
                print(f"Could not get chat for winner {winner_id}: {e}")
                mention = f"ID:{winner_id}"
        else:
            mention = f"ID:{winner_id}"

        winner_mentions.append(mention)

    # Announcement text (plain text)
    winners_text = "\n".join([f"🏆 {i+1}. {w}" for i, w in enumerate(winner_mentions)])
    announcement = (
        f"🎊 Konkurs #{comp_id} yakunlandi! 🎊\n\n"
        f"G'oliblar ({len(winners)} ta):\n{winners_text}\n\n"
        "Tabriklaymiz! 🎉 Adminlar tez orada siz bilan bog'lanishadi."
    )

    # Try to send announcement to group and channel; catch and log errors
    send_errors = []
    try:
        bot.send_message(GROUP_ID, announcement)
    except Exception as e:
        send_errors.append(f"group:{e}")
        print(f"Error sending announcement to group for comp {comp_id}: {e}")

    try:
        bot.send_message(CHANNEL_ID, announcement)
    except Exception as e:
        send_errors.append(f"channel:{e}")
        print(f"Error sending announcement to channel for comp {comp_id}: {e}")

    # Notify winners privately (best-effort)
    for winner_id in winners:
        try:
            uid_int = int(winner_id)
            try:
                bot.send_message(uid_int,
                    f"🎉 Tabriklaymiz! Siz #{comp_id} konkursining g'oliblaridan bo'ldingiz!\n\nAdminlar tez orada bog'lanadi.")
            except Exception as e:
                print(f"Could not send private message to winner {winner_id}: {e}")
        except Exception as e:
            print(f"Invalid winner id {winner_id}: {e}")

    # Mark competition as finished and save winners even if sending had problems
    comp["winners"] = winners
    comp["winners_announced"] = True
    competitions[comp_id] = comp
    save_json("competitions.json", competitions)

    # Notify admins with plain text (best-effort)
    admins_msg = f"🏆 #{comp_id} konkurs yakunlandi. G'oliblar:\n" + "\n".join([f"- {w}" for w in winner_mentions])
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, admins_msg)
        except Exception as e:
            print(f"Could not notify admin {admin_id}: {e}")

    # If there were send errors, log them
    if send_errors:
        print(f"finish_competition {comp_id} had send errors: {send_errors}")

# --- COMPETITION CREATION FLOW ---
def process_comp_winners_count(message, file_id, deadline):
    try:
        winners = int(message.text)
        if winners <= 0:
            raise ValueError

        competitions = load_json("competitions.json")
        comp_id = str(len(competitions) + 1)

        # Store deadline as ISO format
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

    try:
        bot.send_photo(CHANNEL_ID, comp["file_id"], caption, reply_markup=keyboard)
        bot.send_photo(GROUP_ID, comp["file_id"], caption, reply_markup=keyboard)
    except Exception as e:
        print(f"Error posting competition {comp_id}: {e}")

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

# --- UC WITHDRAWAL ---
@bot.message_handler(func=lambda msg: msg.text == "💸 UC yechish")
def request_uc_withdraw(message):
    users = load_json("users.json")
    uc = users.get(str(message.from_user.id), {}).get("uc", 0)
    if uc < 60:
        bot.send_message(message.chat.id, "❌ UC yechish uchun kamida 60 UC kerak.")
        return

    markup = types.InlineKeyboardMarkup()
    for amount in [60, 120, 180, 325]:
        if uc >= amount:
            markup.add(types.InlineKeyboardButton(f"{amount} UC", callback_data=f"withdraw_{amount}"))
    bot.send_message(message.chat.id, "💳 Yechmoqchi bo'lgan UC miqdorini tanlang:", reply_markup=markup)

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
    """Handle back button for all users"""
    if message.from_user.id in ADMIN_IDS:
        # For admin, show admin menu if coming from admin section
        # The original code attempted to check incoming context on message object;
        # We'll just show the admin menu here
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🆕 Yangi konkurs yaratish")
        markup.row("🔙 Asosiy menyu")
        bot.send_message(message.chat.id, "Admin menyusi:", reply_markup=markup)
        return
    # For all users, return to main menu
    send_main_menu(message.chat.id)

# --- COMPETITIONS ADMIN FLOWS ---
@bot.message_handler(func=lambda m: m.text == "🎁 Konkurslar" and m.from_user.id in ADMIN_IDS)
def handle_competitions_menu(message):
    """Admin-only competitions menu"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🆕 Yangi konkurs yaratish")
    markup.row("🔙 Asosiy menyu")
    bot.send_message(
        message.chat.id,
        "Admin: konkurslar boshqaruvi",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🆕 Yangi konkurs yaratish" and m.from_user.id in ADMIN_IDS)
def ask_competition_image(message):
    """Start competition creation process"""
    msg = bot.send_message(
        message.chat.id,
        "Konkurs uchun rasm yuboring:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_comp_image)

@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu" and m.from_user.id in ADMIN_IDS)
def admin_back_to_main(message):
    """Special back button for admin menu"""
    send_main_menu(message.chat.id)

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

# --- JOIN CALLBACK handled above ---

# --- START COMMAND ---
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

if __name__ == "__main__":
    try:
        init_db()
        print("Database initialized")

        # Start competition checker thread
        checker_thread = threading.Thread(target=lambda: (time.sleep(0), [check_expired_competitions(), time.sleep(0)][0]), daemon=True)
        # The above lambda is replaced immediately below by a proper loop thread - keep for compatibility then start proper thread:
        def competition_checker_loop():
            while True:
                try:
                    check_expired_competitions()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    print(f"Error in competition checker: {e}")
                    time.sleep(60)  # Wait before retrying

        checker_thread = threading.Thread(target=competition_checker_loop)
        checker_thread.daemon = True
        checker_thread.start()
        print("Competition checker started")

        # Start health check server
        if FLASK_AVAILABLE:
            app = Flask(__name__)
            @app.route('/')
            def health_check():
                return "PUBG UC Bot is running", 200

            flask_thread = threading.Thread(target=lambda: app.run(
                host='0.0.0.0',
                port=int(os.environ.get("PORT", 10000)),
                debug=False,
                use_reloader=False
            ))
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
