import os
import json
from datetime import datetime
from fastapi import FastAPI, Request
import uvicorn
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")
URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render даст домен

FILE = "journal.json"

bot = Bot(token=TOKEN)
app = FastAPI()

application = Application.builder().token(TOKEN).build()


# ---------------- DATA ----------------

def load():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {}

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


data_store = load()


# ---------------- LOGIC ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бот запущен\n\n"
        "/deposit 100\n"
        "/trade 2 3 BTCUSDT\n"
        "/close 1 50\n"
        "/stats"
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data_store

    try:
        text = update.message.text
        user_id = str(update.effective_user.id)

        if user_id not in data_store:
            data_store[user_id] = {"deposit": 0, "trades": []}

        parts = text.split()

        # 💰 deposit
        if parts[0] == "/deposit":
            data_store[user_id]["deposit"] = float(parts[1])
            save(data_store)
            await update.message.reply_text(f"💰 депозит: {parts[1]}$")
            return

        # 📊 trade
        if parts[0] == "/trade":
            risk = float(parts[1])
            rr = float(parts[2])
            ticker = parts[3]

            deposit = data_store[user_id]["deposit"]

            trade = {
                "id": len(data_store[user_id]["trades"]) + 1,
                "risk": risk,
                "rr": rr,
                "ticker": ticker,
                "deposit": deposit,
                "pnl": None
            }

            data_store[user_id]["trades"].append(trade)
            save(data_store)

            await update.message.reply_text(
f"""📊 СДЕЛКА #{trade['id']}

💰 депозит: {deposit}$
⚠️ риск: {risk}%
📈 RR: {rr}
📊 тикер: {ticker}
"""
            )
            return

        # ❌ close
        if parts[0] == "/close":
            trade_id = int(parts[1])
            pnl = float(parts[2])

            trades = data_store[user_id]["trades"]

            for t in trades:
                if t["id"] == trade_id:
                    t["pnl"] = pnl
                    data_store[user_id]["deposit"] += pnl
                    break

            save(data_store)
            await update.message.reply_text("сделка закрыта")
            return

        # 📊 stats
        if parts[0] == "/stats":
            trades = data_store[user_id]["trades"]

            wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
            losses = sum(1 for t in trades if (t.get("pnl") or 0) < 0)

            await update.message.reply_text(
f"""📊 СТАТИСТИКА

📈 сделок: {len(trades)}
🟢 wins: {wins}
🔴 losses: {losses}
💰 депозит: {data_store[user_id]['deposit']}$
"""
            )
            return

    except:
        await update.message.reply_text("дубина")


# ---------------- WEBHOOK ----------------

@app.post("/")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"ok": True}


@app.on_event("startup")
async def on_start():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    # webhook установка
    if URL:
        await bot.set_webhook(f"{URL}/")


# ---------------- RUN ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
