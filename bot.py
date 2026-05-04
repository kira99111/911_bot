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
        return json.load(open(FILE))
    return {
        "deposit": 0,
        "trades": [],
        "counter": 0,
        "active": None
    }


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load()
state = {}


# =========================
# MENU
# =========================

menu = ReplyKeyboardMarkup([
    ["💰 Депозит"],
    ["➕ Сделка", "📌 Закрыть"],
    ["📊 Неделя", "📆 Месяц"]
], resize_keyboard=True)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Trading Bot", reply_markup=menu)


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

        await update.message.reply_text(f"💰 Депозит: {data['deposit']}$")
        return


    # =====================
    # СДЕЛКА
    # =====================
    if text == "➕ Сделка":

        if data["active"]:
            await update.message.reply_text("⚠️ Уже есть активная сделка")
            return

        state["step"] = "risk"
        await update.message.reply_text("Введите риск %:")
        return


    if state.get("step") == "risk":
        state["risk"] = float(text)
        state["step"] = "rr"
        await update.message.reply_text("Введите RR:")
        return


    if state.get("step") == "rr":
        state["rr"] = float(text)
        state["step"] = "pair"
        await update.message.reply_text("Введите тикер:")
        return


    if state.get("step") == "pair":
        state["pair"] = text
        state["step"] = "entry"
        await update.message.reply_text("ТВХ:")
        return


    if state.get("step") == "entry":
        state["entry"] = float(text)
        state["step"] = "stop"
        await update.message.reply_text("Стоп:")
        return


    if state.get("step") == "stop":
        state["stop"] = float(text)
        state["step"] = "take"
        await update.message.reply_text("Тейк:")
        return


    if state.get("step") == "take":

        data["counter"] += 1

        risk_amount = data["deposit"] * state["risk"] / 100

        # расстояние риска
        risk_distance = abs(state["entry"] - state["stop"])
        reward_distance = abs(state["take"] - state["entry"])

        position = min(data["deposit"] * 0.2, risk_amount * 10)

        leverage = min(15, (position / risk_amount) if risk_amount else 1)

        trade = {
            "id": data["counter"],
            "pair": state["pair"],
            "risk": state["risk"],
            "rr": state["rr"],
            "entry": state["entry"],
            "stop": state["stop"],
            "take": state["take"],
            "risk_amount": risk_amount,
            "position": position,
            "leverage": leverage,
            "created": str(datetime.now()),
            "status": "open"
        }

        data["active"] = trade
        save(data)
        state.clear()

        await update.message.reply_text(
f"""📌 Trade #{trade['id']} ({trade['pair']})

💰 риск: {risk_amount:.2f}$
📊 позиция: {position:.2f}$
⚡ плечо: x{leverage:.1f}

📍 ТВХ: {trade['entry']}
🛑 SL: {trade['stop']}
🎯 TP: {trade['take']}

📊 RR: {trade['rr']}"""
        )
        return


    # =====================
    # ЗАКРЫТИЕ
    # =====================
    if text == "📌 Закрыть":

        if not data["active"]:
            await update.message.reply_text("Нет активной сделки")
            return

        state["step"] = "close"
        await update.message.reply_text("Введите PnL (+/- $):")
        return


    if state.get("step") == "close":

        trade = data["active"]
        pnl = float(text)

        trade["pnl"] = pnl
        trade["status"] = "closed"
        trade["closed"] = str(datetime.now())

        # 💰 ОБНОВЛЕНИЕ ДЕПОЗИТА
        data["deposit"] += pnl

        data["trades"].append(trade)
        data["active"] = None

        save(data)
        state.clear()

        await update.message.reply_text(
f"""📌 Закрыто Trade #{trade['id']}

💰 PnL: {pnl}$  
💰 депозит: {data['deposit']}$"""
        )
        return


    # =====================
    # НЕДЕЛЯ
    # =====================
    if text == "📊 Неделя":

        trades = data["trades"]

        if not trades:
            await update.message.reply_text("Нет сделок")
            return

        wins = len([t for t in trades if t.get("pnl", 0) > 0])
        losses = len([t for t in trades if t.get("pnl", 0) < 0])

        pnl = sum(t.get("pnl", 0) for t in trades)
        winrate = (wins / len(trades)) * 100

        await update.message.reply_text(
f"""📊 НЕДЕЛЯ

📌 сделок: {len(trades)}
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
    if text == "📆 Месяц":

        trades = data["trades"]

        if not trades:
            await update.message.reply_text("Нет сделок")
            return

        wins = len([t for t in trades if t.get("pnl", 0) > 0])
        losses = len([t for t in trades if t.get("pnl", 0) < 0])

        pnl = sum(t.get("pnl", 0) for t in trades)
        winrate = (wins / len(trades)) * 100

        await update.message.reply_text(
f"""📆 МЕСЯЦ

📌 сделок: {len(trades)}
🟢 +: {wins}
🔴 -: {losses}

📈 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$
💰 депозит: {data['deposit']}$"""
        )
        return


# =========================
# RUN
# =========================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
