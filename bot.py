from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import json
import os
import matplotlib.pyplot as plt

# 🔑 токен берётся из Railway (Environment Variables)
TOKEN = os.getenv("TOKEN")

FILE = "journal.json"
ARCHIVE = "archive.json"

# 📅 неделя (год + месяц + неделя месяца)
def current_week():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y %B W{week}")

# 💾 работа с файлами
def load(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return []

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

weekly_log = load(FILE)
archive_log = load(ARCHIVE)
week_id = current_week()

# 🔄 смена недели
def check_week():
    global weekly_log, archive_log, week_id

    now = current_week()

    if now != week_id:
        archive_log.append({
            "week": week_id,
            "trades": weekly_log
        })

        save(ARCHIVE, archive_log)

        weekly_log = []
        save(FILE, weekly_log)

        week_id = now

# 📱 кнопки
menu = ReplyKeyboardMarkup(
    [
        ["📊 Calc", "📅 Week"],
        ["📌 Close trade", "📊 Stats"],
        ["📂 Archive", "📈 Equity"],
        ["🧹 Reset"]
    ],
    resize_keyboard=True
)

# 🟢 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_week()

    await update.message.reply_text(
        f"""🤖 Trading Bot

📅 {week_id}

Выбери действие:""",
        reply_markup=menu
    )

# 🧠 основной обработчик
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global weekly_log

    check_week()

    text = update.message.text
    step = context.user_data.get("step")

    # 📊 calc
    if text == "📊 Calc":
        context.user_data["step"] = "deposit"
        await update.message.reply_text("💰 депозит:")
        return

    # 📅 week
    if text == "📅 Week":
        closed = [t for t in weekly_log if t.get("end_deposit") is not None]

        if not weekly_log:
            await update.message.reply_text("нет сделок")
            return

        wins = 0
        losses = 0
        pnl = 0
        risk_sum = 0

        for t in closed:
            trade_pnl = t["end_deposit"] - t["start_deposit"]
            pnl += trade_pnl
            risk_sum += t["risk_amount"]

            if trade_pnl > 0:
                wins += 1
            else:
                losses += 1

        total = len(closed)
        winrate = (wins / total * 100) if total > 0 else 0

        await update.message.reply_text(
f"""📊 НЕДЕЛЯ {week_id}

📈 сделок: {len(weekly_log)}
✅ закрытых: {total}

🏆 winrate: {winrate:.1f}%
🟢 wins: {wins}
🔴 losses: {losses}

💰 риск: {risk_sum:.2f}$
📊 PnL: {pnl:.2f}$

🧠 {"🔥 сильная неделя" if winrate > 55 else "⚠️ слабая"}
"""
        )
        return

    # 📊 stats
    if text == "📊 Stats":
        closed = [t for t in weekly_log if t.get("end_deposit") is not None]

        if not closed:
            await update.message.reply_text("нет данных")
            return

        wins = 0
        losses = 0
        profit = 0
        loss = 0

        for t in closed:
            pnl = t["end_deposit"] - t["start_deposit"]

            if pnl > 0:
                wins += 1
                profit += pnl
            else:
                losses += 1
                loss += abs(pnl)

        winrate = (wins / len(closed)) * 100

        profit_factor = profit / loss if loss != 0 else float("inf")

        expectancy = (profit - loss) / len(closed)

        await update.message.reply_text(
f"""📊 STATISTICS

🏆 winrate: {winrate:.1f}%
📈 profit factor: {profit_factor:.2f}
💰 expectancy: {expectancy:.2f}$

🟢 wins: {wins}
🔴 losses: {losses}
"""
        )
        return

    # 📈 equity graph
    if text == "📈 Equity":
        closed = [t for t in weekly_log if t.get("end_deposit") is not None]

        if not closed:
            await update.message.reply_text("нет данных")
            return

        x = []
        y = []

        for i, t in enumerate(closed):
            x.append(i)
            y.append(t["end_deposit"])

        plt.figure()
        plt.plot(x, y, marker="o")
        plt.title(f"Equity - {week_id}")
        plt.grid()

        path = "equity.png"
        plt.savefig(path)
        plt.close()

        await update.message.reply_photo(photo=open(path, "rb"))
        return

    # 🧹 reset
    if text == "🧹 Reset":
        weekly_log = []
        save(FILE, weekly_log)
        await update.message.reply_text("очищено")
        return

    # 📌 close trade
    if text == "📌 Close trade":
        context.user_data["step"] = "close_id"
        await update.message.reply_text("номер сделки:")
        return

    # 💰 deposit
    if step == "deposit":
        context.user_data["deposit"] = float(text)
        context.user_data["step"] = "risk"
        await update.message.reply_text("риск %:")
        return

    # 📊 create trade
    if step == "risk":
        deposit = context.user_data["deposit"]
        risk = float(text)

        trade = {
            "id": len(weekly_log) + 1,
            "start_deposit": deposit,
            "risk_amount": deposit * risk / 100,
            "end_deposit": None
        }

        weekly_log.append(trade)
        save(FILE, weekly_log)

        context.user_data["step"] = None

        await update.message.reply_text(f"сделка #{trade['id']} создана")
        return

    # 🔢 close trade id
    if step == "close_id":
        context.user_data["close_id"] = int(text)
        context.user_data["step"] = "close_result"
        await update.message.reply_text("PnL в $:")
        return

    # 💰 close result
    if step == "close_result":
        trade_id = context.user_data["close_id"]
        pnl = float(text)

        for t in weekly_log:
            if t["id"] == trade_id:
                t["end_deposit"] = t["start_deposit"] + pnl
                break

        save(FILE, weekly_log)
        context.user_data["step"] = None

        await update.message.reply_text("сделка закрыта")
        return


# 🚀 запуск
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
