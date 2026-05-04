import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")

FILE = "data.json"


# =========================
# DATA
# =========================

def load():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)

    return {
        "deposit": 0,
        "trade_counter": 0,
        "active_trade": None,
        "week": [],
        "month": []
    }


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load()
state = {}


# =========================
# KEYBOARD
# =========================

def get_menu():
    buttons = [
        ["💰 Депозит", "🧹 Очистить депозит"],
        ["➕ Сделка", "📌 Закрыть сделку"],
        ["📊 Неделя", "📅 Месяц"],
        ["🧾 Очистить неделю", "🧾 Очистить месяц"]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 ТРЕЙДИНГ БОТ",
        reply_markup=get_menu()
    )


# =========================
# HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text


    # =====================
    # ДЕПОЗИТ
    # =====================
    if text == "💰 Депозит":
        state["step"] = "deposit"
        await update.message.reply_text("Введите депозит:")
        return

    if state.get("step") == "deposit":
        data["deposit"] = float(text)
        state.clear()
        save(data)

        await update.message.reply_text(f"💰 Депозит установлен: {data['deposit']}$")
        return


    # =====================
    # СОЗДАТЬ СДЕЛКУ
    # =====================
    if text == "➕ Сделка":

        if data["active_trade"]:
            await update.message.reply_text("⚠️ Уже есть активная сделка")
            return

        state["step"] = "pair"
        await update.message.reply_text("Введите тикер:")
        return


    if state.get("step") == "pair":
        data["trade_counter"] += 1

        trade = {
            "id": data["trade_counter"],
            "pair": text,
            "created": str(datetime.now()),
            "status": "open"
        }

        data["active_trade"] = trade
        state.clear()
        save(data)

        await update.message.reply_text(
            f"📌 Сделка #{trade['id']} ({trade['pair']}) в процессе"
        )
        return


    # =====================
    # ЗАКРЫТИЕ СДЕЛКИ
    # =====================
    if text == "📌 Закрыть сделку":

        trade = data["active_trade"]

        if not trade:
            await update.message.reply_text("Нет активной сделки")
            return

        state["step"] = "close"
        await update.message.reply_text("Введите результат сделки (+ или - $):")
        return


    if state.get("step") == "close":
        trade = data["active_trade"]

        result = float(text)

        trade["result"] = result
        trade["closed"] = str(datetime.now())
        trade["status"] = "closed"

        # 💰 обновление депозита
        data["deposit"] += result

        # 📊 в архив
        data["week"].append(trade)
        data["month"].append(trade)

        data["active_trade"] = None

        state.clear()
        save(data)

        await update.message.reply_text(
            f"📌 Сделка закрыта\n💰 PnL: {result}$\n💰 Новый депозит: {data['deposit']}$"
        )
        return


    # =====================
    # НЕДЕЛЯ
    # =====================
    if text == "📊 Неделя":
        trades = data["week"]

        if not trades:
            await update.message.reply_text("Нет сделок")
            return

        wins = len([t for t in trades if t.get("result", 0) > 0])
        losses = len([t for t in trades if t.get("result", 0) < 0])

        total = len(trades)
        pnl = sum(t.get("result", 0) for t in trades)

        winrate = (wins / total) * 100 if total else 0

        await update.message.reply_text(
f"""📊 НЕДЕЛЯ

📌 сделок: {total}
🟢 +: {wins}
🔴 -: {losses}

📈 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$
💰 депозит: {data['deposit']}$"""
        )
        return


    # =====================
    # МЕСЯЦ
    # =====================
    if text == "📅 Месяц":
        trades = data["month"]

        if not trades:
            await update.message.reply_text("Нет сделок")
            return

        wins = len([t for t in trades if t.get("result", 0) > 0])
        losses = len([t for t in trades if t.get("result", 0) < 0])

        total = len(trades)
        pnl = sum(t.get("result", 0) for t in trades)

        winrate = (wins / total) * 100 if total else 0

        await update.message.reply_text(
f"""📅 МЕСЯЦ

📌 сделок: {total}
🟢 +: {wins}
🔴 -: {losses}

📈 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$
💰 депозит: {data['deposit']}$"""
        )
        return


    # =====================
    # ОЧИСТКА
    # =====================
    if text == "🧹 Очистить депозит":
        data["deposit"] = 0
        save(data)
        await update.message.reply_text("Депозит очищен")
        return

    if text == "🧾 Очистить неделю":
        data["week"] = []
        save(data)
        await update.message.reply_text("Неделя очищена")
        return

    if text == "🧾 Очистить месяц":
        data["month"] = []
        save(data)
        await update.message.reply_text("Месяц очищен")
        return


# =========================
# RUN
# =========================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
