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
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            user_name = user.user.first_name or f"@{user.user.username}" or str(user_id)
        except:
            user_name = str(user_id)
        
        if s["sticker_punishment"] == "ban":
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                # Сообщение в чат
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚫 {user_name} забанен за {s['sticker_limit']} стикеров подряд"
                )
                # Уведомление в ЛС владельцу
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🚫 Пользователь {user_name} (ID: {user_id}) забанен в чате {chat_id} за {s['sticker_limit']} стикеров подряд"
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"❌ Не удалось забанить {user_name} (ID: {user_id}): {e}"
                )
        else:
            duration = s["sticker_punishment_duration"]
            until = datetime.now() + timedelta(seconds=duration)
            
            # Форматируем время
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
                # Сообщение в чат
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔇 {user_name} замучен на {time_display} за {s['sticker_limit']} стикеров подряд"
                )
                # Уведомление в ЛС владельцу
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🔇 Пользователь {user_name} (ID: {user_id}) замучен на {time_display} в чате {chat_id} за {s['sticker_limit']} стикеров подряд"
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"❌ Не удалось замутить {user_name} (ID: {user_id}): {e}"
                )
