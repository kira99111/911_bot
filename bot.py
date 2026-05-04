import os
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")
FILE = "bot_data.json"


# ======================
# LOAD / SAVE
# ======================

def load():
    if os.path.exists(FILE):
        return json.load(open(FILE))
    return {
        "deposit": 0,
        "trades": [],
        "counter": 0,
        "week_start": str(datetime.now().date())
    }


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load()
state = {}


# ======================
# MENU
# ======================

menu = ReplyKeyboardMarkup([
    ["💰 Депозит"],
    ["➕ Сделка", "📌 Закрыть"],
    ["📊 Неделя", "📆 Месяц"],
    ["🧹 Очистить неделю"]
], resize_keyboard=True)


# ======================
# START
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Trading Bot", reply_markup=menu)


# ======================
# RESET WEEK
# ======================

def reset_week_if_needed():
    today = datetime.now().date()

    if str(today) != data["week_start"]:
        data["week_start"] = str(today)
        data["trades"] = []
        save(data)


# ======================
# HANDLER
# ======================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    reset_week_if_needed()


    # ======================
    # ДЕПОЗИТ
    # ======================
    if text == "💰 Депозит":
        state["step"] = "deposit"
        await update.message.reply_text("Введите депозит:")
        return

    if state.get("step") == "deposit":
        data["deposit"] = float(text)
        save(data)
        state.clear()
        await update.message.reply_text(f"💰 Депозит: {data['deposit']}$")
        return


    # ======================
    # СОЗДАНИЕ СДЕЛКИ
    # ======================
    if text == "➕ Сделка":
        state["step"] = "risk"
        await update.message.reply_text("Риск %:")
        return

    if state.get("step") == "risk":
        state["risk"] = float(text)
        state["step"] = "ticker"
        await update.message.reply_text("Тикер:")
        return

    if state.get("step") == "ticker":

        data["counter"] += 1

        trade = {
            "id": data["counter"],
            "risk": state["risk"],
            "ticker": text,
            "status": "open",
            "created": str(datetime.now())
        }

        data["trades"].append(trade)
        save(data)

        state.clear()

        await update.message.reply_text(
f"📌 Сделка #{trade['id']} открыта\n📊 {trade['ticker']}"
        )
        return


    # ======================
    # ЗАКРЫТИЕ
    # ======================
    if text == "📌 Закрыть":
        state["step"] = "close_id"
        await update.message.reply_text("Номер сделки:")
        return

    if state.get("step") == "close_id":
        state["id"] = int(text)
        state["step"] = "pnl"
        await update.message.reply_text("PnL ($):")
        return

    if state.get("step") == "pnl":

        trade_id = state["id"]
        pnl = float(text)

        for t in data["trades"]:
            if t["id"] == trade_id and t["status"] == "open":
                t["status"] = "closed"
                t["pnl"] = pnl
                t["closed"] = str(datetime.now())
                break

        save(data)
        state.clear()

        await update.message.reply_text(f"📌 Сделка #{trade_id} закрыта\n💰 PnL: {pnl}$")
        return


    # ======================
    # НЕДЕЛЯ
    # ======================
    if text == "📊 Неделя":

        closed = [t for t in data["trades"] if t.get("status") == "closed"]

        if not closed:
            await update.message.reply_text("Нет данных")
            return

        wins = len([t for t in closed if t["pnl"] > 0])
        losses = len([t for t in closed if t["pnl"] < 0])

        winrate = (wins / len(closed)) * 100
        pnl = sum(t["pnl"] for t in closed)

        rr_list = []
        for t in closed:
            risk_amount = data["deposit"] * (t["risk"] / 100)
            rr = t["pnl"] / risk_amount if risk_amount else 0
            rr_list.append(rr)

        avg_rr = sum(rr_list) / len(rr_list)

        await update.message.reply_text(
f"""📊 НЕДЕЛЯ

📌 сделок: {len(closed)}
🟢 win: {wins}
🔴 loss: {losses}

📈 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$

📊 Avg RR: {avg_rr:.2f}"""
        )
        return


    # ======================
    # МЕСЯЦ (упрощённо = все сделки)
    # ======================
    if text == "📆 Месяц":

        closed = [t for t in data["trades"] if t.get("status") == "closed"]

        if not closed:
            await update.message.reply_text("Нет данных")
            return

        wins = len([t for t in closed if t["pnl"] > 0])
        losses = len([t for t in closed if t["pnl"] < 0])

        winrate = (wins / len(closed)) * 100
        pnl = sum(t["pnl"] for t in closed)

        rr_list = []
        for t in closed:
            risk_amount = data["deposit"] * (t["risk"] / 100)
            rr = t["pnl"] / risk_amount if risk_amount else 0
            rr_list.append(rr)

        avg_rr = sum(rr_list) / len(rr_list)

        await update.message.reply_text(
f"""📆 МЕСЯЦ

📌 сделок: {len(closed)}
🟢 win: {wins}
🔴 loss: {losses}

📈 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$

📊 Avg RR: {avg_rr:.2f}"""
        )
        return


    # ======================
    # ОЧИСТКА НЕДЕЛИ
    # ======================
    if text == "🧹 Очистить неделю":
        data["trades"] = []
        save(data)
        await update.message.reply_text("🧹 Неделя очищена")
        return


# ======================
# RUN
# ======================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
