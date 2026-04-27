import asyncio
import random
import json
import os
from datetime import date
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, KICKED, LEFT, MEMBER, RESTRICTED

# ==============================
# НАЛАШТУВАННЯ
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

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


def format_user(member: dict) -> str:
    if member.get("username"):
        return f"@{member['username']}"
    return member.get("first_name", "Невідомий")


def get_members(chat_id: int) -> list[dict]:
    data = load_data()
    return data.get(f"members_{chat_id}", [])


def remove_member(chat_id: int, user_id: int) -> dict | None:
    """Видаляє учасника з пулу. Повертає видаленого або None."""
    data = load_data()
    chat_key = f"members_{chat_id}"
    members = data.get(chat_key, [])
    found = next((m for m in members if m["id"] == user_id), None)
    if found:
        data[chat_key] = [m for m in members if m["id"] != user_id]
        save_data(data)
    return found


# ==============================
# АВТО-ВИДАЛЕННЯ при виході/кіку
# ==============================

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED | LEFT))
async def on_member_left(event: ChatMemberUpdated):
    """Спрацьовує коли учасника видалили або він сам вийшов."""
    user = event.old_chat_member.user
    if user.is_bot:
        return

    removed = remove_member(event.chat.id, user.id)
    if removed:
        name = format_user(removed)
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
    elif cmd == "/krasavchyk":
        await cmd_krasavchyk(message)
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
        "😎 /krasavchyk — обрати красавчика дня\n\n"
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

    krasavchyk_id = day_data.get("krasavchyk", {}).get("id")
    pool = [m for m in members if m["id"] != krasavchyk_id] or members
    winner = random.choice(pool)

    day_data["pidor"] = {"id": winner["id"], "name": format_user(winner)}
    data[day_key] = day_data

    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    uid = str(winner["id"])
    if uid not in data[stats_key]:
        data[stats_key][uid] = {"name": format_user(winner), "pidor": 0, "krasavchyk": 0}
    data[stats_key][uid]["pidor"] += 1
    data[stats_key][uid]["name"] = format_user(winner)
    save_data(data)

    msg = await message.reply("🎲 Визначаємо підора дня...")
    await asyncio.sleep(1.5)
    await msg.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await msg.edit_text(
        f"🍑 <b>Підор дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🏆\n\n"
        f"Вітаємо з «перемогою»! 🎉",
        parse_mode="HTML"
    )


async def cmd_krasavchyk(message: Message):
    chat_id = message.chat.id
    today_key = today()
    data = load_data()
    day_key = f"day_{chat_id}_{today_key}"
    day_data = data.get(day_key, {})

    if "krasavchyk" in day_data:
        await message.reply(
            f"😎 Красавчик дня вже обраний!\n\n"
            f"Сьогодні це — <b>{day_data['krasavchyk']['name']}</b> 🌟",
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

    day_data["krasavchyk"] = {"id": winner["id"], "name": format_user(winner)}
    data[day_key] = day_data

    stats_key = f"stats_{chat_id}"
    if stats_key not in data:
        data[stats_key] = {}
    uid = str(winner["id"])
    if uid not in data[stats_key]:
        data[stats_key][uid] = {"name": format_user(winner), "pidor": 0, "krasavchyk": 0}
    data[stats_key][uid]["krasavchyk"] += 1
    data[stats_key][uid]["name"] = format_user(winner)
    save_data(data)

    msg = await message.reply("✨ Визначаємо красавчика дня...")
    await asyncio.sleep(1.5)
    await msg.edit_text("🔄 Крутимо барабан...")
    await asyncio.sleep(1.5)
    await msg.edit_text(
        f"😎 <b>Красавчик дня визначений!</b>\n\n"
        f"Сьогодні цей титул отримує — <b>{format_user(winner)}</b> 🌟\n\n"
        f"Красавчик! Так тримати! 💪",
        parse_mode="HTML"
    )


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
    krasavchyk_board = sorted(players, key=lambda x: -x.get("krasavchyk", 0))

    pidor_lines = [
        f"{medal(i)} {p['name']} — <b>{p['pidor']}</b> раз(и)"
        for i, p in enumerate(pidor_board) if p.get("pidor", 0) > 0
    ]
    krasavchyk_lines = [
        f"{medal(i)} {p['name']} — <b>{p['krasavchyk']}</b> раз(и)"
        for i, p in enumerate(krasavchyk_board) if p.get("krasavchyk", 0) > 0
    ]

    text = "📊 <b>Статистика групи</b>\n\n"
    text += "🍑 <b>Топ підорів:</b>\n"
    text += ("\n".join(pidor_lines) if pidor_lines else "Поки що нікого") + "\n\n"
    text += "😎 <b>Топ красавчиків:</b>\n"
    text += "\n".join(krasavchyk_lines) if krasavchyk_lines else "Поки що нікого"

    await message.reply(text, parse_mode="HTML")


# ==============================
# ЗАПУСК
# ==============================

async def main():
    bot = Bot(token=BOT_TOKEN)
    # Підписуємось на оновлення учасників чату (потрібно для авто-видалення)
    await bot.get_updates(allowed_updates=["message", "chat_member"])
    print("✅ Бот запущений!")
    await dp.start_polling(bot, allowed_updates=["message", "chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
