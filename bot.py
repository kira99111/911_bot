from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import os
import json

TOKEN = os.getenv("TOKEN")
FILE = "data.json"


# ===== STORAGE =====
def load():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {
        "deposit": None,
        "trades": [],
        "week_archive": [],
        "month_archive": [],
        "week_id": "",
        "month_id": ""
    }


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load()


# ===== DATE =====
def get_date():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y %B W{week} %d")


def get_week():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y-%m-W{week}")


def get_month():
    return datetime.now().strftime("%Y-%m")


# ===== CHECK PERIOD =====
def check_period():
    global data

    week_now = get_week()
    month_now = get_month()

    if not data["week_id"]:
        data["week_id"] = week_now

    if not data["month_id"]:
        data["month_id"] = month_now

    # новая неделя
    if data["week_id"] != week_now:
        data["week_archive"].append({
            "week": data["week_id"],
            "trades": data["trades"]
        })
        data["trades"] = []
        data["deposit"] = None
        data["week_id"] = week_now

    # новый месяц
    if data["month_id"] != month_now:
        data["month_archive"].append({
            "month": data["month_id"],
            "weeks": data["week_archive"]
        })
        data["week_archive"] = []
        data["month_id"] = month_now

    save(data)


# ===== MENU =====
menu = ReplyKeyboardMarkup(
    [
        ["💰 Депозит", "📊 Сделка"],
        ["📌 Закрыть", "📈 Статистика"],
        ["🧹 Отменить", "🗑 Очистить неделю"]
    ],
    resize_keyboard=True
)


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_period()

    await update.message.reply_text(
        f"🤖 Trading Bot\n\n📅 {get_date()}",
        reply_markup=menu
    )


# ===== HANDLER =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data

    check_period()

    text = update.message.text
    step = context.user_data.get("step")

    # ===== ДЕПОЗИТ =====
    if text == "💰 Депозит":
        context.user_data["step"] = "deposit"
        await update.message.reply_text("Введи депозит:")
        return

    if step == "deposit":
        data["deposit"] = float(text)
        save(data)
        context.user_data["step"] = None

        await update.message.reply_text(f"💰 Депозит: {data['deposit']}$")
        return

    # ===== СДЕЛКА =====
    if text == "📊 Сделка":
        if not data["deposit"]:
            await update.message.reply_text("Сначала задай депозит")
            return

        context.user_data["step"] = "risk"
        await update.message.reply_text("Риск %:")
        return

    if step == "risk":
        context.user_data["risk"] = float(text)
        context.user_data["step"] = "rr"
        await update.message.reply_text("RR:")
        return

    if step == "rr":
        context.user_data["rr"] = float(text)
        context.user_data["step"] = "ticker"
        await update.message.reply_text("Тикер:")
        return

    if step == "ticker":
        deposit = data["deposit"]
        risk = context.user_data["risk"]
        rr = context.user_data["rr"]

        risk_amount = deposit * risk / 100
        profit = risk_amount * rr

        trade = {
            "id": len(data["trades"]) + 1,
            "date": get_date(),
            "risk_amount": risk_amount,
            "profit_plan": profit,
            "result": None
        }

        data["trades"].append(trade)
        save(data)

        open_trades = len([t for t in data["trades"] if t["result"] is None])

        msg = (
            f"📊 Сделка #{trade['id']}\n\n"
            f"📅 {trade['date']}\n"
            f"💰 депозит: {deposit}$\n\n"
            f"📈 +{profit:.2f}$\n"
            f"📉 -{risk_amount:.2f}$\n\n"
            f"📌 открытых: {open_trades}\n"
            f"⏳ в процессе"
        )

        context.user_data["step"] = None
        await update.message.reply_text(msg)
        return

    # ===== ЗАКРЫТИЕ =====
    if text == "📌 Закрыть":
        context.user_data["step"] = "close_id"
        await update.message.reply_text("ID сделки:")
        return

    if step == "close_id":
        context.user_data["close_id"] = int(text)
        context.user_data["step"] = "close_result"
        await update.message.reply_text("PnL:")
        return

    if step == "close_result":
        trade_id = context.user_data["close_id"]
        pnl = float(text)

        for t in data["trades"]:
            if t["id"] == trade_id:
                t["result"] = pnl

                r = pnl / t["risk_amount"] if t["risk_amount"] else 0

                await update.message.reply_text(
                    f"📌 Trade #{trade_id}\n\n"
                    f"💰 {pnl:.2f}$\n"
                    f"📊 {r:.2f}R"
                )
                break

        save(data)
        context.user_data["step"] = None
        return

    # ===== СТАТИСТИКА =====
    if text == "📈 Статистика":
        closed = [t for t in data["trades"] if t["result"] is not None]

        if not closed:
            await update.message.reply_text("нет данных")
            return

        wins = [t for t in closed if t["result"] > 0]
        losses = [t for t in closed if t["result"] <= 0]

        winrate = len(wins) / len(closed) * 100
        avg_r = sum((t["result"]/t["risk_amount"]) for t in closed) / len(closed)

        await update.message.reply_text(
            f"📊 Неделя\n\n"
            f"🏆 winrate: {winrate:.1f}%\n"
            f"🟢 wins: {len(wins)}\n"
            f"🔴 losses: {len(losses)}\n"
            f"📊 avg R: {avg_r:.2f}"
        )
        return

    # ===== ОТМЕНА =====
    if text == "🧹 Отменить":
        if data["trades"]:
            removed = data["trades"].pop()
            save(data)
            await update.message.reply_text(f"Удалена сделка #{removed['id']}")
        else:
            await update.message.reply_text("Нечего удалять")
        return

    # ===== ОЧИСТКА НЕДЕЛИ =====
    if text == "🗑 Очистить неделю":
        data["week_archive"] = []
        save(data)
        await update.message.reply_text("Архив недели очищен")
        return


# ===== RUN =====
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
