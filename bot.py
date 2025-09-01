import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== КОНСТАНТЫ ==================
ADMIN_CHAT_ID = 1822874836  # число, без кавычек
BOT_TOKEN = "8482024659:AAEKPoPYm96dI6DkQTxU6pFanzZKZ7Y9Gvg"

DISCOUNT_PERCENT = 10  # скидка по рефералке

# Состояния сценария
SELECTING_SERVICE, AWAITING_PRICE_CHOICE, AWAITING_PAY_CHOICE, \
ENTERING_BIRTHDATE, ENTERING_QUESTION, ENTERING_SITUATION, \
UPLOAD_PAYMENT, CONTACT_PREF = range(8)

# Кнопки шагов
BTN_PRICE = "💎 Узнать стоимость"
BTN_PAY = "💳 Оплатить"
BTN_BACK = "Назад"

# Оценки
RATINGS = ["💜 1", "💜 2", "💜 3", "💜 4", "💜 5"]

# Реквизиты для оплаты
PAYMENT_DETAILS = """
💳 *Реквизиты для оплаты:*

🌙 *Гривневая карта:* 
`4441 1111 4397 8900`

💫 *Евро карта:*
`5313 7700 4628 8378`

✨ *PayPal:* 
`@larakiri`

🔮 *После оплаты обязательно отправьте скриншот чека!*
"""

# ================== УСЛУГИ: названия, цены, «магические карточки» ==================
SERVICES = {
    "Предназначение": {
        "price_uah": 500, "price_eur": 10,
        "intro": "Каждый из нас приходит в этот мир не случайно. Душа несёт программу, скрытую от глаз, но ощущаемую сердцем.",
        "gain": [
            "карту жизненных даров и талантов",
            "понимание, зачем вы здесь и куда двигаться",
            "осознание кармических задач и ресурсов",
            "чувство гармонии и уверенности в своём пути",
        ],
        "how": "Вы называете *дату рождения* — и я открываю глубинный пласт вашей судьбы.",
        "requires": ["birthdate"],  # что нужно собрать
        "ask_birthdate": "📅 Напишите вашу *дату рождения* (ДД.ММ.ГГГГ)"
    },
    "Расклад Таро": {
        "price_uah": 500, "price_eur": 10,
        "intro": "Когда разум запутан, Таро говорит языком образов. Карты видят больше, чем мы, и мягко подсказывают, куда шагнуть.",
        "gain": [
            "прояснение ситуации здесь и сейчас",
            "ответ на конкретный вопрос",
            "подсветку скрытых влияний",
            "совет, как лучше действовать",
        ],
        "how": "Вы пишете *дату рождения* и *вопрос* — карты открывают зеркало вашей души.",
        "requires": ["birthdate", "question"],
        "ask_birthdate": "📅 Напишите вашу *дату рождения* (ДД.ММ.ГГГГ)",
        "ask_question": "❓ Напишите, пожалуйста, *ваш вопрос*"
    },
    "Все обо мне": {
        "price_uah": 2500, "price_eur": 50,
        "intro": "Это путешествие в глубь себя — где звёзды рассказывают о вашей природе и роли в танце Вселенной.",
        "gain": [
            "полное астрологическое досье",
            "анализ сильных и нежных мест",
            "понимание кармических узлов",
            "ясное направление: где деньги, любовь, миссия",
        ],
        "how": "Вы пишете *дату рождения*, и я собираю целостный портрет вашей личности.",
        "requires": ["birthdate"],
        "ask_birthdate": "📅 Напишите вашу *дату рождения* (ДД.ММ.ГГГГ)"
    },
    "Твой вопрос": {
        "price_uah": 1000, "price_eur": 20,
        "intro": "Есть ситуация, в которой нужен точный ответ? Вселенная всегда даёт знак — нужно лишь спросить правильно.",
        "gain": [
            "анализ ситуации с разных сторон",
            "вероятности развития событий",
            "советы, как действовать гармонично",
            "поддержку, которая даёт уверенность",
        ],
        "how": "Вы *описываете ситуацию и вопрос* — я считываю энергетику и даю ясность.",
        "requires": ["situation"],
        "ask_situation": "✍️ *Опишите ситуацию и ваш вопрос*"
    },
    "Послание от ангела": {
        "price_uah": 200, "price_eur": 5,
        "intro": "Иногда Душе нужно всего несколько строк, чтобы вспомнить, что она не одна. Ангелы всегда рядом.",
        "gain": [
            "светлое послание от Высших сил",
            "слова, которые попадут прямо в сердце",
            "нежное напоминание о вашей силе",
            "ощущение поддержки и тепла",
        ],
        "how": "Вы пишете *дату рождения* и *вопрос*, и через карты-проводники я передаю слова ангельской энергии.",
        "requires": ["birthdate", "question"],
        "ask_birthdate": "📅 Напишите вашу *дату рождения* (ДД.ММ.ГГГГ)",
        "ask_question": "❓ Напишите, пожалуйста, *ваш вопрос*"
    }
}

# ================== ФАЙЛ-ЛОГ ==================
def append_log(filepath: str, block: str) -> None:
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"📩 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n{block}\n" + "─"*50 + "\n\n")
    except Exception as e:
        print(f"❌ Ошибка записи {filepath}: {e}")

# ================== АДМИН: уведомления и релей ==================
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str, reply_to_message_id: Optional[int] = None):
    try:
        m = await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode='Markdown', reply_to_message_id=reply_to_message_id)
        # лог
        append_log("all_orders.txt", text)
        return m
    except Exception as e:
        print(f"❌ Не удалось отправить админу: {e}")
        append_log("all_orders.txt", text)

async def forward_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    msg = update.message
    username = f"@{user.username}" if user.username else "нет"
    message_text = msg.text if msg.text else "📎 вложение/медиа"

    card_text = (
        "👤 *Клиент написал:*\n"
        f"*Имя:* {user.first_name} {user.last_name or ''}\n"
        f"*Username:* {username}\n"
        f"*ID:* {user.id}\n"
        f"*Сообщение:* {message_text}\n"
        f"*Время:* {datetime.now().strftime('%H:%M:%S')}"
    )
    relay: Dict[int, Dict[str, Any]] = context.bot_data.setdefault("relay", {})

    if msg.text:
        admin_msg = await notify_admin(context, card_text)
        if admin_msg:
            relay[admin_msg.message_id] = {"user_chat_id": msg.chat_id, "user_message_id": msg.message_id}
    else:
        try:
            copy_msg = await context.bot.copy_message(chat_id=ADMIN_CHAT_ID, from_chat_id=msg.chat_id, message_id=msg.message_id)
            relay[copy_msg.message_id] = {"user_chat_id": msg.chat_id, "user_message_id": msg.message_id}
            admin_info = await notify_admin(context, card_text, reply_to_message_id=copy_msg.message_id)
            if admin_info:
                relay[admin_info.message_id] = {"user_chat_id": msg.chat_id, "user_message_id": msg.message_id}
        except Exception as e:
            print(f"❌ Копирование медиа админу не удалось: {e}")
            admin_msg = await notify_admin(context, card_text)
            if admin_msg:
                relay[admin_msg.message_id] = {"user_chat_id": msg.chat_id, "user_message_id": msg.message_id}

# ================== ОТВЕТ АДМИНА REPLY'ЕМ + просьба об оценке ==================
def rating_keyboard():
    return ReplyKeyboardMarkup([RATINGS, [BTN_BACK]], resize_keyboard=True)

async def ask_for_rating(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    txt = (
        "💜 Если было полезно — оцените, пожалуйста, ответ:\n"
        "выберите от *1* до *5*.\n"
        "Также можно написать пару слов обратной связи — это очень ценно 🌸"
    )
    await context.bot.send_message(chat_id=user_id, text=txt, parse_mode='Markdown', reply_markup=rating_keyboard())
    # пометим ожидание оценки (10 минут)
    awaiting: Dict[int, datetime] = context.bot_data.setdefault("await_rating", {})
    awaiting[user_id] = datetime.now() + timedelta(minutes=10)

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    relay: Dict[int, Dict[str, Any]] = context.bot_data.get("relay", {})
    mapping = relay.get(msg.reply_to_message.message_id)
    target_chat_id = mapping["user_chat_id"] if mapping else None
    if not target_chat_id:
        replied_text = msg.reply_to_message.text or ""
        m = re.search(r'ID[:\s]*([0-9]+)', replied_text)
        if m:
            target_chat_id = int(m.group(1))
    if not target_chat_id:
        await msg.reply_text("❌ Не удалось определить клиента. Ответьте именно на карточку/копию сообщения клиента.")
        return
    if msg.text:
        await context.bot.send_message(chat_id=target_chat_id, text=msg.text)
    else:
        await context.bot.copy_message(chat_id=target_chat_id, from_chat_id=ADMIN_CHAT_ID, message_id=msg.message_id)
    await msg.reply_text("✅ Ответ отправлен клиенту")
    # попросим оценку
    await ask_for_rating(context, target_chat_id)

# ================== КЛАВИАТУРЫ ==================
def services_keyboard():
    rows = [
        ["Предназначение", "Расклад Таро"],
        ["Все обо мне", "Твой вопрос"],
        ["Послание от ангела"],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def choice_price_keyboard():
    return ReplyKeyboardMarkup([[BTN_PRICE], [BTN_BACK]], resize_keyboard=True)

def choice_pay_keyboard():
    return ReplyKeyboardMarkup([[BTN_PAY], [BTN_BACK]], resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True)

# ================== ТЕКСТЫ ==================
def render_service_card(name: str) -> str:
    s = SERVICES[name]
    gain_list = "\n".join([f"• {item}" for item in s["gain"]])
    text = (
        f"✨ *{name}*\n\n"
        f"{s['intro']}\n\n"
        f"**Что вы получите:**\n{gain_list}\n\n"
        f"🌙 **Как проходит:**\n{s['how']}\n\n"
        f"Когда будете готовы — нажимайте «{BTN_PRICE}»."
    )
    return text

# ================== ХЕЛПЕРЫ ==================
def is_valid_date(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def get_discounted(price: int) -> int:
    return max(0, round(price * (100 - DISCOUNT_PERCENT) / 100))

# ================== ЗАКАЗ АДМИНУ ==================
async def forward_order_to_admin(context: ContextTypes.DEFAULT_TYPE, user_data: dict, user, service: str):
    try:
        order_text = (
            "🌟 *НОВЫЙ ЗАКАЗ* 🌟\n\n"
            f"📅 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🔮 *Услуга:* {service}\n"
            f"👤 *Клиент:* {user.first_name}\n"
            f"📱 *Username:* @{user.username or 'нет'}\n"
            f"🆔 *ID:* {user.id}\n"
        )
        if user_data.get('birthdate'):
            order_text += f"🎂 *Дата рождения:* {user_data['birthdate']}\n"
        if user_data.get('question'):
            order_text += f"❓ *Вопрос:* {user_data['question']}\n"
        if user_data.get('situation'):
            order_text += f"💫 *Ситуация:* {user_data['situation']}\n"
        if user_data.get('ref_from'):
            order_text += f"🎁 Реферал от: {user_data['ref_from']}\n"
        order_text += f"\n💬 *Ответить:* /reply {user.id} ваш_текст"
        await notify_admin(context, order_text)
    except Exception as e:
        logger.error(f"Ошибка пересылки: {e}")

# ================== КОМАНДЫ АДМИНА (reply + шаблоны + статистика) ==================
async def reply_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: /reply <id_клиента> Ваш ответ")
        return
    user_id = int(context.args[0])
    reply_text = ' '.join(context.args[1:])
    await context.bot.send_message(chat_id=user_id, text=f"💫 *Ответ от консультанта:*\n\n{reply_text}\n\n✨ С любовью, Ваша Lara", parse_mode='Markdown')
    await update.message.reply_text("✅ Ответ отправлен клиенту!")
    # просьба об оценке
    await ask_for_rating(context, user_id)

READY_ANSWERS: Dict[str, str] = {
    "ready":   "✨ Ваш ответ готов!\nЯ вложила в него максимум внимания и энергии.\nСкоро получите подробное сообщение 🌙",
    "inwork":  "🌙 Спасибо за доверие!\nВаш запрос принят в работу.\n⏳ В течение ближайшего времени я пришлю готовый разбор ✨",
    "paid":    "💫 Оплату получила, благодарю 🙏\nТеперь начинаю работать над вашим запросом.\nСкоро получите ответ 🔮",
    "done":    "🔔 Ваш разбор завершён!\nОн содержит рекомендации, важные подсказки и ответы на ваши вопросы.\n✨ Отправляю прямо сейчас 🌙",
    "thanks":  "🙏 Благодарю за доверие!\nДля меня честь сопровождать вас на этом пути 🌸"
}

async def send_template(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text(f"❌ Используйте: /{key} <id_клиента>")
        return
    user_id = int(context.args[0])
    await context.bot.send_message(chat_id=user_id, text=READY_ANSWERS[key])
    await update.message.reply_text("✅ Отправлено клиенту")
    await ask_for_rating(context, user_id)

async def cmd_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):   await send_template(update, context, "ready")
async def cmd_inwork(update: Update, context: ContextTypes.DEFAULT_TYPE):  await send_template(update, context, "inwork")
async def cmd_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):    await send_template(update, context, "paid")
async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):    await send_template(update, context, "done")
async def cmd_thanks(update: Update, context: ContextTypes.DEFAULT_TYPE):  await send_template(update, context, "thanks")

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("all_orders.txt", "r", encoding="utf-8") as f:
            content = f.read()
        msgs = content.split("─"*50)
        for msg in msgs[-5:]:
            if msg.strip():
                await update.message.reply_text(f"📋 {msg}", parse_mode='Markdown')
    except FileNotFoundError:
        await update.message.reply_text("📁 Файл с сообщениями ещё не создан")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    try:
        with open("all_orders.txt", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        await update.message.reply_text("📁 Файл ещё не создан")
        return
    total_msgs = len(re.findall(r"^📩", content, flags=re.M))
    total_orders = len(re.findall(r"🌟 \*НОВЫЙ ЗАКАЗ\*", content))
    payments = len(re.findall(r"Оплата подтверждена", content))
    report = (
        "📊 *Статистика:*\n"
        f"• Записей в журнале: {total_msgs}\n"
        f"• Новых заказов: {total_orders}\n"
        f"• Подтверждений оплаты: {payments}\n"
    )
    await update.message.reply_text(report, parse_mode='Markdown')

# ================== РЕФЕРАЛКА ==================
async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = f"REF{user_id}"
    text = (
        "🎁 *Реферальная программа*\n\n"
        f"Дайте подруге код: `{code}` — и она получит *-{DISCOUNT_PERCENT}%* на любую услугу.\n"
        "Пусть начнёт со мной диалог и отправит: `/start {code}`\n\n"
        "За каждого приглашённого — дополнительная благодарность от меня 🌸"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

def parse_ref_code(arg: str) -> Optional[int]:
    m = re.fullmatch(r"REF(\d+)", arg.strip())
    return int(m.group(1)) if m else None

# ================== СЦЕНАРИЙ ДЛЯ КЛИЕНТА ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # обработаем реф-код: /start REF<id>
    ref_from = None
    if context.args:
        ref_from = parse_ref_code(context.args[0])
        if ref_from and ref_from != update.effective_user.id:
            context.user_data['ref_from'] = ref_from
            await notify_admin(context, f"🎁 Новый клиент по рефералке от {ref_from} (клиент: {update.effective_user.id})")

    await forward_all_messages(update, context)
    welcome = (
        "🌙 *Добрый день, дорогой искатель истины!*\n\n"
        "Выберите услугу, которая резонирует с вашей душой:\n"
    )
    await update.message.reply_text(welcome, reply_markup=services_keyboard(), parse_mode='Markdown')
    return SELECTING_SERVICE

def render_price_text(name: str, ref: bool) -> str:
    s = SERVICES[name]
    uah, eur = s['price_uah'], s['price_eur']
    if ref:
        du, de = get_discounted(uah), get_discounted(eur)
        return f"💎 *Стоимость услуги:* ~~{uah}~~ → *{du}* грн или ~~{eur}~~ → *{de}* € (скидка {DISCOUNT_PERCENT}%)\n\nГотовы перейти к оплате?"
    return f"💎 *Стоимость услуги:* {uah} грн или {eur} €\n\nГотовы перейти к оплате?"

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    name = update.message.text
    if name not in SERVICES:
        await update.message.reply_text("Пожалуйста, выберите услугу из меню ниже 🌙", reply_markup=services_keyboard())
        return SELECTING_SERVICE
    context.user_data['selected_service'] = name
    # очистим ранее собранные данные
    for key in ("birthdate", "question", "situation"):
        context.user_data.pop(key, None)
    await update.message.reply_text(render_service_card(name), reply_markup=choice_price_keyboard(), parse_mode='Markdown')
    return AWAITING_PRICE_CHOICE

async def price_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    text = update.message.text
    if text == BTN_BACK:
        await update.message.reply_text("🌙 Выберите услугу:", reply_markup=services_keyboard(), parse_mode='Markdown')
        return SELECTING_SERVICE
    if text != BTN_PRICE:
        await update.message.reply_text("Нажмите, пожалуйста, «💎 Узнать стоимость» или «Назад».", reply_markup=choice_price_keyboard())
        return AWAITING_PRICE_CHOICE
    name = context.user_data.get('selected_service')
    ref = bool(context.user_data.get('ref_from'))
    await update.message.reply_text(render_price_text(name, ref), reply_markup=choice_pay_keyboard(), parse_mode='Markdown')
    return AWAITING_PAY_CHOICE

# ---- Автосбор нужных данных перед оплатой (п.10)
def next_required_field(name: str, user_data: dict) -> Optional[str]:
    for field in SERVICES[name]["requires"]:
        if field not in user_data:
            return field
    return None

async def pay_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    text = update.message.text
    name = context.user_data.get('selected_service')
    if text == BTN_BACK:
        await update.message.reply_text(render_service_card(name), reply_markup=choice_price_keyboard(), parse_mode='Markdown')
        return AWAITING_PRICE_CHOICE
    if text != BTN_PAY:
        await update.message.reply_text("Нажмите, пожалуйста, «💳 Оплатить» или «Назад».", reply_markup=choice_pay_keyboard())
        return AWAITING_PAY_CHOICE

    # проверим обязательные поля
    missing = next_required_field(name, context.user_data)
    if missing == "birthdate":
        await update.message.reply_text(SERVICES[name]["ask_birthdate"], reply_markup=back_keyboard(), parse_mode='Markdown')
        return ENTERING_BIRTHDATE
    if missing == "question":
        await update.message.reply_text(SERVICES[name]["ask_question"], reply_markup=back_keyboard(), parse_mode='Markdown')
        return ENTERING_QUESTION
    if missing == "situation":
        await update.message.reply_text(SERVICES[name]["ask_situation"], reply_markup=back_keyboard(), parse_mode='Markdown')
        return ENTERING_SITUATION

    # всё собрано — показать реквизиты
    await update.message.reply_text(PAYMENT_DETAILS, reply_markup=back_keyboard(), parse_mode='Markdown')
    return UPLOAD_PAYMENT

# ---- Обработка ввода недостающих данных
async def birthdate_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    if update.message.text == BTN_BACK:
        await update.message.reply_text(render_service_card(context.user_data['selected_service']), reply_markup=choice_price_keyboard(), parse_mode='Markdown')
        return AWAITING_PRICE_CHOICE
    if not is_valid_date(update.message.text):
        await update.message.reply_text("❌ Пожалуйста, укажите дату в формате *ДД.ММ.ГГГГ*.", reply_markup=back_keyboard(), parse_mode='Markdown')
        return ENTERING_BIRTHDATE
    context.user_data['birthdate'] = update.message.text
    # вернём на оплату
    await update.message.reply_text("✅ Дата принята. Можем продолжать.", reply_markup=choice_pay_keyboard(), parse_mode='Markdown')
    return AWAITING_PAY_CHOICE

async def question_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    if update.message.text == BTN_BACK:
        await update.message.reply_text(render_service_card(context.user_data['selected_service']), reply_markup=choice_price_keyboard(), parse_mode='Markdown')
        return AWAITING_PRICE_CHOICE
    context.user_data['question'] = update.message.text
    await update.message.reply_text("✅ Вопрос принят. Можем продолжать.", reply_markup=choice_pay_keyboard(), parse_mode='Markdown')
    return AWAITING_PAY_CHOICE

async def situation_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    if update.message.text == BTN_BACK:
        await update.message.reply_text(render_service_card(context.user_data['selected_service']), reply_markup=choice_price_keyboard(), parse_mode='Markdown')
        return AWAITING_PRICE_CHOICE
    context.user_data['situation'] = update.message.text
    await update.message.reply_text("✅ Ситуация принята. Можем продолжать.", reply_markup=choice_pay_keyboard(), parse_mode='Markdown')
    return AWAITING_PAY_CHOICE

# ---- Принятие оплаты
async def payment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    if update.message.text == BTN_BACK:
        await update.message.reply_text("Готовы продолжить оплату?", reply_markup=choice_pay_keyboard(), parse_mode='Markdown')
        return AWAITING_PAY_CHOICE
    if update.message.photo:
        service = context.user_data.get('selected_service', '—')
        user = update.message.from_user
        await forward_order_to_admin(context, context.user_data, user, service)
        completion_text = (
            f"✨ *Оплата подтверждена!*\n\n"
            f"Ваш запрос на услугу \"{service}\" принят.\n\n"
            f"⏳ *Ответ будет готов в течение часа*\n\n"
            f"💫 *Ожидайте сообщение...*"
        )
        await update.message.reply_text(completion_text, reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ *Отправьте, пожалуйста, скриншот оплаты.*", reply_markup=back_keyboard(), parse_mode='Markdown')
        return UPLOAD_PAYMENT

# ---- Обработка отзывов/оценок (п.7)
async def rating_or_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting: Dict[int, datetime] = context.bot_data.get("await_rating", {})
    expire = awaiting.get(user_id)

    if not expire or datetime.now() > expire:
        # не ждём оценку — игнорируем, чтобы не мешать сценарию
        return

    txt = update.message.text or ""
    rating_match = re.fullmatch(r"💜\s([1-5])", txt)

    entry = f"📝 ОТЗЫВ\n👤 ID: {user_id}\n"
    if rating_match:
        stars = int(rating_match.group(1))
        entry += f"Оценка: {stars}/5\n"
        await update.message.reply_text("Спасибо за вашу оценку 💜")
    else:
        entry += f"Комментарий: {txt}\n"
        await update.message.reply_text("Благодарю за тёплые слова 🌸")

    append_log("reviews.txt", entry)
    await notify_admin(context, entry)

    # если это была оценка — оставим окно ещё на 10 минут для текста; если текст — закроем ожидание
    if rating_match:
        awaiting[user_id] = datetime.now() + timedelta(minutes=10)
    else:
        awaiting.pop(user_id, None)

# ================== ПРОЧЕЕ ==================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_all_messages(update, context)
    await update.message.reply_text("🌙 *Диалог прерван.* /start — начать заново", reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    return ConversationHandler.END

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("all_orders.txt", "r", encoding="utf-8") as f:
            content = f.read()
        msgs = content.split("─"*50)
        for msg in msgs[-5:]:
            if msg.strip():
                await update.message.reply_text(f"📋 {msg}", parse_mode='Markdown')
    except FileNotFoundError:
        await update.message.reply_text("📁 Файл с сообщениями ещё не создан")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')

async def ping_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔔 Тест: админ, это сообщение пришло тебе?")

# ================== MAIN ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_SERVICE: [
                MessageHandler(filters.Regex(f'^({"|".join(SERVICES.keys())})$'), service_selected)
            ],
            AWAITING_PRICE_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, price_choice)
            ],
            AWAITING_PAY_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pay_choice)
            ],
            ENTERING_BIRTHDATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, birthdate_received)
            ],
            ENTERING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_received)
            ],
            ENTERING_SITUATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, situation_received)
            ],
            UPLOAD_PAYMENT: [
                MessageHandler(filters.PHOTO, payment_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Сценарий
    application.add_handler(conv_handler)

    # Команды админа
    application.add_handler(CommandHandler("reply", reply_to_client))
    application.add_handler(CommandHandler("ready",   cmd_ready))
    application.add_handler(CommandHandler("inwork",  cmd_inwork))
    application.add_handler(CommandHandler("paid",    cmd_paid))
    application.add_handler(CommandHandler("done",    cmd_done))
    application.add_handler(CommandHandler("thanks",  cmd_thanks))
    application.add_handler(CommandHandler("orders", show_orders))
    application.add_handler(CommandHandler("stats", stats))

    # Рефералка и сервисные
    application.add_handler(CommandHandler("promo", promo))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("ping_admin", ping_admin))

    # Ответ админа через обычный Reply (на карточку/копию)
    application.add_handler(MessageHandler(filters.Chat(ADMIN_CHAT_ID), admin_reply))

    # Ловим оценки/отзывы (пока открыто окно фидбэка)
    application.add_handler(MessageHandler(filters.Regex(r'^💜 [1-5]$'), rating_or_feedback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, rating_or_feedback))

    # Подстраховка: любые сообщения вне сценария → админу
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_all_messages))

    print("🌙 Бот запущен. Рефералка -10%, автосбор данных, отзывы/оценки активны.")
    application.run_polling()

if __name__ == '__main__':
    main()
