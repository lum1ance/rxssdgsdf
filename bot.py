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

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id): return
    
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    cmd_id = update.message.message_id
    parts = text.split()
    
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
        
        try:
            await context.bot.delete_message(chat_id, update.message.reply_to_message.message_id)
        except:
            pass
        return
    
    try:
        count = int(parts[1])
    except:
        return
    
    deleted = 0
    current_id = cmd_id - 1
    
    while deleted < count and current_id > 0:
        try:
            await context.bot.delete_message(chat_id, current_id)
            deleted += 1
        except:
            pass
        current_id -= 1
        await asyncio.sleep(0.05)

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id): return
    start = datetime.now()
    msg = await update.message.reply_text("...")
    end = datetime.now()
    await msg.edit_text(f"{(end - start).total_seconds() * 1000:.0f}ms")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id): return
    chat_id, text = update.effective_chat.id, update.message.text.strip()
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
                username = text[e.offset:e.offset + e.length].lstrip('@')
                target_name = username
                try:
                    member = await context.bot.get_chat_member(chat_id, f"@{username}")
                    target_id = member.user.id
                except:
                    try: target_id = (await context.bot.get_chat(f"@{username}")).id
                    except: pass
                break
    if not target_id:
        await update.message.reply_text("❌ Пользователь не указан или бот его не видит")
        return
    if not target_name: target_name = str(target_id)
    try:
        await context.bot.restrict_chat_member(chat_id, target_id,
            permissions={"can_send_messages": True, "can_send_media": True, "can_send_other": True, "can_add_web_page_previews": True})
        await update.message.reply_text(f"🔊 {target_name} размучен")
    except:
        await update.message.reply_text(f"❌ Не удалось размутить {target_name}")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ознакомиться с правилами [тут](https://telegra.ph/Rules-01-24-146)",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_stickers_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    parts = update.message.text.strip().split()
    if len(parts) != 2: return
    try: limit = int(parts[1])
    except: return
    s = chat_settings.setdefault(chat_id, {}).setdefault("sticker_settings", {
        "sticker_limit": None, "sticker_punishment": "mute", "sticker_punishment_duration": 3600, "user_sticker_counter": {}
    })
    s["sticker_limit"] = limit
    s["user_sticker_counter"] = {}
    await update.message.reply_text(f"✅ Лимит стикеров установлен: {limit}")

async def cmd_trigger_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id): return
    chat_id = update.effective_chat.id
    lines = update.message.text.strip().split('\n', 1)
    if len(lines) < 2: return
    punishment = lines[1].strip()
    s = chat_settings.setdefault(chat_id, {}).setdefault("sticker_settings", {
        "sticker_limit": None, "sticker_punishment": "mute", "sticker_punishment_duration": 3600, "user_sticker_counter": {}
    })
    if punishment.lower() == "бан":
        s["sticker_punishment"] = "ban"
        s["sticker_punishment_duration"] = None
        await update.message.reply_text("✅ Триггер стикеров: бан")
    elif punishment.lower().startswith("мут"):
        m = re.search(r"мут\s+(.+)", punishment, re.IGNORECASE)
        if m:
            sec = parse_time(m.group(1))
            if sec:
                s["sticker_punishment"] = "mute"
                s["sticker_punishment_duration"] = sec
                await update.message.reply_text(f"✅ Триггер стикеров: мут {m.group(1)}")
            else: await update.message.reply_text("❌ Неверный формат времени")
        else: await update.message.reply_text("❌ Укажите время после 'мут'")
    else: await update.message.reply_text("❌ Укажите 'бан' или 'мут [время]'")

async def cmd_flood_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ссылка на инфо [тут](https://t.me/lunacyyflood)",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    chat_id, user_id = update.effective_chat.id, update.effective_user.id
    if chat_id in chat_settings and "sticker_settings" in chat_settings[chat_id]:
        c = chat_settings[chat_id]["sticker_settings"]["user_sticker_counter"]
        if user_id in c: c[user_id] = 0

async def post_init(app: Application):
    await app.bot.set_my_commands([])
    await app.bot.send_message(OWNER_ID, "Bot started")
    print("Bot started!")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\+бот'), cmd_grant_access))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!дел(\s+\d+)?$'), cmd_del))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!пинг$'), cmd_ping))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^анмут\b'), cmd_unmute))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^правила$'), cmd_rules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^-стикеры\s+\d+$'), cmd_stickers_limit))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^триггер стикеры'), cmd_trigger_stickers))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\.флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\.инфо флуд$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!флуд инфо$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!инфо флуд$'), cmd_flood_info))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(~filters.Sticker.ALL & ~filters.COMMAND, handle_other))
    print("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
