import asyncio
import logging
import os
import json
import base64
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject

import google.generativeai as genai
from PIL import Image
import io

# ============ КОНФИГ ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
ADMIN_ID = 8777046904
ADMIN_USERNAME = "DietologLobar"
DB_PATH = "bot.db"

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "ВСТАВЬ_КЛЮЧ_GEMINI")
GEMINI_PROXY_URL = os.getenv("GEMINI_PROXY_URL", "")  # Например: https://gemini-proxy.xxx.workers.dev
GEMINI_MODEL = "gemini-2.0-flash"  # Бесплатная модель с vision

# ============ ПЕРЕВОДЫ ============
TEXTS = {
    "ru": {
        "choose_language": "🌐 Выберите язык / Tilni tanlang:",
        "welcome": (
            "👋 Добро пожаловать в бот для похудения!\n\n"
            "Здесь вы сможете вести дневник питания, считать калории "
            "и получать персональные рекомендации.\n\n"
            "💳 Подписка: /subscribe\n"
            "🌐 Сменить язык: /language\n"
            "📸 Отправь фото еды — я посчитаю калории\n"
            "📊 /today — что съел сегодня"
        ),
        "language_set": "✅ Язык установлен: Русский",
        "payment_text": (
            "💳 <b>Оплата подписки</b>\n\n"
            "Для оформления подписки напишите администратору: @DietologLobar\n\n"
            "После оплаты нажмите кнопку «✅ Я оплатил(а)» — администратор "
            "проверит поступление средств и активирует доступ."
        ),
        "pay_button": "Написать @DietologLobar",
        "paid_button": "✅ Я оплатил(а)",
        "claim_sent": "Заявка отправлена администратору @DietologLobar. Ожидайте активации.",
        "sub_active": "🎉 Ваша подписка активирована до {date}! Приятного использования.",
        "sub_expired": "⛔ Ваша подписка истекла. Продлите доступ: /subscribe",
        "blocked": "⛔ Ваш доступ к боту заблокирован администратором.",
        "unblocked": "✅ Ваш доступ к боту восстановлен.",
        "extend_notify": "🎁 Ваша подписка продлена на {days} дн. до {date}!",
        "need_sub": "⛔ Для этой функции нужна активная подписка. Оформить: /subscribe",
        "onboarding_gender": "👤 Выбери свой пол:",
        "onboarding_age": "🎂 Сколько тебе лет? (напиши число)",
        "onboarding_weight": "⚖️ Твой вес в кг? (напиши число, например 75.5)",
        "onboarding_height": "📏 Твой рост в см? (напиши число, например 175)",
        "onboarding_activity": "🏃 Уровень активности:",
        "onboarding_goal": "🎯 Твоя цель:",
        "onboarding_done": "✅ Норма калорий рассчитана: <b>{kcal} ккал/день</b>\n\nТеперь отправь фото еды, и я посчитаю калории!",
        "gender_male": "👨 Мужской",
        "gender_female": "👩 Женский",
        "activity_low": "🪑 Сидячий (мало движения)",
        "activity_medium": "🚶 Средний (1-3 тренировки/нед)",
        "activity_high": "🏋️ Высокий (4+ тренировки/нед)",
        "goal_lose": "📉 Похудеть",
        "goal_keep": "⚖️ Удержать вес",
        "photo_analyzing": "🔍 Анализирую фото...",
        "photo_result": (
            "🍽 <b>{dish}</b>\n\n"
            "🔥 Калории: <b>{calories} ккал</b>\n"
            "🥩 Белки: {proteins} г\n"
            "🧈 Жиры: {fats} г\n"
            "🍞 Углеводы: {carbs} г\n\n"
            "📊 Сегодня: {today_kcal} / {norm_kcal} ккал"
        ),
        "photo_error": "😔 Не удалось распознать еду на фото. Попробуй другое фото или добавь текстом: /add",
        "add_text_prompt": "✍️ Напиши, что ты съел (например: «2 яйца и тост»)",
        "today_empty": "📭 Сегодня ты ещё ничего не записал.\n\nОтправь фото еды или команду /add",
        "today_header": "📊 <b>Сегодня</b>\n\n",
        "today_item": "• {name}: {cal} ккал\n",
        "today_footer": "\n🔥 Итого: <b>{total} / {norm} ккал</b>",
        "no_norm": "⚠️ Сначала пройди онбординг: /start",
    },
    "uz": {
        "choose_language": "🌐 Выберите язык / Tilni tanlang:",
        "welcome": (
            "👋 Ozish botiga xush kelibsiz!\n\n"
            "Bu yerda siz ovqatlanish kundaligini yuritishingiz, kaloriyalarni "
            "hisoblashingiz va shaxsiy tavsiyalar olishingiz mumkin.\n\n"
            "💳 Obuna: /subscribe\n"
            "🌐 Tilni o'zgartirish: /language\n"
            "📸 Ovqat rasmini yuboring — kaloriyalarni hisoblayman\n"
            "📊 /today — bugun nima yedingiz"
        ),
        "language_set": "✅ Til tanlandi: O'zbekcha",
        "payment_text": (
            "💳 <b>Obunani to'lash</b>\n\n"
            "Obuna rasmiylashtirish uchun administratorga yozing: @DietologLobar\n\n"
            "To'lovdan so'ng «✅ Men to'ladim» tugmasini bosing — administrator "
            "mablag' tushganini tekshirib, kirishni faollashtiradi."
        ),
        "pay_button": "@DietologLobar ga yozish",
        "paid_button": "✅ Men to'ladim",
        "claim_sent": "So'rov @DietologLobar administratoriga yuborildi. Faollashtirishni kuting.",
        "sub_active": "🎉 Obunangiz {date} gacha faollashtirildi! Yoqimli foydalanish.",
        "sub_expired": "⛔ Obunangiz tugadi. Obunani yangilang: /subscribe",
        "blocked": "⛔ Botga kirishingiz administrator tomonidan bloklandi.",
        "unblocked": "✅ Botga kirishingiz tiklandi.",
        "extend_notify": "🎁 Obunangiz {days} kunga uzaytirildi, {date} gacha!",
        "need_sub": "⛔ Bu funksiya uchun faol obuna kerak. Rasmiylashtirish: /subscribe",
        "onboarding_gender": "👤 Jinsingizni tanlang:",
        "onboarding_age": "🎂 Yoshingiz nechada? (raqam yozing)",
        "onboarding_weight": "⚖️ Vazningiz kg? (raqam, masalan 75.5)",
        "onboarding_height": "📏 Bo'yingiz sm? (raqam, masalan 175)",
        "onboarding_activity": "🏃 Faollik darajasi:",
        "onboarding_goal": "🎯 Maqsadingiz:",
        "onboarding_done": "✅ Kaloriya normasi hisoblandi: <b>{kcal} kkal/kun</b>\n\nEndi ovqat rasmini yuboring, kaloriyalarni hisoblayman!",
        "gender_male": "👨 Erkak",
        "gender_female": "👩 Ayol",
        "activity_low": "🪑 Kam harakat",
        "activity_medium": "🚶 O'rtacha (haftada 1-3 mashg'ulot)",
        "activity_high": "🏋️ Yuqori (haftada 4+ mashg'ulot)",
        "goal_lose": "📉 Ozish",
        "goal_keep": "⚖️ Vaznni saqlash",
        "photo_analyzing": "🔍 Rasm tahlil qilinmoqda...",
        "photo_result": (
            "🍽 <b>{dish}</b>\n\n"
            "🔥 Kaloriya: <b>{calories} kkal</b>\n"
            "🥩 Oqsillar: {proteins} g\n"
            "🧈 Yog'lar: {fats} g\n"
            "🍞 Uglevodlar: {carbs} g\n\n"
            "📊 Bugun: {today_kcal} / {norm_kcal} kkal"
        ),
        "photo_error": "😔 Rasmda ovqatni aniqlay olmadim. Boshqa rasm yuboring yoki matn bilan qo'shing: /add",
        "add_text_prompt": "✍️ Nima yeganingizni yozing (masalan: «2 tuxum va tost»)",
        "today_empty": "📭 Bugun hali hech narsa yozmadingiz.\n\nOvqat rasmini yuboring yoki /add buyrug'ini bering",
        "today_header": "📊 <b>Bugun</b>\n\n",
        "today_item": "• {name}: {cal} kkal\n",
        "today_footer": "\n🔥 Jami: <b>{total} / {norm} kkal</b>",
        "no_norm": "⚠️ Avval onboardingdan o'ting: /start",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, "")
    return text.format(**kwargs) if kwargs else text


# ============ GEMINI ИНИЦИАЛИЗАЦИЯ ============
# Если задан прокси — используем его вместо прямого URL
if GEMINI_PROXY_URL:
    # Патчим базовый URL для google-generativeai
    import google.generativeai.client as genai_client
    genai_client._base_url = GEMINI_PROXY_URL
    genai.configure(api_key=GEMINI_API_KEY)
else:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(GEMINI_MODEL)


# ============ БД ============
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT,
                subscription_end TEXT,
                is_blocked INTEGER DEFAULT 0,
                gender TEXT,
                age INTEGER,
                weight REAL,
                height REAL,
                activity TEXT,
                goal TEXT,
                daily_kcal INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                food_name TEXT,
                calories INTEGER,
                proteins REAL,
                fats REAL,
                carbs REAL,
                photo_id TEXT
            )
        """)
        await db.commit()


async def register_user(user_id: int, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, language, subscription_end, is_blocked) "
            "VALUES (?, ?, NULL, NULL, 0)",
            (user_id, username)
        )
        await db.commit()


async def get_raw_lang(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def get_user_lang(user_id: int) -> str:
    lang = await get_raw_lang(user_id)
    return lang if lang else "ru"


async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id)
        )
        await db.commit()


async def is_subscribed(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT subscription_end FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row or not row[0]:
        return False
    return datetime.fromisoformat(row[0]) > datetime.now()


async def activate_subscription(user_id: int, days: int) -> datetime:
    end_date = datetime.now() + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (end_date.isoformat(), user_id)
        )
        await db.commit()
    return end_date


async def extend_subscription(user_id: int, days: int) -> datetime | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT subscription_end FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        now = datetime.now()
        current_end = datetime.fromisoformat(row[0]) if row[0] else None
        base = current_end if current_end and current_end > now else now
        new_end = base + timedelta(days=days)

        await db.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (new_end.isoformat(), user_id)
        )
        await db.commit()
        return new_end


async def set_blocked(user_id: int, blocked: bool) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET is_blocked = ? WHERE user_id = ?",
            (1 if blocked else 0, user_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def is_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_blocked FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row and row[0])


async def get_user_profile(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def update_user_profile(user_id: int, **kwargs):
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
        await db.commit()


async def save_meal(user_id: int, food_name: str, calories: int, proteins: float, fats: float, carbs: float, photo_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO meals (user_id, date, food_name, calories, proteins, fats, carbs, photo_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, datetime.now().date().isoformat(), food_name, calories, proteins, fats, carbs, photo_id)
        )
        await db.commit()


async def get_today_meals(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM meals WHERE user_id = ? AND date = ?",
            (user_id, datetime.now().date().isoformat())
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_today_total(user_id: int) -> int:
    meals = await get_today_meals(user_id)
    return sum(m["calories"] for m in meals)


# ============ MIDDLEWARE ============
class BlockCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and user.id != ADMIN_ID and await is_blocked(user.id):
            lang = await get_user_lang(user.id)
            msg = t(lang, "blocked")
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            return
        return await handler(event, data)


# ============ КЛАВИАТУРЫ ============
def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        ]
    ])


def payment_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "pay_button"), url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text=t(lang, "paid_button"), callback_data="user_paid_claim")],
    ])


def gender_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "gender_male"), callback_data="ob_male"),
         InlineKeyboardButton(text=t(lang, "gender_female"), callback_data="ob_female")],
    ])


def activity_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "activity_low"), callback_data="ob_low")],
        [InlineKeyboardButton(text=t(lang, "activity_medium"), callback_data="ob_medium")],
        [InlineKeyboardButton(text=t(lang, "activity_high"), callback_data="ob_high")],
    ])


def goal_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "goal_lose"), callback_data="ob_lose")],
        [InlineKeyboardButton(text=t(lang, "goal_keep"), callback_data="ob_keep")],
    ])


# ============ РОУТЕР ============
router = Router()

# Состояния онбординга (в памяти, сбрасываются при рестарте)
onboarding_state: Dict[int, dict] = {}


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await register_user(user.id, user.username)

    raw_lang = await get_raw_lang(user.id)
    if raw_lang:
        profile = await get_user_profile(user.id)
        if not profile or not profile.get("daily_kcal"):
            # Язык есть, но онбординг не пройден
            await start_onboarding(message, raw_lang)
        else:
            await message.answer(t(raw_lang, "welcome"))
    else:
        await message.answer(
            "🌐 Выберите язык / Tilni tanlang:",
            reply_markup=language_keyboard()
        )


@router.callback_query(F.data.in_({"lang_ru", "lang_uz"}))
async def set_language(callback: CallbackQuery):
    lang = "ru" if callback.data == "lang_ru" else "uz"
    await set_user_lang(callback.from_user.id, lang)

    await callback.message.edit_text(t(lang, "language_set"))
    profile = await get_user_profile(callback.from_user.id)
    if not profile or not profile.get("daily_kcal"):
        await start_onboarding(callback.message, lang)
    else:
        await callback.message.answer(t(lang, "welcome"))
    await callback.answer()


async def start_onboarding(message: Message, lang: str):
    user_id = message.chat.id
    onboarding_state[user_id] = {"step": "gender"}
    await message.answer(t(lang, "onboarding_gender"), reply_markup=gender_keyboard(lang))


@router.callback_query(F.data.startswith("ob_"))
async def onboarding_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    data = callback.data

    if data in ("ob_male", "ob_female"):
        gender = "male" if data == "ob_male" else "female"
        onboarding_state[user_id] = {"step": "age", "gender": gender}
        await callback.message.answer(t(lang, "onboarding_age"))
    elif data in ("ob_low", "ob_medium", "ob_high"):
        activity = data.replace("ob_", "")
        onboarding_state[user_id]["activity"] = activity
        onboarding_state[user_id]["step"] = "goal"
        await callback.message.answer(t(lang, "onboarding_goal"), reply_markup=goal_keyboard(lang))
    elif data in ("ob_lose", "ob_keep"):
        goal = data.replace("ob_", "")
        state = onboarding_state.get(user_id, {})
        state["goal"] = goal
        await finish_onboarding(callback.message, user_id, lang, state)

    await callback.answer()


@router.message(F.text.regexp(r"^\d+([.,]\d+)?$"))
async def onboarding_numbers(message: Message):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    state = onboarding_state.get(user_id)

    if not state:
        return  # не в процессе онбординга — игнорируем

    try:
        value = float(message.text.replace(",", "."))
    except ValueError:
        return

    step = state.get("step")
    if step == "age":
        state["age"] = int(value)
        state["step"] = "weight"
        await message.answer(t(lang, "onboarding_weight"))
    elif step == "weight":
        state["weight"] = value
        state["step"] = "height"
        await message.answer(t(lang, "onboarding_height"))
    elif step == "height":
        state["height"] = value
        state["step"] = "activity"
        await message.answer(t(lang, "onboarding_activity"), reply_markup=activity_keyboard(lang))


async def finish_onboarding(message: Message, user_id: int, lang: str, state: dict):
    # Формула Миффлина-Сан Жеора
    gender = state.get("gender", "male")
    age = state.get("age", 30)
    weight = state.get("weight", 70)
    height = state.get("height", 170)
    activity = state.get("activity", "low")
    goal = state.get("goal", "lose")

    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    multipliers = {"low": 1.2, "medium": 1.55, "high": 1.725}
    tdee = bmr * multipliers.get(activity, 1.2)

    if goal == "lose":
        daily_kcal = int(tdee - 500)  # дефицит 500 ккал
    else:
        daily_kcal = int(tdee)

    await update_user_profile(
        user_id,
        gender=gender, age=age, weight=weight, height=height,
        activity=activity, goal=goal, daily_kcal=daily_kcal
    )
    onboarding_state.pop(user_id, None)

    await message.answer(t(lang, "onboarding_done", kcal=daily_kcal))


# ============ АНАЛИЗ ФОТО ============
@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)

    if not await is_subscribed(user_id):
        await message.answer(t(lang, "need_sub"))
        return

    profile = await get_user_profile(user_id)
    if not profile or not profile.get("daily_kcal"):
        await message.answer(t(lang, "no_norm"))
        return

    await message.answer(t(lang, "photo_analyzing"))

    # Скачиваем фото
    photo = message.photo[-1]
    file = await message.bot.download(photo)
    image_data = file.read()
    image = Image.open(io.BytesIO(image_data))

    prompt = """Ты нутрициолог. Проанализируй фото еды.
Ответь СТРОГО в JSON без markdown:
{"dish": "название блюда", "calories": 250, "proteins": 12.5, "fats": 8.0, "carbs": 30.0}
Оцени порцию примерно. Если на фото несколько блюд — суммируй."""

    try:
        response = await asyncio.to_thread(
            model.generate_content, [prompt, image]
        )
        text = response.text.strip()
        # Чистим возможные ```json ... ```
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())

        dish = data.get("dish", "Блюдо")
        calories = int(data.get("calories", 0))
        proteins = float(data.get("proteins", 0))
        fats = float(data.get("fats", 0))
        carbs = float(data.get("carbs", 0))

        await save_meal(user_id, dish, calories, proteins, fats, carbs, photo.file_id)

        today_total = await get_today_total(user_id)
        norm = profile["daily_kcal"]

        await message.answer(t(
            lang, "photo_result",
            dish=dish, calories=calories, proteins=proteins, fats=fats, carbs=carbs,
            today_kcal=today_total, norm_kcal=norm
        ))
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        await message.answer(t(lang, "photo_error"))


@router.message(Command("today"))
async def cmd_today(message: Message):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)

    if not await is_subscribed(user_id):
        await message.answer(t(lang, "need_sub"))
        return

    profile = await get_user_profile(user_id)
    if not profile or not profile.get("daily_kcal"):
        await message.answer(t(lang, "no_norm"))
        return

    meals = await get_today_meals(user_id)
    if not meals:
        await message.answer(t(lang, "today_empty"))
        return

    text = t(lang, "today_header")
    total = 0
    for m in meals:
        text += t(lang, "today_item", name=m["food_name"], cal=m["calories"])
        total += m["calories"]

    text += t(lang, "today_footer", total=total, norm=profile["daily_kcal"])
    await message.answer(text)


@router.message(Command("add"))
async def cmd_add(message: Message):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)

    if not await is_subscribed(user_id):
        await message.answer(t(lang, "need_sub"))
        return

    profile = await get_user_profile(user_id)
    if not profile or not profile.get("daily_kcal"):
        await message.answer(t(lang, "no_norm"))
        return

    await message.answer(t(lang, "add_text_prompt"))
    onboarding_state[user_id] = {"step": "add_food"}


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    state = onboarding_state.get(user_id)

    # Если в режиме добавления еды текстом
    if state and state.get("step") == "add_food":
        onboarding_state.pop(user_id, None)

        prompt = f"""Ты нутрициолог. Пользователь описал еду: "{message.text}"
Оцени калории и БЖУ. Ответь СТРОГО в JSON:
{{"dish": "название", "calories": 250, "proteins": 12.5, "fats": 8.0, "carbs": 30.0}}"""

        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())

            dish = data.get("dish", message.text[:50])
            calories = int(data.get("calories", 0))
            proteins = float(data.get("proteins", 0))
            fats = float(data.get("fats", 0))
            carbs = float(data.get("carbs", 0))

            await save_meal(user_id, dish, calories, proteins, fats, carbs)

            profile = await get_user_profile(user_id)
            today_total = await get_today_total(user_id)
            norm = profile["daily_kcal"]

            await message.answer(t(
                lang, "photo_result",
                dish=dish, calories=calories, proteins=proteins, fats=fats, carbs=carbs,
                today_kcal=today_total, norm_kcal=norm
            ))
        except Exception as e:
            logging.error(f"Gemini text error: {e}")
            await message.answer(t(lang, "photo_error"))
        return


# ============ АДМИН-КОМАНДЫ ============
@router.message(Command("activate"))
async def activate_sub(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /activate <user_id> <days>")
        return
    try:
        target_id = int(args[1])
        days = int(args[2])
    except ValueError:
        await message.answer("❌ user_id и days должны быть числами.")
        return

    end_date = await activate_subscription(target_id, days)
    await message.answer(f"✅ Пользователь {target_id} активирован до {end_date.date()}")
    try:
        lang = await get_user_lang(target_id)
        await message.bot.send_message(target_id, t(lang, "sub_active", date=end_date.date()))
    except Exception:
        pass


@router.message(Command("extend"))
async def cmd_extend(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /extend <user_id> <days>")
        return
    try:
        target_id = int(args[1])
        days = int(args[2])
    except ValueError:
        await message.answer("❌ user_id и days должны быть числами.")
        return
    if days <= 0:
        await message.answer("❌ days должно быть положительным.")
        return

    new_end = await extend_subscription(target_id, days)
    if new_end is None:
        await message.answer(f"❌ Пользователь {target_id} не найден.")
        return
    await message.answer(f"✅ Подписка {target_id} продлена на {days} дн. до {new_end.date()}")
    try:
        lang = await get_user_lang(target_id)
        await message.bot.send_message(target_id, t(lang, "extend_notify", days=days, date=new_end.date()))
    except Exception:
        pass


@router.message(Command("check"))
async def check_sub(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /check <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return
    status = "✅ активна" if await is_subscribed(target_id) else "⛔ не активна"
    blocked = "🚫 заблокирован" if await is_blocked(target_id) else "🟢 не заблокирован"
    await message.answer(f"Пользователь {target_id}:\nПодписка: {status}\nСтатус: {blocked}")


@router.message(Command("block"))
async def cmd_block(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /block <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return
    if target_id == ADMIN_ID:
        await message.answer("❌ Нельзя заблокировать себя.")
        return
    found = await set_blocked(target_id, True)
    if not found:
        await message.answer(f"❌ Пользователь {target_id} не найден.")
        return
    await message.answer(f"🚫 Пользователь {target_id} заблокирован.")
    try:
        lang = await get_user_lang(target_id)
        await message.bot.send_message(target_id, t(lang, "blocked"))
    except Exception:
        pass


@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /unblock <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return
    found = await set_blocked(target_id, False)
    if not found:
        await message.answer(f"❌ Пользователь {target_id} не найден.")
        return
    await message.answer(f"✅ Пользователь {target_id} разблокирован.")
    try:
        lang = await get_user_lang(target_id)
        await message.bot.send_message(target_id, t(lang, "unblocked"))
    except Exception:
        pass


# ============ MAIN ============
async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.message.middleware(BlockCheckMiddleware())
    dp.callback_query.middleware(BlockCheckMiddleware())
    dp.include_router(router)

    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
