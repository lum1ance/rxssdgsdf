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

# --- Функция отправки уведомления владельцу ---
async def notify_owner(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=f"✅ {text}")
    except:
        pass

# --- Парсинг времени ---
def parse_time(time_str: str) -> int | None:
    match = re.match(r"(\d+)\s*(сек|секунд|секунду|минут|минута|минуту|час|часа|часов|день|дня|дней)", time_str.lower())
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)
    
    if "сек" in unit:
        return val
    elif "минут" in unit:
        return val * 60
    elif "час" in unit:
        return val * 3600
    elif "ден" in unit:
        return val * 86400
    return None

# --- Проверка доступа ---
def has_access(user_id: int) -> bool:
    return user_id in allowed_users

# --- Получение ID пользователя из упоминания или ответа ---
def get_target_id(update: Update) -> int | None:
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    
    text = update.message.text.strip()
    # Ищем @username
    match = re.search(r'@(\w+)', text)
    if match:
        username = match.group(1)
        # Простой способ - ищем в entities
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "mention" and entity.user:
                    return entity.user.id
        return None
    
    # Ищем ID в тексте
    match = re.search(r'\b(\d{5,})\b', text)
    if match:
        return int(match.group(1))
    
    return None

# --- Команда +бот (выдать доступ) ---
async def cmd_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        return
    
    target_id = get_target_id(update)
    
    if target_id:
        allowed_users.add(target_id)
        await update.message.reply_text(f"✅ Доступ выдан пользователю {target_id}")
        await notify_owner(context, f"Доступ выдан пользователю {target_id}")
    else:
        await update.message.reply_text("❌ Не удалось определить пользователя. Ответьте на его сообщение или укажите ID/username.")

# --- !дел и !дел N ---
async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return

    text = update.message.text.strip()
    parts = text.split()
    
    chat_id = update.effective_chat.id
    command_msg_id = update.message.message_id
    
    try:
        await context.bot.delete_message(chat_id, command_msg_id)
    except:
        pass
    
    if len(parts) == 1:
        if not update.message.reply_to_message:
            msg = await context.bot.send_message(
                chat_id=chat_id, 
                text="Команду !дел без числа нужно писать в ответ на сообщение"
            )
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except:
                pass
            return
        target_msg_id = update.message.reply_to_message.message_id
        msg_ids = [target_msg_id]
    else:
        try:
            count_to_delete = int(parts[1])
        except ValueError:
            return
        target_msg_id = command_msg_id - 1
        start_id = target_msg_id - count_to_delete + 1
        if start_id < 0:
            start_id = 0
        msg_ids = list(range(start_id, target_msg_id + 1))
    
    for i in range(0, len(msg_ids), 100):
        chunk = msg_ids[i:i+100]
        try:
            await context.bot.delete_messages(chat_id, chunk)
        except:
            for msg_id in chunk:
                try:
                    await context.bot.delete_message(chat_id, msg_id)
                except:
                    pass

# --- !пинг ---
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    start_time = datetime.now()
    msg = await update.message.reply_text("🏓 Пинг...")
    end_time = datetime.now()
    ping_ms = (end_time - start_time).total_seconds() * 1000
    await msg.edit_text(f"🏓 Понг!\n📡 Пинг: {ping_ms:.0f} мс")

# --- муты период ---
async def cmd_mute_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    # Ищем время после "муты период"
    match = re.search(r'муты период\s+(.+)', text, re.IGNORECASE)
    if not match:
        return
    
    time_str = match.group(1).strip()
    seconds = parse_time(time_str)
    
    if not seconds:
        return
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    
    if "mute_settings" not in chat_settings[chat_id]:
        chat_settings[chat_id]["mute_settings"] = {}
    
    chat_settings[chat_id]["mute_settings"]["default_duration"] = seconds
    await update.message.reply_text(f"✅ Время мута по умолчанию: {time_str}")
    await notify_owner(context, f"Время мута по умолчанию изменено на {time_str}")

# --- Мут ---
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    target_id = get_target_id(update)
    if not target_id:
        await update.message.reply_text("❌ Укажите пользователя (ответом или @username)")
        return
    
    # Парсим время и причину
    # Формат: мут [время] @user причина
    # или: мут @user причина (тогда время по умолчанию)
    
    duration = None
    reason = ""
    
    # Проверяем, указано ли время
    time_match = re.match(r'мут\s+(\d+\s*(?:сек|секунд|секунду|минут|минута|минуту|час|часа|часов|день|дня|дней))\s+', text, re.IGNORECASE)
    if time_match:
        time_str = time_match.group(1)
        duration = parse_time(time_str)
        # Убираем время и "мут" из текста для получения причины
        remaining = text[time_match.end():].strip()
        # Убираем упоминание пользователя
        remaining = re.sub(r'@\w+', '', remaining).strip()
        reason = remaining if remaining else "Без причины"
    else:
        # Время не указано, берём по умолчанию
        if chat_id in chat_settings and "mute_settings" in chat_settings[chat_id]:
            duration = chat_settings[chat_id]["mute_settings"].get("default_duration", 3600)
        else:
            duration = 3600
        
        # Убираем "мут" и упоминание, остальное - причина
        remaining = re.sub(r'^мут\s+', '', text, flags=re.IGNORECASE)
        remaining = re.sub(r'@\w+', '', remaining).strip()
        reason = remaining if remaining else "Без причины"
    
    # Применяем мут
    until_date = datetime.now() + timedelta(seconds=duration)
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions={
                "can_send_messages": False,
                "can_send_media": False,
                "can_send_other": False,
                "can_add_web_page_previews": False
            },
            until_date=until_date
        )
        
        # Форматируем время для отображения
        if duration >= 86400:
            time_display = f"{duration // 86400} дн."
        elif duration >= 3600:
            time_display = f"{duration // 3600} ч."
        elif duration >= 60:
            time_display = f"{duration // 60} мин."
        else:
            time_display = f"{duration} сек."
        
        await update.message.reply_text(
            f"🔇 Пользователь замучен на {time_display}\n"
            f"📝 Причина: {reason}"
        )
        await notify_owner(context, f"Пользователь {target_id} замучен на {time_display}. Причина: {reason}")
    except Exception as e:
        await update.message.reply_text("❌ Не удалось замутить пользователя")

# --- Анмут ---
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    target_id = get_target_id(update)
    
    if not target_id:
        await update.message.reply_text("❌ Укажите пользователя (ответом или @username)")
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions={
                "can_send_messages": True,
                "can_send_media": True,
                "can_send_other": True,
                "can_add_web_page_previews": True
            }
        )
        await update.message.reply_text("🔊 Пользователь размучен")
        await notify_owner(context, f"Пользователь {target_id} размучен")
    except Exception as e:
        await update.message.reply_text("❌ Не удалось размутить пользователя")

# --- +Правила ---
async def cmd_add_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    lines = text.split('\n', 1)
    if len(lines) < 2:
        await update.message.reply_text("❌ Напишите правила с новой строки")
        return
    
    rules_text = lines[1].strip()
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    
    chat_settings[chat_id]["rules"] = rules_text
    await update.message.reply_text("✅ Правила сохранены")
    await notify_owner(context, "Правила чата обновлены")

# --- Правила (для всех) ---
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in chat_settings or "rules" not in chat_settings[chat_id]:
        await update.message.reply_text("📋 Правила чата не установлены")
        return
    
    rules_text = chat_settings[chat_id]["rules"]
    await update.message.reply_text(f"📋 **Правила чата:**\n\n{rules_text}")

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
    
    await notify_owner(context, f"Лимит стикеров установлен: {limit}")

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
        chat_settings[chat_id] = {}
    
    if "sticker_settings" not in chat_settings[chat_id]:
        chat_settings[chat_id]["sticker_settings"] = {
            "sticker_limit": None,
            "sticker_punishment": "mute",
            "sticker_punishment_duration": 3600,
            "user_sticker_counter": {}
        }
    
    if punishment_line == "бан":
        chat_settings[chat_id]["sticker_settings"]["sticker_punishment"] = "ban"
        chat_settings[chat_id]["sticker_settings"]["sticker_punishment_duration"] = None
        await notify_owner(context, "Триггер стикеров: наказание — бан")
    elif punishment_line.startswith("мут"):
        time_match = re.search(r"мут\s+(.+)", punishment_line)
        if time_match:
            time_str = time_match.group(1).strip()
            seconds = parse_time(time_str)
            if seconds:
                chat_settings[chat_id]["sticker_settings"]["sticker_punishment"] = "mute"
                chat_settings[chat_id]["sticker_settings"]["sticker_punishment_duration"] = seconds
                await notify_owner(context, f"Триггер стикеров: наказание — мут {time_str}")

# --- Проверка стикеров ---
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in chat_settings or "sticker_settings" not in chat_settings[chat_id]:
        return
    
    settings = chat_settings[chat_id]["sticker_settings"]
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
                await notify_owner(context, f"Пользователь {user_id} забанен за {limit} стикеров подряд")
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
                await notify_owner(context, f"Пользователь {user_id} замучен за {limit} стикеров подряд")
            except:
                pass

# --- Сброс счетчика стикеров ---
async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id in chat_settings and "sticker_settings" in chat_settings[chat_id]:
        counter = chat_settings[chat_id]["sticker_settings"]["user_sticker_counter"]
        if user_id in counter:
            counter[user_id] = 0

async def post_init(application: Application):
    await application.bot.set_my_commands([])
    await application.bot.send_message(chat_id=OWNER_ID, text="✅ Бот запущен и готов к работе")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # +бот
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^\+бот'),
        cmd_grant_access
    ))
    
    # !дел
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^!дел(\s+\d+)?$'), 
        cmd_del
    ))
