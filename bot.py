import asyncio
import random
import json
import os
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# ==============================
# НАЛАШТУВАННЯ
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
dp = Dispatcher()

# Файл для зберігання результатів дня
DATA_FILE = "daily_results.json"


# ==============================
# РОБОТА З ДАНИМИ
# ==============================

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def today() -> str:
    return str(date.today())


# ==============================
# ОТРИМАННЯ УЧАСНИКІВ ГРУПИ
# ==============================

async def get_members(bot: Bot, chat_id: int) -> list[dict]:
    """
    Повертає список учасників чату.
    Через обмеження Telegram API для великих груп — бот збирає учасників
    зі списку тих, хто писав повідомлення (кешується автоматично нижче).
    Для супергруп з адмін-правами використовується getChatAdministrators як fallback.
    """
    data = load_data()
    chat_key = f"members_{chat_id}"

    if chat_key not in data:
        data[chat_key] = []

    return data.get(chat_key, [])


def add_member(chat_id: int, user: types.User):
    """Додає учасника до кешу якщо його ще нема."""
    data = load_data()
    chat_key = f"members_{chat_id}"

    if chat_key not in data:
        data[chat_key] = []

    members = data[chat_key]
    ids = [m["id"] for m in members]

    if user.id not in ids and not user.is_bot:
        members.append({
            "id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
        })
        data[chat_key] = members
        save_data(data)


def format_user(member: dict) -> str:
    """Форматує ім'я користувача для виводу."""
    if member.get("username"):
        return f"@{member['username']}"
    return member.get("first_name", "Невідомий")


# ==============================
# ХЕНДЛЕР: збір учасників
# ==============================

@dp.message()
async def track_members(message: Message):
    """Відстежує всіх хто пише — додає до пулу учасників."""
    if message.chat.type in ("group", "supergroup") and message.from_user:
        add_member(message.chat.id, message.from_user)

    # Далі обробляємо команди
    if message.text and message.text.startswith("/"):
        await handle_commands(message)


async def handle_commands(message: Message):
    text = message.text.split()[0].lower().split("@")[0]  # /command@botname → /command

    if text == "/pidor":
        await cmd_pidor(message)
    elif text == "/krasavchyk":
        await cmd_krasavchyk(message)
    elif text == "/start" or text == "/help":
        await cmd_help(message)
    elif text == "/members":
        await cmd_members(message)
    elif text == "/stats":
        await cmd_stats(message)


# ==============================
# КОМАНДИ
# ==============================

async def cmd_help(message: Message):
    await message.reply(
        "🎲 <b>Бот дня</b>\n\n"
        "Команди:\n"
        "🍑 /pidor — обрати підора дня\n"
        "😎 /krasavchyk — обрати красавчика дня\n"
        "📊 /stats — статистика групи\n"
        "👥 /members — список учасників у пулі\n\n"
        "<i>Просто пишіть в чат — бот запам'ятовує учасників автоматично!</i>",
        parse_mode="HTML"
    )


async def cmd_members(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Команда тільки для груп!")
        return

    members = await get_members(message.bot, message.chat.id)
    if not members:
        await message.reply("😶 Поки що нікого в пулі. Нехай люди пишуть в чат!")
        return

    names = "\n".join(f"• {format_user(m)}" for m in members)
    await message.reply(f"👥 <b>Учасники ({len(members)}):</b>\n{names}", parse_mode="HTML")


async def cmd_pidor(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Команда тільки для груп!")
        return

    chat_id = message.chat.id
    today_key = today()
    data = load_data()
    day_data = data.get(f"day_{chat_id}_{today_key}", {})

    # Вже є результат на сьогодні?
    if "pidor" in day_data:
        winner = day_data["pidor"]
        await message.reply(
            f"🍑 Підор дня вже обраний!\n\n"
            f"Сьогодні це — <b>{winner['name']}</b> 🎉",
            parse_mode="HTML"
        )
        return

    members = await get_members(message.bot, chat_id)
    if len(members) < 2:
        await message.reply("😅 Замало учасників! Потрібно мінімум 2 людини.")
        return

    # Виключаємо вже обраного красавчика
    krasavchyk_id = day_data.get("krasavchyk", {}).get("id")
    pool = [m for m in members if m["id"] != krasavchyk_id]

    if not pool:
        pool = members  # fallback якщо всі вже обрані

    winner = random.choice(pool)

    # Зберігаємо результат
    day_data["pidor"] = {"id": winner["id"], "name": format_user(winner)}
    data[f"day_{chat_id}_{today_key}"] = day_data

    # Оновлюємо статистику
    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    user_id_str = str(winner["id"])
    if user_id_str not in data[stats_key]:
        data[stats_key][user_id_str] = {"name": format_user(winner), "pidor": 0, "krasavchyk": 0}
    data[stats_key][user_id_str]["pidor"] += 1
    data[stats_key][user_id_str]["name"] = format_user(winner)  # оновлюємо ім'я

    save_data(data)

    # Анімована відповідь
    suspense = await message.reply("🎲 Визначаємо підора дня...")
    await asyncio.sleep(1.5)
    await suspense.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await suspense.edit_text(
        f"🍑 <b>Підор дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🏆\n\n"
        f"Вітаємо з «перемогою»! 🎉",
        parse_mode="HTML"
    )


async def cmd_krasavchyk(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Команда тільки для груп!")
        return

    chat_id = message.chat.id
    today_key = today()
    data = load_data()
    day_data = data.get(f"day_{chat_id}_{today_key}", {})

    # Вже є результат на сьогодні?
    if "krasavchyk" in day_data:
        winner = day_data["krasavchyk"]
        await message.reply(
            f"😎 Красавчик дня вже обраний!\n\n"
            f"Сьогодні це — <b>{winner['name']}</b> 🌟",
            parse_mode="HTML"
        )
        return

    members = await get_members(message.bot, chat_id)
    if len(members) < 2:
        await message.reply("😅 Замало учасників! Потрібно мінімум 2 людини.")
        return

    # Виключаємо вже обраного підора
    pidor_id = day_data.get("pidor", {}).get("id")
    pool = [m for m in members if m["id"] != pidor_id]

    if not pool:
        pool = members

    winner = random.choice(pool)

    day_data["krasavchyk"] = {"id": winner["id"], "name": format_user(winner)}
    data[f"day_{chat_id}_{today_key}"] = day_data

    # Оновлюємо статистику
    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    user_id_str = str(winner["id"])
    if user_id_str not in data[stats_key]:
        data[stats_key][user_id_str] = {"name": format_user(winner), "pidor": 0, "krasavchyk": 0}
    data[stats_key][user_id_str]["krasavchyk"] += 1
    data[stats_key][user_id_str]["name"] = format_user(winner)  # оновлюємо ім'я

    save_data(data)

    suspense = await message.reply("✨ Визначаємо красавчика дня...")
    await asyncio.sleep(1.5)
    await suspense.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await suspense.edit_text(
        f"😎 <b>Красавчик дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🌟\n\n"
        f"Красавчик! Так тримати! 💪",
        parse_mode="HTML"
    )


async def cmd_stats(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Команда тільки для груп!")
        return

    chat_id = message.chat.id
    data = load_data()
    stats = data.get(f"stats_{chat_id}", {})

    if not stats:
        await message.reply("📊 Статистики ще немає. Зіграйте хоча б одну гру!")
        return

    # Сортуємо за кількістю підорів (по спадній), потім красавчиків
    players = list(stats.values())
    players.sort(key=lambda x: (-x.get("pidor", 0), -x.get("krasavchyk", 0)))

    # Топ підорів
    pidor_board = sorted(players, key=lambda x: -x.get("pidor", 0))
    krasavchyk_board = sorted(players, key=lambda x: -x.get("krasavchyk", 0))

    def medal(i):
        return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."

    pidor_lines = []
    for i, p in enumerate(pidor_board):
        if p.get("pidor", 0) > 0:
            pidor_lines.append(f"{medal(i)} {p['name']} — <b>{p['pidor']}</b> раз(и)")

    krasavchyk_lines = []
    for i, p in enumerate(krasavchyk_board):
        if p.get("krasavchyk", 0) > 0:
            krasavchyk_lines.append(f"{medal(i)} {p['name']} — <b>{p['krasavchyk']}</b> раз(и)")

    text = "📊 <b>Статистика групи</b>\n\n"

    text += "🍑 <b>Топ підорів:</b>\n"
    text += ("\n".join(pidor_lines) if pidor_lines else "Поки що нікого") + "\n\n"

    text += "😎 <b>Топ красавчиків:</b>\n"
    text += ("\n".join(krasavchyk_lines) if krasavchyk_lines else "Поки що нікого")

    await message.reply(text, parse_mode="HTML")


# ==============================
# ЗАПУСК
# ==============================

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("✅ Бот запущений!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
