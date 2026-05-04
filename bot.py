from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import json
import os

TOKEN = os.getenv("TOKEN")

FILE = "data.json"

# =======================
# 💾 загрузка / сохранение
# =======================

def load():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {
        "deposit": 0,
        "trades": [],
        "week_archive": [],
        "month_archive": []
    }

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load()

# =======================
# 📅 периоды
# =======================

def get_week():
    now = datetime.now()
    return f"{now.year}-W{now.isocalendar()[1]}"

def get_month():
    now = datetime.now()
    return f"{now.year}-{now.month}"

# =======================
# 📱 кнопки
# =======================

menu = ReplyKeyboardMarkup(
    [
        ["💰 Депозит"],
        ["📊 Новая сделка"],
        ["📌 Закрыть сделку"],
        ["📅 Статистика недели", "📆 Статистика месяца"],
        ["🧹 Очистить неделю"]
    ],
    resize_keyboard=True
)

# =======================
# 🚀 старт
# =======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Трейдинг журнал\n\nВыбери действие:",
        reply_markup=menu
    )

# =======================
# 🧠 обработчик
# =======================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data

    text = update.message.text
    step = context.user_data.get("step")

    # =======================
    # 💰 депозит
    # =======================
    if text == "💰 Депозит":
        context.user_data["step"] = "deposit"
        await update.message.reply_text("💰 Введите депозит:")
        return

    if step == "deposit":
        data["deposit"] = float(text)
        save(data)
        context.user_data["step"] = None

        await update.message.reply_text(f"📊 Депозит установлен: {data['deposit']}$")
        return

    # =======================
    # 📊 новая сделка
    # =======================
    if text == "📊 Новая сделка":
        context.user_data["step"] = "risk"
        await update.message.reply_text("⚠️ Введите риск (%):")
        return

    if step == "risk":
        context.user_data["risk"] = float(text)
        context.user_data["step"] = "ticker"
        await update.message.reply_text("📌 Введите тикер:")
        return

    if step == "ticker":
        context.user_data["ticker"] = text
        context.user_data["step"] = "rr"
        await update.message.reply_text("📈 Введите RR:")
        return

    if step == "rr":
        risk = context.user_data["risk"]
        ticker = context.user_data["ticker"]
        rr = float(text)

        trade_id = len(data["trades"]) + 1
        deposit = data["deposit"]

        risk_amount = deposit * risk / 100
        profit = risk_amount * rr

        trade = {
            "id": trade_id,
            "ticker": ticker,
            "risk": risk,
            "rr": rr,
            "risk_amount": risk_amount,
            "profit": profit,
            "result": None,
            "created": datetime.now().isoformat()
        }

        data["trades"].append(trade)
        save(data)

        context.user_data["step"] = None

        await update.message.reply_text(
f"""📊 ПАРАМЕТРЫ СДЕЛКИ #{trade_id}

💰 Депозит: {deposit}$
⚠️ Риск: {risk}% ({risk_amount:.2f}$)
📈 RR: {rr}
📌 Тикер: {ticker}

🟢 Потенциал: +{profit:.2f}$
🔴 Риск: -{risk_amount:.2f}$
"""
        )
        return

    # =======================
    # 📌 закрытие сделки
    # =======================
    if text == "📌 Закрыть сделку":
        open_trades = [t for t in data["trades"] if t["result"] is None]

        if not open_trades:
            await update.message.reply_text("❌ Нет открытых сделок")
            return

        msg = "📌 Выбери сделку:\n"
        for t in open_trades:
            msg += f"{t['id']}) {t['ticker']}\n"

        context.user_data["step"] = "close_id"
        await update.message.reply_text(msg)
        return

    if step == "close_id":
        trade_id = int(text)
        context.user_data["close_id"] = trade_id
        context.user_data["step"] = "close_pnl"
        await update.message.reply_text("💰 Введи PnL ($):")
        return

    if step == "close_pnl":
        pnl = float(text)
        trade_id = context.user_data["close_id"]

        for t in data["trades"]:
            if t["id"] == trade_id:
                t["result"] = pnl
                data["deposit"] += pnl
                break

        save(data)
        context.user_data["step"] = None

        await update.message.reply_text(
f"""📌 Сделка #{trade_id} закрыта

💰 PnL: {pnl:.2f}$
💰 Новый депозит: {data['deposit']:.2f}$
"""
        )
        return

    # =======================
    # 📅 статистика недели
    # =======================
    if text == "📅 Статистика недели":
        week = get_week()

        trades = [t for t in data["trades"] if t["result"] is not None]

        wins = len([t for t in trades if t["result"] > 0])
        losses = len([t for t in trades if t["result"] <= 0])

        total = len(trades)
        winrate = (wins / total * 100) if total else 0

        avg = sum(t["result"] for t in trades) / total if total else 0

        await update.message.reply_text(
f"""📅 НЕДЕЛЯ {week}

📊 Сделок: {total}
🟢 Win: {wins}
🔴 Loss: {losses}

🏆 Winrate: {winrate:.1f}%
💰 Средний результат: {avg:.2f}$
💰 Депозит: {data['deposit']:.2f}$
"""
        )
        return

    # =======================
    # 📆 статистика месяца
    # =======================
    if text == "📆 Статистика месяца":
        month = get_month()

        trades = [t for t in data["trades"] if t["result"] is not None]

        wins = len([t for t in trades if t["result"] > 0])
        losses = len([t for t in trades if t["result"] <= 0])

        total = len(trades)
        winrate = (wins / total * 100) if total else 0

        avg = sum(t["result"] for t in trades) / total if total else 0

        await update.message.reply_text(
f"""📆 МЕСЯЦ {month}

📊 Сделок: {total}
🟢 Win: {wins}
🔴 Loss: {losses}

🏆 Winrate: {winrate:.1f}%
💰 Средний результат: {avg:.2f}$
💰 Депозит: {data['deposit']:.2f}$
"""
        )
        return

    # =======================
    # 🧹 очистка недели
    # =======================
    if text == "🧹 Очистить неделю":
        data["trades"] = []
        save(data)
        await update.message.reply_text("🧹 Неделя очищена")
        return


# =======================
# 🚀 запуск
# =======================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
