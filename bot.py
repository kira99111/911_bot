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
        "start_deposit": None,
        "balance": None,
        "trades": [],
        "archive": [],
        "week": ""
    }


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load()


# ===== DATE =====
def now_str():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y %B W{week} %d %H:%M")


def current_week():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y-%m-W{week}")


# ===== WEEK CHECK =====
def check_week():
    global data

    w = current_week()

    if not data["week"]:
        data["week"] = w

    if data["week"] != w:
        data["archive"].append({
            "week": data["week"],
            "trades": data["trades"],
            "final_balance": data["balance"]
        })
        data["trades"] = []
        data["start_deposit"] = None
        data["balance"] = None
        data["week"] = w

    save(data)


# ===== MENU =====
def get_menu():
    has_open = any(t["result"] is None for t in data["trades"])

    buttons = [
        ["💰 Депозит", "📊 Сделка"],
        ["📈 Статистика"]
    ]

    if has_open:
        buttons.insert(1, ["📌 Закрыть"])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_week()
    await update.message.reply_text(
        f"🤖 Trading Bot\n\n📅 {now_str()}",
        reply_markup=get_menu()
    )


# ===== HANDLER =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data

    check_week()

    text = update.message.text
    step = context.user_data.get("step")

    # ===== ДЕПОЗИТ =====
    if text == "💰 Депозит":
        if data["balance"]:
            await update.message.reply_text(f"Депозит уже задан: {data['balance']}$")
            return

        context.user_data["step"] = "deposit"
        await update.message.reply_text("Введи депозит:")
        return

    if step == "deposit":
        value = float(text)
        data["start_deposit"] = value
        data["balance"] = value

        save(data)
        context.user_data.clear()

        await update.message.reply_text(f"💰 Баланс: {data['balance']}$")
        return

    # ===== СОЗДАНИЕ СДЕЛКИ =====
    if text == "📊 Сделка":
        if not data["balance"]:
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
        context.user_data["ticker"] = text.upper()
        context.user_data["step"] = "calc_position"
        await update.message.reply_text("Рассчитать позицию? (да/нет)")
        return

    # ===== OPTIONAL POSITION =====
    if step == "calc_position":
        if text.lower() == "да":
            context.user_data["step"] = "entry"
            await update.message.reply_text("Вход:")
            return
        else:
            context.user_data["step"] = "create_trade"
            text = None

    if step == "entry":
        context.user_data["entry"] = float(text)
        context.user_data["step"] = "sl"
        await update.message.reply_text("Стоп:")
        return

    if step == "sl":
        context.user_data["sl"] = float(text)
        context.user_data["step"] = "tp"
        await update.message.reply_text("Тейк:")
        return

    if step == "tp":
        context.user_data["tp"] = float(text)
        context.user_data["step"] = "create_trade"

    # ===== CREATE TRADE =====
    if step == "create_trade":
        deposit = data["balance"]
        risk = context.user_data["risk"]
        rr = context.user_data["rr"]
        ticker = context.user_data["ticker"]

        risk_amount = deposit * risk / 100
        profit_plan = risk_amount * rr

        position_info = ""

        if "entry" in context.user_data:
            entry = context.user_data["entry"]
            sl = context.user_data["sl"]

            distance = abs(entry - sl)
            size = risk_amount / distance if distance else 0
            position_value = size * entry

            leverage = position_value / deposit if deposit else 0

            if position_value > deposit * 0.3:
                position_value = deposit * 0.3

            if leverage > 15:
                leverage = 15

            position_info = (
                f"💼 участие: {position_value:.2f}$\n"
                f"⚙️ плечо: {leverage:.2f}x\n\n"
            )

        trade = {
            "ticker": ticker,
            "risk_amount": risk_amount,
            "profit_plan": profit_plan,
            "start_time": now_str(),
            "result": None
        }

        data["trades"].append(trade)
        save(data)

        open_trades = len([t for t in data["trades"] if t["result"] is None])

        msg = (
            f"📊 {ticker}\n\n"
            f"💰 баланс: {deposit:.2f}$\n"
            f"{position_info}"
            f"📈 +{profit_plan:.2f}$\n"
            f"📉 -{risk_amount:.2f}$\n\n"
            f"📌 открытых: {open_trades}\n"
            f"⏳ сделка в процессе"
        )

        context.user_data.clear()
        await update.message.reply_text(msg)
        return

    # ===== ЗАКРЫТИЕ =====
    if text == "📌 Закрыть":
        open_trades = [t for t in data["trades"] if t["result"] is None]

        if not open_trades:
            await update.message.reply_text("Нет открытых сделок")
            return

        keyboard = [[t["ticker"]] for t in open_trades]

        context.user_data["step"] = "close_select"

        await update.message.reply_text(
            "Выбери сделку:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if step == "close_select":
        context.user_data["close_ticker"] = text
        context.user_data["step"] = "close_result"
        await update.message.reply_text("PnL ($):")
        return

    if step == "close_result":
        ticker = context.user_data["close_ticker"]
        pnl = float(text)

        for t in data["trades"]:
            if t["ticker"] == ticker and t["result"] is None:
                t["result"] = pnl
                t["end_time"] = now_str()

                data["balance"] += pnl

                r = pnl / t["risk_amount"] if t["risk_amount"] else 0

                await update.message.reply_text(
                    f"📌 {ticker}\n\n"
                    f"💰 {pnl:.2f}$\n"
                    f"📊 {r:.2f}R\n\n"
                    f"💼 баланс: {data['balance']:.2f}$"
                )
                break

        save(data)
        context.user_data.clear()
        return

    # ===== СТАТИСТИКА =====
    if text == "📈 Статистика":
        closed = [t for t in data["trades"] if t["result"] is not None]

        if not closed:
            await update.message.reply_text("Нет данных")
            return

        wins = [t for t in closed if t["result"] > 0]
        losses = [t for t in closed if t["result"] <= 0]

        winrate = len(wins) / len(closed) * 100

        msg = (
            f"📊 Неделя\n\n"
            f"💰 старт: {data['start_deposit']}$\n"
            f"💼 текущий: {data['balance']:.2f}$\n\n"
            f"🏆 winrate: {winrate:.1f}%\n"
            f"🟢 {len(wins)} / 🔴 {len(losses)}\n\n"
        )

        for t in closed:
            r = t["result"] / t["risk_amount"] if t["risk_amount"] else 0
            msg += f"{t['ticker']} → {r:.2f}R\n"

        await update.message.reply_text(msg)
        return


# ===== RUN =====
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
