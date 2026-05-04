import os
import json
from aiohttp import web
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# 🔑 TOKEN
TOKEN = os.getenv("TOKEN")

# 🌐 PORT от Render
PORT = int(os.environ.get("PORT", 10000))

# 🤖 Bot + Application
bot = Bot(token=TOKEN)
app = Application.builder().token(TOKEN).build()

DATA_FILE = "data.json"


# ---------------- DATA ----------------

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


data_store = load()


# ---------------- COMMANDS ----------------

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

            for t in data_store[user_id]["trades"]:
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


# ---------------- WEBHOOK HANDLER ----------------

async def webhook(request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await app.process_update(update)
    return web.Response(text="ok")


# ---------------- SET WEBHOOK ----------------

async def on_startup(app_web):
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        await bot.set_webhook(url + "/webhook")


# ---------------- APP ----------------

app_web = web.Application()
app_web.router.add_post("/webhook", webhook)
app_web.on_startup.append(on_startup)


# ---------------- RUN ----------------

if __name__ == "__main__":
    web.run_app(app_web, host="0.0.0.0", port=PORT)
