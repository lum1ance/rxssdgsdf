import os
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatType

BOT_TOKEN = "8573201067:AAGvvfIyn6yA1oSFzubflhJG0BVNbU5ly0M"
OWNER_ID = 7416252489
allowed_users = {OWNER_ID}
chat_settings = {}
custom_rules_link = None

def parse_time(time_str: str) -> int | None:
    time_str = time_str.lower().strip()
    match = re.match(r"(\d+)\s*(сек|секунд|секунду|секунды)", time_str)
    if match: return int(match.group(1))
    match = re.match(r"(\d+)\s*(минут|минута|минуту|минуты)", time_str)
    if match: return int(match.group(1)) * 60
    match = re.match(r"(\d+)\s*(час|часа|часов)", time_str)
    if match: return int(match.group(1)) * 3600
    match = re.match(r"(\d+)\s*(день|дня|дней)", time_str)
    if match: return int(match.group(1)) * 86400
    return None

def has_access(user_id: int) -> bool:
    return user_id in allowed_users

def is_private_chat(update: Update) -> bool:
    """Проверяет, является ли чат личным"""
    return update.effective_chat.type == ChatType.PRIVATE

def is_owner(update: Update) -> bool:
    """Проверяет, является ли пользователь владельцем"""
    return update.effective_user.id == OWNER_ID

async def check_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, можно ли отвечать в личном чате.
    Возвращает True если ответ разрешён, False если нет.
    Если False - отправляет сообщение о запрете.
    """
    if is_private_chat(update) and not is_owner(update):
        await update.message.reply_text("❌ Бот не отвечает в личных сообщениях")
        return False
    return True

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список команд"""
    if is_private_chat(update) and not is_owner(update):
        return
    
    user_id = update.effective_user.id
    is_admin = has_access(user_id)
    is_owner_user = is_owner(update)
    
    help_text = "📋 **Список команд:**\n\n"
    
    # Публичные команды
    help_text += "🌐 **Для всех:**\n"
    help_text += "`правила` — показать правила чата\n"
    help_text += "`.флуд инфо` / `!флуд инфо` — информация о флуде\n\n"
    
    # Команды для админов (с доступом)
    if is_admin:
        help_text += "👑 **Администрирование:**\n"
        help_text += "`!дел` (реплай) — удалить одно сообщение\n"
        help_text += "`!дел 10` — удалить 10 последних сообщений\n"
        help_text += "`!пинг` — проверить задержку бота\n\n"
        
        help_text += "🛡️ **Анти-спам (стикеры/GIF):**\n"
        help_text += "`спам 5` — установить лимит стикеров/GIF\n"
        help_text += "`спам бан` — бан за превышение лимита\n"
        help_text += "`спам мут 15 минут` — мут за превышение\n\n"
    
    # Команды только для владельца
    if is_owner_user:
        help_text += "⚙️ **Владелец:**\n"
        help_text += "`+бот @user` — выдать доступ к боту\n"
        help_text += "`-бот @user` — отозвать доступ\n"
        help_text += "`+правила ссылка` — установить правила\n"
        help_text += "`+правила` — удалить правила\n\n"
    
    help_text += "`!хелп` / `.хелп` / `/хелп` — это сообщение"
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать доступ к командам бота"""
    if not await check_private_chat(update, context): return
    if update.effective_user.id != OWNER_ID: return
    target_id, target_name = None, None
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        target_id, target_name = u.id, u.first_name or f"@{u.username}" or str(u.id)
    elif update.message.entities:
        for e in update.message.entities:
            if e.type == "text_mention" and e.user:
                target_id, target_name = e.user.id, e.user.first_name or f"@{e.user.username}" or str(e.user.id)
    if target_id:
        allowed_users.add(target_id)
        await update.message.reply_text(f"✅ Доступ выдан {target_name}")
    else:
        await update.message.reply_text("❌ Не удалось определить пользователя")

async def cmd_revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отозвать доступ к командам бота"""
    if not await check_private_chat(update, context): return
    if update.effective_user.id != OWNER_ID: return
    target_id, target_name = None, None
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        target_id, target_name = u.id, u.first_name or f"@{u.username}" or str(u.id)
    elif update.message.entities:
        for e in update.message.entities:
            if e.type == "text_mention" and e.user:
                target_id, target_name = e.user.id, e.user.first_name or f"@{e.user.username}" or str(e.user.id)
                break
            elif e.type == "mention":
                username = update.message.text[e.offset:e.offset + e.length].lstrip('@')
                target_name = username
                try:
                    target_id = (await context.bot.get_chat_member(update.effective_chat.id, f"@{username}")).user.id
                except:
                    try:
                        target_id = (await context.bot.get_chat(f"@{username}")).id
                    except:
                        pass
                break
    if not target_id:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return
    if target_id == OWNER_ID:
        await update.message.reply_text("❌ Нельзя отозвать права у владельца")
        return
    if target_id in allowed_users:
        allowed_users.remove(target_id)
        await update.message.reply_text(f"❌ Права отозваны у {target_name}")
    else:
        await update.message.reply_text(f"ℹ️ У {target_name} и так нет прав")

async def cmd_set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить ссылку в команде 'правила'"""
    if not await check_private_chat(update, context): return
    if update.effective_user.id != OWNER_ID: return
    global custom_rules_link
    text = update.message.text.strip()
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        custom_rules_link = None
        await update.message.reply_text("✅ Правила удалены")
        return
    link = parts[1].strip()
    if not (link.startswith("http://") or link.startswith("https://") or link.startswith("t.me/")):
        await update.message.reply_text("❌ Укажи корректную ссылку (начинается с http://, https:// или t.me/)")
        return
    custom_rules_link = link
    await update.message.reply_text(f"✅ Правила установлены:\n{link}")

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить сообщения"""
    if not await check_private_chat(update, context): return
    if not has_access(update.effective_user.id): return
    text, chat_id, cmd_id = update.message.text.strip(), update.effective_chat.id, update.message.message_id
    parts = text.split()
    try: await context.bot.delete_message(chat_id, cmd_id)
    except: pass
    if len(parts) == 1:
        if not update.message.reply_to_message:
            msg = await context.bot.send_message(chat_id, "Ответь на сообщение")
            await asyncio.sleep(3)
            try: await msg.delete()
            except: pass
            return
        try: await context.bot.delete_message(chat_id, update.message.reply_to_message.message_id)
        except: pass
        return
    try: count = int(parts[1])
    except: return
    deleted, current_id = 0, cmd_id - 1
    while deleted < count and current_id > 0:
        try:
            await context.bot.delete_message(chat_id, current_id)
            deleted += 1
        except: pass
        current_id -= 1
        await asyncio.sleep(0.05)

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить задержку бота"""
    if not await check_private_chat(update, context): return
    if not has_access(update.effective_user.id): return
    start = datetime.now()
    msg = await update.message.reply_text("...")
    end = datetime.now()
    await msg.edit_text(f"{(end - start).total_seconds() * 1000:.0f}ms")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать правила"""
    if not await check_private_chat(update, context): return
    if custom_rules_link is None:
        await update.message.reply_text("❌ Правила не установлены")
        return
    
    await update.message.reply_text(
        f"Ознакомиться с правилами [тут]({custom_rules_link})",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_spam_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить лимит стикеров/GIF"""
    if not await check_private_chat(update, context): return
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    parts = update.message.text.strip().split()
    if len(parts) != 2: return
    try: limit = int(parts[1])
    except: return
    s = chat_settings.setdefault(chat_id, {}).setdefault("spam_settings", {
        "spam_limit": None, 
        "spam_punishment": "mute", 
        "spam_punishment_duration": 3600, 
        "spam_counter": 0,
        "last_spam_user": None
    })
    s["spam_limit"] = limit
    s["spam_counter"] = 0
    s["last_spam_user"] = None
    await update.message.reply_text(f"✅ Лимит стикеров/GIF установлен: {limit}")

async def cmd_spam_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настроить наказание за превышение лимита"""
    if not await check_private_chat(update, context): return
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Укажите наказание: бан или мут [время]")
        return
    
    punishment = parts[1].strip()
    s = chat_settings.setdefault(chat_id, {}).setdefault("spam_settings", {
        "spam_limit": None, 
        "spam_punishment": "mute", 
        "spam_punishment_duration": 3600, 
        "spam_counter": 0,
        "last_spam_user": None
    })
    
    if punishment.lower() == "бан":
        s["spam_punishment"], s["spam_punishment_duration"] = "ban", None
        await update.message.reply_text("✅ Наказание за спам: бан")
    elif punishment.lower().startswith("мут"):
        m = re.search(r"мут\s+(.+)", punishment, re.IGNORECASE)
        if m:
            sec = parse_time(m.group(1))
            if sec:
                s["spam_punishment"], s["spam_punishment_duration"] = "mute", sec
                await update.message.reply_text(f"✅ Наказание за спам: мут {m.group(1)}")
            else:
                await update.message.reply_text("❌ Неверный формат времени")
        else:
            await update.message.reply_text("❌ Укажите время после 'мут'")
    else:
        await update.message.reply_text("❌ Укажите 'бан' или 'мут [время]'")

async def cmd_flood_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о флуде"""
    if not await check_private_chat(update, context): return
    await update.message.reply_text(
        "Ссылка на инфо [тут](https://t.me/lunacyyflood)",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def handle_spam_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка стикеров и GIF для анти-спам системы"""
    if not await check_private_chat(update, context): return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    s = chat_settings.get(chat_id, {}).get("spam_settings")
    
    if not s or not s["spam_limit"]:
        return
    
    # Увеличиваем общий счётчик
    s["spam_counter"] = s.get("spam_counter", 0) + 1
    
    # Сохраняем ID последнего отправителя
    s["last_spam_user"] = user_id
    
    # Проверяем, не превышен ли лимит
    if s["spam_counter"] >= s["spam_limit"]:
        # Сбрасываем счётчик
        s["spam_counter"] = 0
        target_user = s["last_spam_user"]
        s["last_spam_user"] = None
        
        try:
            u = await context.bot.get_chat_member(chat_id, target_user)
            name = u.user.first_name or f"@{u.user.username}" or str(target_user)
        except:
            name = str(target_user)
        
        if s["spam_punishment"] == "ban":
            try:
                await context.bot.ban_chat_member(chat_id, target_user)
                await context.bot.send_message(
                    chat_id, 
                    f"🚫 {name} забанен за спам стикерами/GIF!"
                )
                await context.bot.send_message(
                    OWNER_ID,
                    f"🚫 {name} (ID: {target_user}) забанен в чате {chat_id} за спам стикерами/GIF"
                )
            except Exception as e:
                await context.bot.send_message(
                    OWNER_ID,
                    f"❌ Не удалось забанить {name}: {str(e)[:100]}"
                )
        else:
            dur = s["spam_punishment_duration"]
            until = datetime.now() + timedelta(seconds=dur)
            if dur >= 86400:
                td = f"{dur // 86400} дн."
            elif dur >= 3600:
                td = f"{dur // 3600} ч."
            elif dur >= 60:
                td = f"{dur // 60} мин."
            else:
                td = f"{dur} сек."
            
            try:
                await context.bot.restrict_chat_member(
                    chat_id, 
                    target_user,
                    permissions={
                        "can_send_messages": False,
                        "can_send_media": False,
                        "can_send_other": False,
                        "can_add_web_page_previews": False
                    },
                    until_date=until
                )
                await context.bot.send_message(
                    chat_id,
                    f"🔇 {name} замучен на {td} за спам стикерами/GIF!"
                )
                await context.bot.send_message(
                    OWNER_ID,
                    f"🔇 {name} (ID: {target_user}) замучен на {td} в чате {chat_id} за спам стикерами/GIF"
                )
            except Exception as e:
                await context.bot.send_message(
                    OWNER_ID,
                    f"❌ Не удалось замутить {name}: {str(e)[:100]}"
                )

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс счетчика при отправке других сообщений"""
    if not await check_private_chat(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in chat_settings and "spam_settings" in chat_settings[chat_id]:
        s = chat_settings[chat_id]["spam_settings"]
        # Сбрасываем счётчик при любом НЕ стикере и НЕ GIF
        s["spam_counter"] = 0
        s["last_spam_user"] = None

async def post_init(app: Application):
    await app.bot.set_my_commands([])
    await app.bot.send_message(OWNER_ID, "Bot started")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Команда хелп
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^[!./]хелп$'), cmd_help))
    
    # Команды управления доступом
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\+бот'), cmd_grant_access))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^-бот'), cmd_revoke_access))
    
    # Команды администрирования
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!дел(\s+\d+)?$'), cmd_del))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!пинг$'), cmd_ping))
    
    # Команды информации
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\+правила'), cmd_set_rules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^правила$'), cmd_rules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\.флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\.инфо флуд$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!инфо флуд$'), cmd_flood_info))
    
    # Команды анти-спама
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^спам\s+\d+$'), cmd_spam_limit))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^спам\s+(бан|мут)'), cmd_spam_punishment))
    
    # Обработчики стикеров и GIF
    app.add_handler(MessageHandler(filters.Sticker.ALL | filters.ANIMATION, handle_spam_content))
    
    # Обработчик остальных сообщений (сброс счётчика)
    app.add_handler(MessageHandler(~filters.Sticker.ALL & ~filters.ANIMATION & ~filters.COMMAND, handle_other))
    
    app.run_polling()

if __name__ == "__main__":
    main()
