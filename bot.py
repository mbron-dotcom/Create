import asyncio
import random
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, KICKED, LEFT, MEMBER

KYIV_TZ = ZoneInfo("Europe/Kyiv")

PIDOR_GIFS = [
    "https://media.giphy.com/media/jF18UtxYIwc6HzajSf/giphy.gif",
    "https://media.giphy.com/media/iRJaqL4fd5sUd88XfN/giphy.gif",
    "https://media.giphy.com/media/G58JDn4zHh9zvVDpkh/giphy.gif",
    "https://media.giphy.com/media/fFI1kP1IP3qCtJLX1B/giphy.gif",
    "https://media.giphy.com/media/UbNcN7UpHDzVcq3acQ/giphy.gif",
]

POTUZHNYK_GIFS = [
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno1.gif",
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno2.gif",
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno3.gif",
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno4.gif",
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno5.gif",
    "https://raw.githubusercontent.com/mbron-dotcom/Create/main/potuzhno6.gif",
]

# ==============================
# НАЛАШТУВАННЯ
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

DATA_FILE = "/app/data/daily_results.json"


# ==============================
# РОБОТА З ДАНИМИ
# ==============================

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def today() -> str:
    return datetime.now(KYIV_TZ).strftime("%Y-%m-%d")


def format_user(member: dict, in_chat: bool = True) -> str:
    if in_chat and member.get("username"):
        return f"@{member['username']}"
    return member.get("first_name", "Невідомий")


def get_members(chat_id: int) -> list[dict]:
    data = load_data()
    return data.get(f"members_{chat_id}", [])


def is_in_chat(chat_id: int, user_id: int) -> bool:
    members = get_members(chat_id)
    return any(m["id"] == user_id for m in members)


def remove_member(chat_id: int, user_id: int) -> dict | None:
    data = load_data()
    chat_key = f"members_{chat_id}"
    members = data.get(chat_key, [])
    found = next((m for m in members if m["id"] == user_id), None)
    if found:
        data[chat_key] = [m for m in members if m["id"] != user_id]
        save_data(data)
    return found


def plural_raz(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "разів"
    r = n % 10
    if r == 1:
        return "раз"
    if 2 <= r <= 4:
        return "рази"
    return "разів"


# ==============================
# АВТО-РЕЄСТРАЦІЯ при вході
# ==============================

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def on_member_joined(event: ChatMemberUpdated):
    user = event.new_chat_member.user
    if user.is_bot:
        return

    chat_id = event.chat.id
    data = load_data()
    chat_key = f"members_{chat_id}"

    if chat_key not in data:
        data[chat_key] = []

    members = data[chat_key]

    if any(m["id"] == user.id for m in members):
        return

    members.append({
        "id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
    })
    data[chat_key] = members
    save_data(data)

    await event.bot.send_message(
        chat_id,
        f"👋 Вітаємо <b>{user.first_name}</b>! Тебе автоматично додано в розіграш 🎲\n"
        f"Всього учасників: <b>{len(members)}</b> 👥",
        parse_mode="HTML"
    )


# ==============================
# АВТО-ВИДАЛЕННЯ при виході/кіку
# ==============================

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED | LEFT))
async def on_member_left(event: ChatMemberUpdated):
    user = event.old_chat_member.user
    if user.is_bot:
        return

    removed = remove_member(event.chat.id, user.id)
    if removed:
        name = format_user(removed, in_chat=False)
        await event.bot.send_message(
            event.chat.id,
            f"👋 <b>{name}</b> покинув чат — автоматично видалений з розіграшу.",
            parse_mode="HTML"
        )


# ==============================
# ХЕНДЛЕР: роутинг команд
# ==============================

@dp.message()
async def router(message: Message):
    if not message.text or not message.text.startswith("/"):
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Бот працює тільки в групах!")
        return

    cmd = message.text.split()[0].lower().split("@")[0]

    if cmd == "/reg":
        await cmd_reg(message)
    elif cmd == "/unreg":
        await cmd_unreg(message)
    elif cmd == "/members":
        await cmd_members(message)
    elif cmd == "/pidor":
        await cmd_pidor(message)
    elif cmd == "/potuzhnyk":
        await cmd_potuzhnyk(message)
    elif cmd == "/stats":
        await cmd_stats(message)
    elif cmd in ("/start", "/help"):
        await cmd_help(message)


# ==============================
# КОМАНДИ
# ==============================

async def cmd_help(message: Message):
    await message.reply(
        "🎲 <b>Бот дня</b>\n\n"
        "<b>Реєстрація:</b>\n"
        "✅ /reg — зареєструватись в розіграші\n"
        "❌ /unreg — вийти з розіграшу\n"
        "👥 /members — список учасників\n\n"
        "<b>Розіграш:</b>\n"
        "🍑 /pidor — обрати підора дня\n"
        "💪 /potuzhnyk — обрати потужніка дня\n\n"
        "<b>Статистика:</b>\n"
        "📊 /stats — хто скільки разів вигравав\n\n"
        "<i>Напиши /reg щоб потрапити в розіграш!\n"
        "Якщо вийдеш з чату — автоматично видалишся з пулу.</i>",
        parse_mode="HTML"
    )


async def cmd_reg(message: Message):
    user = message.from_user
    chat_id = message.chat.id
    data = load_data()
    chat_key = f"members_{chat_id}"

    if chat_key not in data:
        data[chat_key] = []

    members = data[chat_key]

    if any(m["id"] == user.id for m in members):
        await message.reply(f"😏 <b>{user.first_name}</b>, ти вже в грі!", parse_mode="HTML")
        return

    members.append({
        "id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
    })
    data[chat_key] = members
    save_data(data)

    await message.reply(
        f"✅ <b>{user.first_name}</b> зареєструвався в розіграші!\n"
        f"Всього учасників: <b>{len(members)}</b> 👥",
        parse_mode="HTML"
    )


async def cmd_unreg(message: Message):
    user = message.from_user
    chat_id = message.chat.id

    removed = remove_member(chat_id, user.id)

    if not removed:
        await message.reply(f"🤔 <b>{user.first_name}</b>, тебе і так не було в грі!", parse_mode="HTML")
        return

    members = get_members(chat_id)
    await message.reply(
        f"👋 <b>{user.first_name}</b> вийшов з розіграшу.\n"
        f"Залишилось учасників: <b>{len(members)}</b> 👥",
        parse_mode="HTML"
    )


async def cmd_members(message: Message):
    members = get_members(message.chat.id)

    if not members:
        await message.reply("😶 Поки що нікого немає. Напишіть /reg щоб зареєструватись!")
        return

    names = "\n".join(f"• {format_user(m)}" for m in members)
    await message.reply(
        f"👥 <b>Учасники розіграшу ({len(members)}):</b>\n\n{names}",
        parse_mode="HTML"
    )


async def cmd_pidor(message: Message):
    chat_id = message.chat.id
    today_key = today()
    data = load_data()
    day_key = f"day_{chat_id}_{today_key}"
    day_data = data.get(day_key, {})

    if "pidor" in day_data:
        await message.reply(
            f"🍑 Підор дня вже обраний!\n\n"
            f"Сьогодні це — <b>{day_data['pidor']['name']}</b> 🎉",
            parse_mode="HTML"
        )
        return

    members = get_members(chat_id)
    if len(members) < 2:
        await message.reply(
            "😅 Замало учасників!\n"
            "Нехай люди напишуть /reg щоб зареєструватись."
        )
        return

    potuzhnyk_id = day_data.get("potuzhnyk", {}).get("id")
    pool = [m for m in members if m["id"] != potuzhnyk_id] or members
    winner = random.choice(pool)

    day_data["pidor"] = {"id": winner["id"], "name": format_user(winner)}
    data[day_key] = day_data

    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    uid = str(winner["id"])
    if uid not in data[stats_key]:
        data[stats_key][uid] = {"name": format_user(winner), "pidor": 0, "potuzhnyk": 0}
    data[stats_key][uid]["pidor"] += 1
    data[stats_key][uid]["name"] = format_user(winner)
    save_data(data)

    pidor_count = data[stats_key][uid]["pidor"]
    pidor_str = f"{pidor_count} {plural_raz(pidor_count)}"

    msg = await message.reply("🎲 Визначаємо підора дня...")
    await asyncio.sleep(1.5)
    await msg.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await msg.edit_text(
        f"🍑 <b>Підор дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🏆\n\n"
        f"Вітаємо з «перемогою»! 🎉\n\n"
        f"<i>{format_user(winner)} підор підор підорок вже {pidor_str} 👑</i>",
        parse_mode="HTML"
    )
    # ✅ Надсилаємо гіфку як animation через URL-рядок
    await message.answer_animation(animation=random.choice(PIDOR_GIFS))


async def cmd_potuzhnyk(message: Message):
    chat_id = message.chat.id
    today_key = today()
    data = load_data()
    day_key = f"day_{chat_id}_{today_key}"
    day_data = data.get(day_key, {})

    if "potuzhnyk" in day_data:
        await message.reply(
            f"💪 Потужнік дня вже обраний!\n\n"
            f"Сьогодні це — <b>{day_data['potuzhnyk']['name']}</b> 🌟",
            parse_mode="HTML"
        )
        return

    members = get_members(chat_id)
    if len(members) < 2:
        await message.reply(
            "😅 Замало учасників!\n"
            "Нехай люди напишуть /reg щоб зареєструватись."
        )
        return

    pidor_id = day_data.get("pidor", {}).get("id")
    pool = [m for m in members if m["id"] != pidor_id] or members
    winner = random.choice(pool)

    day_data["potuzhnyk"] = {"id": winner["id"], "name": format_user(winner)}
    data[day_key] = day_data

    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    uid = str(winner["id"])
    if uid not in data[stats_key]:
        data[stats_key][uid] = {"name": format_user(winner), "pidor": 0, "potuzhnyk": 0}
    data[stats_key][uid]["potuzhnyk"] += 1
    data[stats_key][uid]["name"] = format_user(winner)
    save_data(data)

    potuzhnyk_count = data[stats_key][uid]["potuzhnyk"]
    potuzhnyk_str = f"{potuzhnyk_count} {plural_raz(potuzhnyk_count)}"

    msg = await message.reply("✨ Визначаємо потужніка дня...")
    await asyncio.sleep(1.5)
    await msg.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await msg.edit_text(
        f"💪 <b>Потужнік дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🌟\n\n"
        f"Потужно! Так тримати! 🔥\n\n"
        f"<i>{format_user(winner)} напотужнічав вже {potuzhnyk_str} 👑</i>",
        parse_mode="HTML"
    )
    # ✅ Надсилаємо гіфку як animation через URL-рядок
    await message.answer_animation(animation=random.choice(POTUZHNYK_GIFS))



async def cmd_stats(message: Message):
    chat_id = message.chat.id
    data = load_data()
    stats = data.get(f"stats_{chat_id}", {})

    if not stats:
        await message.reply("📊 Статистики ще немає. Зіграйте хоча б одну гру!")
        return

    players = list(stats.values())

    def medal(i):
        return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."

    pidor_board = sorted(players, key=lambda x: -x.get("pidor", 0))
    potuzhnyk_board = sorted(players, key=lambda x: -x.get("potuzhnyk", 0))

    def fmt_stats_name(p: dict, chat_id: int) -> str:
        uid = next((k for k, v in data.get(f"stats_{chat_id}", {}).items() if v == p), None)
        if uid and is_in_chat(chat_id, int(uid)):
            return p["name"]
        return p.get("first_name", p["name"])

    pidor_lines = [
        f"{medal(i)} {fmt_stats_name(p, chat_id)} — <b>{p['pidor']}</b> {plural_raz(p['pidor'])}"
        for i, p in enumerate(pidor_board) if p.get("pidor", 0) > 0
    ]
    potuzhnyk_lines = [
        f"{medal(i)} {fmt_stats_name(p, chat_id)} — <b>{p['potuzhnyk']}</b> {plural_raz(p['potuzhnyk'])}"
        for i, p in enumerate(potuzhnyk_board) if p.get("potuzhnyk", 0) > 0
    ]

    text = "📊 <b>Статистика групи</b>\n\n"
    text += "🍑 <b>Топ підорів:</b>\n"
    text += ("\n".join(pidor_lines) if pidor_lines else "Поки що нікого") + "\n\n"
    text += "💪 <b>Топ потужніків:</b>\n"
    text += "\n".join(potuzhnyk_lines) if potuzhnyk_lines else "Поки що нікого"

    await message.reply(text, parse_mode="HTML")


# ==============================
# ЗАПУСК
# ==============================

async def main():
    bot = Bot(token=BOT_TOKEN)

    await bot.set_my_commands([
        types.BotCommand(command="reg",        description="Зареєструватись в розіграші"),
        types.BotCommand(command="unreg",      description="Вийти з розіграшу"),
        types.BotCommand(command="pidor",      description="Обрати підора дня 🍑"),
        types.BotCommand(command="potuzhnyk",  description="Обрати потужніка дня 💪"),
        types.BotCommand(command="stats",      description="Статистика групи 📊"),
        types.BotCommand(command="members",    description="Список учасників 👥"),
        types.BotCommand(command="help",       description="Допомога ❓"),
    ])

    print("✅ Бот запущений!")
    await dp.start_polling(bot, allowed_updates=["message", "chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
