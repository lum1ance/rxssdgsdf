import os
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN = "8352504575:AAGa6_2HepvJcUVGFcLHpsuCA27G1Y4615E"
OWNER_ID = 7416252489
allowed_users = {OWNER_ID}
chat_settings = {}
custom_rules_link = None
admin_log = {}

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

async def cmd_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать доступ к командам бота"""
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
    if not has_access(update.effective_user.id): return
    start = datetime.now()
    msg = await update.message.reply_text("...")
    end = datetime.now()
    await msg.edit_text(f"{(end - start).total_seconds() * 1000:.0f}ms")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать правила"""
    if custom_rules_link is None:
        await update.message.reply_text("❌ Правила не установлены")
        return
    
    await update.message.reply_text(
        f"Ознакомиться с правилами [тут]({custom_rules_link})",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_stickers_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить лимит стикеров"""
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    parts = update.message.text.strip().split()
    if len(parts) != 3: return
    try: limit = int(parts[2])
    except: return
    s = chat_settings.setdefault(chat_id, {}).setdefault("sticker_settings", {
        "sticker_limit": None, "sticker_punishment": "mute", "sticker_punishment_duration": 3600, "user_sticker_counter": {}
    })
    s["sticker_limit"] = limit
    s["user_sticker_counter"] = {}
    await update.message.reply_text(f"✅ Лимит стикеров установлен: {limit}")

async def cmd_stickers_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настроить наказание за превышение лимита стикеров"""
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    # Убираем "стикеры" из начала
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Укажите наказание: бан или мут [время]")
        return
    
    punishment = parts[1].strip()
    s = chat_settings.setdefault(chat_id, {}).setdefault("sticker_settings", {
        "sticker_limit": None, "sticker_punishment": "mute", "sticker_punishment_duration": 3600, "user_sticker_counter": {}
    })
    
    if punishment.lower() == "бан":
        s["sticker_punishment"], s["sticker_punishment_duration"] = "ban", None
        await update.message.reply_text("✅ Наказание за стикеры: бан")
    elif punishment.lower().startswith("мут"):
        m = re.search(r"мут\s+(.+)", punishment, re.IGNORECASE)
        if m:
            sec = parse_time(m.group(1))
            if sec:
                s["sticker_punishment"], s["sticker_punishment_duration"] = "mute", sec
                await update.message.reply_text(f"✅ Наказание за стикеры: мут {m.group(1)}")
            else:
                await update.message.reply_text("❌ Неверный формат времени")
        else:
            await update.message.reply_text("❌ Укажите время после 'мут'")
    else:
        await update.message.reply_text("❌ Укажите 'бан' или 'мут [время]'")

async def cmd_flood_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о флуде"""
    await update.message.reply_text(
        "Ссылка на инфо [тут](https://t.me/lunacyyflood)",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_tgadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать админку в чате с базовыми правами"""
    if update.effective_user.id != OWNER_ID: return
    chat_id = update.effective_chat.id
    target_id, target_name = None, None
    
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        target_id, target_name = u.id, u.first_name or f"@{u.username}" or str(u.id)
    elif update.message.entities:
        text = update.message.text
        for e in update.message.entities:
            if e.type == "text_mention" and e.user:
                target_id, target_name = e.user.id, e.user.first_name or f"@{e.user.username}" or str(e.user.id)
                break
            elif e.type == "mention":
                username = text[e.offset:e.offset + e.length].lstrip('@')
                target_name = username
                try:
                    target_id = (await context.bot.get_chat_member(chat_id, f"@{username}")).user.id
                except:
                    try:
                        target_id = (await context.bot.get_chat(f"@{username}")).id
                    except:
                        pass
                break
    
    if not target_id:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return
    
    if not target_name:
        target_name = str(target_id)
    
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not bot_member.can_promote_members:
            await update.message.reply_text("❌ У бота нет права назначать администраторов")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки прав бота: {str(e)[:100]}")
        return
    
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_member.status in ["administrator", "creator"]:
            await update.message.reply_text(f"ℹ️ {target_name} уже является администратором или создателем")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки пользователя: {str(e)[:100]}")
        return
    
    try:
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=False,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=True,
            can_post_messages=False,
            can_edit_messages=False,
            can_pin_messages=True,
            can_manage_topics=False,
            is_anonymous=False
        )
        
        if chat_id not in admin_log:
            admin_log[chat_id] = {}
        admin_log[chat_id][target_id] = update.effective_user.id
        
        await update.message.reply_text(f"✅ {target_name} назначен администратором")
        await context.bot.send_message(
            OWNER_ID,
            f"👑 {target_name} (ID: {target_id}) назначен админом в чате {chat_id}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось назначить админа: {str(e)[:100]}")

async def cmd_alltgadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать ВСЕ права админа (кроме анонимности)"""
    if update.effective_user.id != OWNER_ID: return
    chat_id = update.effective_chat.id
    target_id, target_name = None, None
    
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        target_id, target_name = u.id, u.first_name or f"@{u.username}" or str(u.id)
    elif update.message.entities:
        text = update.message.text
        for e in update.message.entities:
            if e.type == "text_mention" and e.user:
                target_id, target_name = e.user.id, e.user.first_name or f"@{e.user.username}" or str(e.user.id)
                break
            elif e.type == "mention":
                username = text[e.offset:e.offset + e.length].lstrip('@')
                target_name = username
                try:
                    target_id = (await context.bot.get_chat_member(chat_id, f"@{username}")).user.id
                except:
                    try:
                        target_id = (await context.bot.get_chat(f"@{username}")).id
                    except:
                        pass
                break
    
    if not target_id:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return
    
    if not target_name:
        target_name = str(target_id)
    
    try:
        # Проверяем права бота
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not bot_member.can_promote_members:
            await update.message.reply_text("❌ У бота нет права назначать администраторов")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки прав бота: {str(e)[:100]}")
        return
    
    try:
        # Проверяем, что цель не создатель
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_member.status == "creator":
            await update.message.reply_text("❌ Нельзя выдать админку создателю чата")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки пользователя: {str(e)[:100]}")
        return
    
    try:
        # Выдаём все возможные права
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=True,
            can_change_info=True,
            can_invite_users=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_pin_messages=True,
            can_manage_topics=True
        )
        
        if chat_id not in admin_log:
            admin_log[chat_id] = {}
        admin_log[chat_id][target_id] = update.effective_user.id
        
        await update.message.reply_text(f"✅ {target_name} получил все права администратора")
        await context.bot.send_message(
            OWNER_ID,
            f"👑 {target_name} (ID: {target_id}) получил ВСЕ права админа в чате {chat_id}"
        )
    except Exception as e:
        error_msg = str(e)
        if "not enough rights" in error_msg.lower() or "right_forbidden" in error_msg.lower():
            await update.message.reply_text("❌ У бота недостаточно прав для выдачи всех привилегий. Проверь, что у бота включены ВСЕ права в настройках чата.")
        else:
            await update.message.reply_text(f"❌ Не удалось выдать права: {error_msg[:100]}")

async def cmd_untgadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Снять админку в чате"""
    if update.effective_user.id != OWNER_ID: return
    chat_id = update.effective_chat.id
    target_id, target_name = None, None
    
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        target_id, target_name = u.id, u.first_name or f"@{u.username}" or str(u.id)
    elif update.message.entities:
        text = update.message.text
        for e in update.message.entities:
            if e.type == "text_mention" and e.user:
                target_id, target_name = e.user.id, e.user.first_name or f"@{e.user.username}" or str(e.user.id)
                break
            elif e.type == "mention":
                username = text[e.offset:e.offset + e.length].lstrip('@')
                target_name = username
                try:
                    target_id = (await context.bot.get_chat_member(chat_id, f"@{username}")).user.id
                except:
                    try:
                        target_id = (await context.bot.get_chat(f"@{username}")).id
                    except:
                        pass
                break
    
    if not target_id:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return
    
    if not target_name:
        target_name = str(target_id)
    
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_member.status == "creator":
            await update.message.reply_text("❌ Нельзя снять админку с создателя чата")
            return
        
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_pin_messages=False,
            can_manage_topics=False,
            is_anonymous=False
        )
        await update.message.reply_text(f"⬇️ {target_name} больше не администратор")
        await context.bot.send_message(
            OWNER_ID,
            f"⬇️ {target_name} (ID: {target_id}) снят с админки в чате {chat_id}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось снять админку: {str(e)[:100]}")

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка стикеров для анти-спам системы"""
    chat_id, user_id = update.effective_chat.id, update.effective_user.id
    s = chat_settings.get(chat_id, {}).get("sticker_settings")
    if not s or not s["sticker_limit"]: return
    c = s["user_sticker_counter"]
    c[user_id] = c.get(user_id, 0) + 1
    if c[user_id] >= s["sticker_limit"]:
        c[user_id] = 0
        try:
            u = await context.bot.get_chat_member(chat_id, user_id)
            name = u.user.first_name or f"@{u.user.username}" or str(user_id)
        except: name = str(user_id)
        if s["sticker_punishment"] == "ban":
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.send_message(chat_id, f"🚫 {name} забанен за {s['sticker_limit']} стикеров подряд")
                await context.bot.send_message(OWNER_ID, f"🚫 {name} (ID: {user_id}) забанен в чате {chat_id} за {s['sticker_limit']} стикеров")
            except: pass
        else:
            dur = s["sticker_punishment_duration"]
            until = datetime.now() + timedelta(seconds=dur)
            if dur >= 86400: td = f"{dur // 86400} дн."
            elif dur >= 3600: td = f"{dur // 3600} ч."
            elif dur >= 60: td = f"{dur // 60} мин."
            else: td = f"{dur} сек."
            try:
                await context.bot.restrict_chat_member(chat_id, user_id,
                    permissions={"can_send_messages": False, "can_send_media": False, "can_send_other": False, "can_add_web_page_previews": False},
                    until_date=until)
                await context.bot.send_message(chat_id, f"🔇 {name} замучен на {td} за {s['sticker_limit']} стикеров подряд")
                await context.bot.send_message(OWNER_ID, f"🔇 {name} (ID: {user_id}) замучен на {td} в чате {chat_id} за {s['sticker_limit']} стикеров")
            except: pass

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс счетчика стикеров при отправке других сообщений"""
    chat_id, user_id = update.effective_chat.id, update.effective_user.id
    if chat_id in chat_settings and "sticker_settings" in chat_settings[chat_id]:
        c = chat_settings[chat_id]["sticker_settings"]["user_sticker_counter"]
        if user_id in c: c[user_id] = 0

async def post_init(app: Application):
    await app.bot.set_my_commands([])
    await app.bot.send_message(OWNER_ID, "Bot started")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Команды управления доступом
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\+бот'), cmd_grant_access))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^-бот'), cmd_revoke_access))
    
    # Команды администрирования
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!дел(\s+\d+)?$'), cmd_del))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!пинг$'), cmd_ping))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!тгадмин'), cmd_tgadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!аллтг'), cmd_alltgadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!антгадмин'), cmd_untgadmin))
    
    # Команды информации
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\+правила'), cmd_set_rules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^правила$'), cmd_rules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\.флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^\.инфо флуд$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^!инфо флуд$'), cmd_flood_info))
    
    # Команды анти-стикер спама
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^стикеры спам\s+\d+$'), cmd_stickers_limit))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^стикеры\s+(бан|мут)'), cmd_stickers_punishment))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(~filters.Sticker.ALL & ~filters.COMMAND, handle_other))
    
    app.run_polling()

if __name__ == "__main__":
    main()
