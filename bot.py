import os
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- Токен берётся из переменной окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения")

OWNER_ID = 7416252489

# --- Хранилище данных ---
allowed_users = {OWNER_ID}
chat_settings = {}

# --- Парсинг времени ---
def parse_time(time_str: str) -> int | None:
    match = re.match(r"(\d+)\s*(час|часа|часов|минут|минуты|минуту|день|дня|дней)", time_str.lower())
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)
    
    if "час" in unit:
        return val * 3600
    elif "минут" in unit:
        return val * 60
    elif "ден" in unit:
        return val * 86400
    return None

# --- Проверка доступа ---
def has_access(user_id: int) -> bool:
    return user_id in allowed_users

# --- Команда +бот (выдать доступ) ---
async def cmd_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        return
    
    target_id = None
    
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    else:
        text = update.message.text.strip()
        parts = text.split()
        if len(parts) > 1:
            mention = parts[1].replace("@", "")
            if mention.isdigit():
                target_id = int(mention)
    
    if target_id:
        allowed_users.add(target_id)
        await update.message.reply_text(f"✅ Доступ выдан пользователю {target_id}")
    else:
        await update.message.reply_text("❌ Не удалось определить пользователя. Ответьте на его сообщение или укажите ID.")

# --- !дел и !дел N ---
async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("Команду нужно писать в ответ на сообщение")
        return

    text = update.message.text.strip()
    parts = text.split()
    
    count_to_delete = 1
    
    if len(parts) > 1:
        try:
            count_to_delete = int(parts[1])
        except ValueError:
            pass

    try:
        await update.message.delete()
    except:
        pass

    target_msg_id = update.message.reply_to_message.message_id
    chat_id = update.effective_chat.id

    msg_ids = list(range(target_msg_id, target_msg_id + count_to_delete))
    
    for i in range(0, len(msg_ids), 100):
        chunk = msg_ids[i:i+100]
        try:
            await context.bot.delete_messages(chat_id, chunk)
        except:
            pass

# --- -стикеры N ---
async def cmd_stickers_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) != 2:
        return
        
    try:
        limit = int(parts[1])
    except ValueError:
        return

    if chat_id not in chat_settings:
        chat_settings[chat_id] = {
            "sticker_limit": None,
            "sticker_punishment": "mute",
            "sticker_punishment_duration": 3600,
            "user_sticker_counter": {}
        }
    
    chat_settings[chat_id]["sticker_limit"] = limit
    chat_settings[chat_id]["user_sticker_counter"] = {}

# --- триггер стикеры ---
async def cmd_trigger_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    lines = text.split('\n', 1)
    if len(lines) < 2:
        return
        
    punishment_line = lines[1].strip().lower()
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {
            "sticker_limit": None,
            "sticker_punishment": "mute",
            "sticker_punishment_duration": 3600,
            "user_sticker_counter": {}
        }
    
    if punishment_line == "бан":
        chat_settings[chat_id]["sticker_punishment"] = "ban"
        chat_settings[chat_id]["sticker_punishment_duration"] = None
    elif punishment_line.startswith("мут"):
        time_match = re.search(r"мут\s+(.+)", punishment_line)
        if time_match:
            time_str = time_match.group(1).strip()
            seconds = parse_time(time_str)
            if seconds:
                chat_settings[chat_id]["sticker_punishment"] = "mute"
                chat_settings[chat_id]["sticker_punishment_duration"] = seconds

# --- Проверка стикеров ---
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in chat_settings:
        return
    
    settings = chat_settings[chat_id]
    if settings["sticker_limit"] is None:
        return
        
    limit = settings["sticker_limit"]
    counter = settings["user_sticker_counter"]
    
    if user_id not in counter:
        counter[user_id] = 0
    counter[user_id] += 1
    
    if counter[user_id] >= limit:
        counter[user_id] = 0
        
        if settings["sticker_punishment"] == "ban":
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
            except:
                pass
        elif settings["sticker_punishment"] == "mute":
            until_date = datetime.now() + timedelta(seconds=settings["sticker_punishment_duration"])
            try:
                await context.bot.restrict_chat_member(
                    chat_id, user_id,
                    permissions={
                        "can_send_messages": False,
                        "can_send_media": False,
                        "can_send_other": False,
                        "can_add_web_page_previews": False
                    },
                    until_date=until_date
                )
            except:
                pass

# --- Сброс счетчика ---
async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id in chat_settings:
        counter = chat_settings[chat_id]["user_sticker_counter"]
        if user_id in counter:
            counter[user_id] = 0

async def post_init(application: Application):
    await application.bot.set_my_commands([])

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^\+бот(\s+@?\w+|\s+\d+)?$'),
        cmd_grant_access
    ))
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^!дел(\s+\d+)?$'), 
        cmd_del
    ))
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^-стикеры\s+\d+$'), 
        cmd_stickers_limit
    ))
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^триггер стикеры'),
        cmd_trigger_stickers
    ))
    
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(~filters.Sticker.ALL & ~filters.COMMAND, handle_other))
    
    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
