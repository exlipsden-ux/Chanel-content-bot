from telebot import TeleBot, types
from telebot.apihelper import ApiTelegramException

TOKEN         = ''
CHANNEL_ID    = -
ALLOWED_IDS   = {}
bot = TeleBot(TOKEN, parse_mode='HTML')
post_sessions: dict[int, bool] = {}

def make_button_markup(spec: str) -> types.InlineKeyboardMarkup | None:
    s = spec.strip()
    if not s or s.lower() == 'нет':
        return None
    if '|' not in s:
        raise ValueError('Ожидаем формат "текст|URL|текст кнопки')
    parts = [p.strip() for p in s.split('|', 2)]
    if len(parts) != 3:
        raise ValueError('Неверное число частей, надо три через |')
    text, url, label = parts
    if not (url.startswith(('http://','https://','tg://','https://t.me/')) and label):
        raise ValueError('Неверный URL или пустой текст кнопки')
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(label, url=url))
    return markup

def make_edit_button(spec: str):
    spec = spec.strip()

    if not spec or spec.lower() == "нет":
        return None

    if "|" not in spec:
        raise ValueError("Нужно: ссылка|текст кнопки")

    url, text = map(str.strip, spec.split("|", 1))

    if not url.startswith(("http://", "https://", "tg://", "https://t.me/")):
        raise ValueError("Неверная ссылка")

    if not text:
        raise ValueError("Пустой текст кнопки")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text, url=url))

    return markup

def is_allowed(uid: int) -> bool:
    return uid in ALLOWED_IDS

@bot.message_handler(commands=['post'])
def cmd_post_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    post_sessions[message.from_user.id] = True
    bot.send_message(
        message.from_user.id,
        "Пришли теперь либо текст в формате:\n"
        "Текст сообщения|URL|Текст кнопки\n"
        "или фото с подписью в том же формате.\n",
        parse_mode='Markdown'
    )
@bot.message_handler(func=lambda m: post_sessions.get(m.from_user.id, False),
                     content_types=['text', 'photo'])
def cmd_post_do(message: types.Message):
    admin = message.from_user.id
    post_sessions.pop(admin, None)

    try:
        if message.content_type == 'text':
            payload = message.text
            markup = make_button_markup(payload)
            text = payload.split('|',1)[0].strip() if '|' in payload else payload
            bot.send_message(chat_id=CHANNEL_ID, text=text, reply_markup=markup)

        else:
            # фото с подписью
            caption = message.caption or ''
            markup = make_button_markup(caption)
            text = caption.split('|',1)[0].strip() if '|' in caption else ''
            bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=message.photo[-1].file_id,
                caption=text,
                reply_markup=markup
            )

        bot.send_message(admin, "Опубликовано в канале.")
    except ValueError as e:
        bot.send_message(admin, f"Ошибка формата: {e}")
    except ApiTelegramException as e:
        bot.send_message(admin, f"Ошибка при отправке в канал: {e}")

button_edit_sessions = {}


@bot.message_handler(
    func=lambda msg: bool(getattr(msg, "forward_from_chat", None)
                          and getattr(msg, "forward_from_message_id", None)),
    content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker']
)
def start_button_edit(msg):
    user_id = msg.from_user.id

    if not is_allowed(user_id):
        return

    chat_id = msg.forward_from_chat.id
    message_id = msg.forward_from_message_id

    button_edit_sessions[user_id] = (chat_id, message_id)

    bot.send_message(
        user_id,
        "📌 Пост принят.\n\n"
        "Отправь новую кнопку:\n"
        "`https://site.ru|Текст кнопки`\n\n"
        "или напиши `нет`, чтобы удалить кнопку.",
        parse_mode="Markdown"
    )


@bot.message_handler(
    func=lambda msg: bool(getattr(msg, "forward_from_chat", None)
                          and not getattr(msg, "forward_from_message_id", None)),
    content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker']
)
def forwarded_copy_warning(msg):
    user_id = msg.from_user.id

    if not is_allowed(user_id):
        return

    bot.send_message(
        user_id,
        "❗ Нужно переслать сообщение обычным способом, не копией."
    )


@bot.message_handler(
    func=lambda msg: msg.from_user.id in button_edit_sessions,
    content_types=['text']
)
def apply_button_edit(msg):
    user_id = msg.from_user.id

    if not is_allowed(user_id):
        button_edit_sessions.pop(user_id, None)
        return

    session_data = button_edit_sessions.pop(user_id, None)

    if not session_data:
        bot.send_message(user_id, "❗ Сессия потеряна.")
        return

    chat_id, message_id = session_data
    button_spec = msg.text.strip()

    try:
        new_markup = make_edit_button(button_spec)
    except ValueError as err:
        bot.send_message(user_id, f"❗ Ошибка формата: {err}")
        return

    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_markup
        )

        bot.send_message(user_id, "✅ Кнопка обновлена.")

    except ApiTelegramException as api_err:
        bot.send_message(user_id, f"❗ Telegram ошибка: {api_err}")

if __name__ == '__main__':
    bot.infinity_polling()
