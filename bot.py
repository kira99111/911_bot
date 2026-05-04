from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import json
import os

TOKEN = os.getenv("TOKEN")

FILE_WEEK = "week.json"
FILE_ARCHIVE = "archive.json"
FILE_MONTH = "month.json"

# =========================
# TIME
# =========================

def now_date():
    dt = datetime.now()
    week = (dt.day - 1) // 7 + 1
    return {
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "week": week,
        "label": f"{dt.year}-{dt.month:02d}-W{week}"
    }

# =========================
# STORAGE
# =========================

def load(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return []

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

week_log = load(FILE_WEEK)
archive = load(FILE_ARCHIVE)
month_log = load(FILE_MONTH)

state = {}

deposit = {"value": None}

# =========================
# BUTTONS
# =========================

menu = ReplyKeyboardMarkup(
    [
        ["💰 Депозит", "➕ Сделка"],
        ["📌 Закрыть", "📊 Статистика"],
        ["📂 Архив", "🧹 Неделя"],
        ["↩️ Отмена"]
    ],
    resize_keyboard=True
)

# =========================
# HELPERS
# =========================

def count_open():
    return len([t for t in week_log if t["status"] == "open"])

def next_trade_id():
    return len(week_log) + 1

def calc_leverage(risk_pct):
    if risk_pct <= 3:
        return 10
    elif risk_pct <= 5:
        return 12
    elif risk_pct <= 7:
        return 15
    return 15

def calc_position(deposit_value, risk_pct):
    risk_money = deposit_value * risk_pct / 100

    # ограничение 30%
    max_allowed = deposit_value * 0.30
    position = min(risk_money * 10, max_allowed)

    return risk_money, position

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = now_date()

    await update.message.reply_text(
        f"""🤖 Trading Bot

📅 {d['year']}-M{d['month']}-W{d['week']}

💰 Депозит: {deposit['value'] if deposit['value'] else 'не задан'}

📌 Открытых сделок: {count_open()}
""",
        reply_markup=menu
    )

# =========================
# MAIN HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global week_log, archive, month_log, deposit

    text = update.message.text

    # =================
    # DEPOSIT
    # =================
    if text == "💰 Депозит":
        state["step"] = "deposit"
        await update.message.reply_text("Введи депозит:")
        return

    if state.get("step") == "deposit":
        deposit["value"] = float(text)
        state["step"] = None

        await update.message.reply_text(
            f"💰 Депозит установлен: {deposit['value']}$"
        )
        return

    # =================
    # NEW TRADE
    # =================
    if text == "➕ Сделка":
        if not deposit["value"]:
            await update.message.reply_text("Сначала задай депозит")
            return

        state["step"] = "risk"
        await update.message.reply_text("📊 Риск %:")
        return

    # risk
    if state.get("step") == "risk":
        state["risk"] = float(text)
        state["step"] = "pair"
        await update.message.reply_text("📌 Тикер:")
        return

    # pair
    if state.get("step") == "pair":
        state["pair"] = text

        risk_money, position = calc_position(deposit["value"], state["risk"])
        lev = calc_leverage(state["risk"])

        trade = {
            "id": next_trade_id(),
            "pair": state["pair"],
            "risk_pct": state["risk"],
            "risk_money": risk_money,
            "position": position,
            "leverage": lev,
            "start_deposit": deposit["value"],
            "result": None,
            "status": "open",
            "time_open": str(datetime.now())
        }

        week_log.append(trade)
        save(FILE_WEEK, week_log)

        state.clear()

        await update.message.reply_text(
f"""📊 СДЕЛКА #{trade['id']}

📌 {trade['pair']}
💰 депозит: {deposit['value']:.2f}$
⚠️ риск: {trade['risk_pct']:.2f}%
💸 риск $: {risk_money:.2f}
📦 сумма: {position:.2f}$
📊 плечо: x{lev}

📌 открытых сделок: {count_open()}
"""
        )
        return

    # =================
    # CLOSE TRADE
    # =================
    if text == "📌 Закрыть":
        open_trades = [t for t in week_log if t["status"] == "open"]

        if not open_trades:
            await update.message.reply_text("Нет открытых сделок")
            return

        state["step"] = "close_id"

        msg = "Выбери номер сделки:\n\n"
        for t in open_trades:
            msg += f"#{t['id']} {t['pair']} | депозит {t['start_deposit']}$\n"

        await update.message.reply_text(msg)
        return

    if state.get("step") == "close_id":
        trade_id = int(text)

        state["close_id"] = trade_id
        state["step"] = "close_pnl"

        await update.message.reply_text("💰 PnL ($):")
        return

    if state.get("step") == "close_pnl":
        pnl = float(text)

        for t in week_log:
            if t["id"] == state["close_id"]:
                t["result"] = pnl
                t["status"] = "closed"
                break

        deposit["value"] += pnl

        save(FILE_WEEK, week_log)

        state.clear()

        await update.message.reply_text(
f"""📌 Trade #{t['id']}

💰 PnL: {pnl:.2f}$
📊 R: {pnl / t['risk_money']:.2f}R
💰 депозит: {deposit['value']:.2f}$
"""
        )
        return

    # =================
    # STATS
    # =================
    if text == "📊 Статистика":
        closed = [t for t in week_log if t["status"] == "closed"]

        wins = len([t for t in closed if t["result"] > 0])
        losses = len([t for t in closed if t["result"] <= 0])

        pnl = sum(t["result"] for t in closed)

        winrate = (wins / len(closed) * 100) if closed else 0

        await update.message.reply_text(
f"""📊 СТАТИСТИКА

📈 сделок: {len(week_log)}
📌 закрытых: {len(closed)}

🏆 winrate: {winrate:.1f}%
💰 PnL: {pnl:.2f}$

🟢 wins: {wins}
🔴 losses: {losses}
"""
        )
        return

    # =================
    # RESET WEEK
    # =================
    if text == "🧹 Неделя":
        archive.append(week_log)
        save(FILE_ARCHIVE, archive)

        week_log = []
        save(FILE_WEEK, week_log)

        await update.message.reply_text("Неделя очищена")
        return

    # =================
    # CANCEL
    # =================
    if text == "↩️ Отмена":
        state.clear()
        await update.message.reply_text("Отменено")
        return


# =========================
# RUN
# =========================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
