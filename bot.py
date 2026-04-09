import os
import asyncio
import re
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# --- Токен из переменной окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

OWNER_ID = 7416252489

# --- Хранилище ---
allowed_users = {OWNER_ID}
chat_settings = {}

# --- HTTP сервер для Railway ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.getenv('PORT', 8080))
    HTTPServer(('0.0.0.0', port), DummyHandler).serve_forever()

# --- Парсинг времени ---
def parse_time(time_str: str) -> int | None:
    time_str = time_str.lower().strip()
    
    match = re.match(r"(\d+)\s*(сек|секунд|секунду|секунды)", time_str)
    if match:
        return int(match.group(1))
    
    match = re.match(r"(\d+)\s*(минут|минута|минуту|минуты)", time_str)
    if match:
        return int(match.group(1)) * 60
    
    match = re.match(r"(\d+)\s*(час|часа|часов)", time_str)
    if match:
        return int(match.group(1)) * 3600
    
    match = re.match(r"(\d+)\s*(день|дня|дней)", time_str)
    if match:
        return int(match.group(1)) * 86400
    
    return None

# --- Проверка доступа ---
def has_access(user_id: int) -> bool:
    return user_id in allowed_users

# --- +бот ---
async def cmd_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    target_id = None
    target_name = None
    
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        target_id = user.id
        target_name = user.first_name or f"@{user.username}" or str(user.id)
    elif update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention" and entity.user:
                target_id = entity.user.id
                target_name = entity.user.first_name or f"@{entity.user.username}" or str(target_id)
    
    if target_id:
        allowed_users.add(target_id)
        await update.message.reply_text(f"✅ Доступ выдан {target_name}")
    else:
        await update.message.reply_text("❌ Не удалось определить пользователя")

# --- !дел ---
async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return

    text = update.message.text.strip()
    parts = text.split()
    chat_id = update.effective_chat.id
    cmd_id = update.message.message_id
    
    try:
        await context.bot.delete_message(chat_id, cmd_id)
    except:
        pass
    
    if len(parts) == 1:
        if not update.message.reply_to_message:
            msg = await context.bot.send_message(chat_id, "Ответь на сообщение")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except:
                pass
            return
        msg_ids = [update.message.reply_to_message.message_id]
    else:
        try:
            count = int(parts[1])
        except:
            return
        start_id = cmd_id - count
        if start_id < 0:
            start_id = 0
        msg_ids = list(range(start_id, cmd_id))
    
    for i in range(0, len(msg_ids), 100):
        chunk = msg_ids[i:i+100]
        try:
            await context.bot.delete_messages(chat_id, chunk)
        except:
            for mid in chunk:
                try:
                    await context.bot.delete_message(chat_id, mid)
                except:
                    pass

# --- !пинг ---
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    start = datetime.now()
    msg = await update.message.reply_text("...")
    end = datetime.now()
    ping_ms = (end - start).total_seconds() * 1000
    await msg.edit_text(f"{ping_ms:.0f}ms")

# --- муты период ---
async def cmd_mute_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    match = re.search(r'муты период\s+(.+)', text, re.IGNORECASE)
    if not match:
        return
    
    seconds = parse_time(match.group(1))
    if not seconds:
        return
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    if "mute_settings" not in chat_settings[chat_id]:
        chat_settings[chat_id]["mute_settings"] = {}
    
    chat_settings[chat_id]["mute_settings"]["default_duration"] = seconds
    await update.message.reply_text(f"✅ Период мута по умолчанию: {match.group(1)}")

# --- мут ---
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    target_id = None
    target_name = None
    
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        target_id = user.id
        target_name = user.first_name or f"@{user.username}" or str(user.id)
    else:
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "text_mention" and entity.user:
                    target_id = entity.user.id
                    target_name = entity.user.first_name or f"@{entity.user.username}" or str(target_id)
                    break
                elif entity.type == "mention":
                    username = text[entity.offset:entity.offset + entity.length].lstrip('@')
                    target_name = username
                    try:
                        member = await context.bot.get_chat_member(chat_id, f"@{username}")
                        target_id = member.user.id
                    except:
                        try:
                            chat = await context.bot.get_chat(f"@{username}")
                            target_id = chat.id
                        except:
                            pass
                    break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не указан или бот его не видит")
        return
    
    if not target_name:
        target_name = str(target_id)
    
    duration = None
    
    time_match = re.match(r'мут\s+(\d+\s*(?:сек|секунд|минут|минута|минуту|час|часа|часов|день|дня|дней))\s+', text, re.IGNORECASE)
    if time_match:
        duration = parse_time(time_match.group(1))
    else:
        if chat_id in chat_settings and "mute_settings" in chat_settings[chat_id]:
            duration = chat_settings[chat_id]["mute_settings"].get("default_duration", 3600)
        else:
            duration = 3600
    
    if duration >= 86400:
        time_display = f"{duration // 86400} дн."
    elif duration >= 3600:
        time_display = f"{duration // 3600} ч."
    elif duration >= 60:
        time_display = f"{duration // 60} мин."
    else:
        time_display = f"{duration} сек."
    
    until_date = datetime.now() + timedelta(seconds=duration)
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions={"can_send_messages": False, "can_send_media": False,
                        "can_send_other": False, "can_add_web_page_previews": False},
            until_date=until_date
        )
        await update.message.reply_text(f"🔇 {target_name} был замучен на {time_display}")
    except:
        await update.message.reply_text(f"❌ Не удалось замутить {target_name}")

# --- анмут ---
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    target_id = None
    target_name = None
    
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        target_id = user.id
        target_name = user.first_name or f"@{user.username}" or str(user.id)
    else:
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "text_mention" and entity.user:
                    target_id = entity.user.id
                    target_name = entity.user.first_name or f"@{entity.user.username}" or str(target_id)
                    break
                elif entity.type == "mention":
                    username = text[entity.offset:entity.offset + entity.length].lstrip('@')
                    target_name = username
                    try:
                        member = await context.bot.get_chat_member(chat_id, f"@{username}")
                        target_id = member.user.id
                    except:
                        try:
                            chat = await context.bot.get_chat(f"@{username}")
                            target_id = chat.id
                        except:
                            pass
                    break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не указан или бот его не видит")
        return
    
    if not target_name:
        target_name = str(target_id)
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions={"can_send_messages": True, "can_send_media": True,
                        "can_send_other": True, "can_add_web_page_previews": True}
        )
        await update.message.reply_text(f"🔊 {target_name} размучен")
    except:
        await update.message.reply_text(f"❌ Не удалось размутить {target_name}")

# --- +правила ---
async def cmd_add_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text
    
    lines = text.split('\n', 1)
    if len(lines) < 2:
        await update.message.reply_text("❌ Напишите правила с новой строки")
        return
    
    rules_text = lines[1].strip()
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    
    chat_settings[chat_id]["rules"] = rules_text
    await update.message.reply_text("✅ Правила сохранены")

# --- правила ---
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in chat_settings or "rules" not in chat_settings[chat_id]:
        await update.message.reply_text("📋 Правила не установлены")
        return
    
    rules_text = chat_settings[chat_id]["rules"]
    await update.message.reply_text(
        f"📋 **Правила чата:**\n\n{rules_text}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False
    )

# --- -стикеры ---
async def cmd_stickers_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    parts = update.message.text.strip().split()
    
    if len(parts) != 2:
        return
    
    try:
        limit = int(parts[1])
    except:
        return
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    if "sticker_settings" not in chat_settings[chat_id]:
        chat_settings[chat_id]["sticker_settings"] = {
            "sticker_limit": None,
            "sticker_punishment": "mute",
            "sticker_punishment_duration": 3600,
            "user_sticker_counter": {}
        }
    
    chat_settings[chat_id]["sticker_settings"]["sticker_limit"] = limit
    chat_settings[chat_id]["sticker_settings"]["user_sticker_counter"] = {}

# --- триггер стикеры ---
async def cmd_trigger_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    lines = text.split('\n', 1)
    if len(lines) < 2:
        return
    
    punishment = lines[1].strip()
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    if "sticker_settings" not in chat_settings[chat_id]:
        chat_settings[chat_id]["sticker_settings"] = {
            "sticker_limit": None,
            "sticker_punishment": "mute",
            "sticker_punishment_duration": 3600,
            "user_sticker_counter": {}
        }
    
    if punishment.lower() == "бан":
        chat_settings[chat_id]["sticker_settings"]["sticker_punishment"] = "ban"
        chat_settings[chat_id]["sticker_settings"]["sticker_punishment_duration"] = None
        await update.message.reply_text("✅ Триггер стикеров: бан")
    elif punishment.lower().startswith("мут"):
        time_match = re.search(r"мут\s+(.+)", punishment, re.IGNORECASE)
        if time_match:
            time_str = time_match.group(1).strip()
            seconds = parse_time(time_str)
            if seconds:
                chat_settings[chat_id]["sticker_settings"]["sticker_punishment"] = "mute"
                chat_settings[chat_id]["sticker_settings"]["sticker_punishment_duration"] = seconds
                await update.message.reply_text(f"✅ Триггер стикеров: мут {time_str}")
            else:
                await update.message.reply_text("❌ Неверный формат времени")
        else:
            await update.message.reply_text("❌ Укажите время после 'мут'")
    else:
        await update.message.reply_text("❌ Укажите 'бан' или 'мут [время]'")

# --- Обработка стикеров ---
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in chat_settings or "sticker_settings" not in chat_settings[chat_id]:
        return
    
    s = chat_settings[chat_id]["sticker_settings"]
    if s["sticker_limit"] is None:
        return
    
    counter = s["user_sticker_counter"]
    counter[user_id] = counter.get(user_id, 0) + 1
    
    if counter[user_id] >= s["sticker_limit"]:
        counter[user_id] = 0
        
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            user_name = user.user.first_name or f"@{user.user.username}" or str(user_id)
        except:
            user_name = str(user_id)
        
        if s["sticker_punishment"] == "ban":
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚫 {user_name} забанен за {s['sticker_limit']} стикеров подряд"
                )
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🚫 {user_name} (ID: {user_id}) забанен в чате {chat_id} за {s['sticker_limit']} стикеров"
                )
            except:
                pass
        else:
            duration = s["sticker_punishment_duration"]
            until = datetime.now() + timedelta(seconds=duration)
            
            if duration >= 86400:
                time_display = f"{duration // 86400} дн."
            elif duration >= 3600:
                time_display = f"{duration // 3600} ч."
            elif duration >= 60:
                time_display = f"{duration // 60} мин."
            else:
                time_display = f"{duration} сек."
            
            try:
                await context.bot.restrict_chat_member(
                    chat_id, user_id,
                    permissions={"can_send_messages": False, "can_send_media": False,
                                "can_send_other": False, "can_add_web_page_previews": False},
                    until_date=until
                )
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔇 {user_name} замучен на {time_display} за {s['sticker_limit']} стикеров подряд"
                )
                await context.bot.send_message(
                    chat_id=
