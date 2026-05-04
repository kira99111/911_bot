from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import json
import os
import matplotlib.pyplot as plt
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

TOKEN = os.getenv("TOKEN")

FILE = "journal.json"
ARCHIVE = "archive.json"


def current_week():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y %B W{week}")


def load(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}


def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


weekly_log = load(FILE)
archive_log = load(ARCHIVE)
week_id = current_week()


def check_week():
    global weekly_log, archive_log, week_id

    now = current_week()

    if now != week_id:
        archive_log[week_id] = weekly_log
        save(ARCHIVE, archive_log)

        weekly_log = {}
        save(FILE, weekly_log)

        week_id = now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_week()

    await update.message.reply_text(
f"""🤖 TRADING BOT

📅 Неделя: {week_id}

/deposit 100 — депозит
/trade 2 3 BTCUSDT — сделка
/close 1 50 — закрыть
/week — неделя
/stats — статистика
/equity — график
/reset — очистка
"""
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global weekly_log

    try:
        check_week()

        text = update.message.text
        parts = text.split()
        user_id = str(update.effective_user.id)

        if user_id not in weekly_log:
            weekly_log[user_id] = []

        user_trades = weekly_log[user_id]

        # 💰 депозит
        if parts[0] == "/deposit":
            context.user_data["deposit"] = float(parts[1])
            await update.message.reply_text(f"💰 депозит: {parts[1]}$")
            return

        # 📊 trade
        if parts[0] == "/trade":
            risk = float(parts[1])
            rr = float(parts[2])
            ticker = parts[3]

            deposit = context.user_data.get("deposit", 0)

            trade = {
                "id": len(user_trades) + 1,
                "risk": risk,
                "rr": rr,
                "ticker": ticker,
                "start_deposit": deposit,
                "end_deposit": None
            }

            user_trades.append(trade)
            weekly_log[user_id] = user_trades
            save(FILE, weekly_log)

            await update.message.reply_text(
f"""📊 СДЕЛКА #{trade['id']}

💰 депозит: {deposit}$
⚠️ риск: {risk}%
📈 RR: {rr}
📊 тикер: {ticker}
"""
            )
            return

        # 📌 close
        if parts[0] == "/close":
            trade_id = int(parts[1])
            pnl = float(parts[2])

            for t in user_trades:
                if t["id"] == trade_id:
                    t["end_deposit"] = t["start_deposit"] + pnl
                    break

            weekly_log[user_id] = user_trades
            save(FILE, weekly_log)

            await update.message.reply_text("сделка закрыта")
            return

        # 📅 week
        if parts[0] == "/week":
            closed = [t for t in user_trades if t.get("end_deposit")]

            wins = sum(1 for t in closed if t["end_deposit"] > t["start_deposit"])
            losses = len(closed) - wins

            winrate = (wins / len(closed) * 100) if closed else 0

            await update.message.reply_text(
f"""📊 НЕДЕЛЯ

📈 сделок: {len(user_trades)}
🏆 winrate: {winrate:.1f}%
🟢 wins: {wins}
🔴 losses: {losses}
"""
            )
            return

        # 📊 stats
        if parts[0] == "/stats":
            closed = [t for t in user_trades if t.get("end_deposit")]

            wins = sum(1 for t in closed if t["end_deposit"] > t["start_deposit"])
            losses = len(closed) - wins

            await update.message.reply_text(
f"""📊 STATS

🟢 wins: {wins}
🔴 losses: {losses}
"""
            )
            return

        # 📈 equity
        if parts[0] == "/equity":
            closed = [t for t in user_trades if t.get("end_deposit")]

            if not closed:
                await update.message.reply_text("нет данных")
                return

            x, y = [], []

            for i, t in enumerate(closed):
                x.append(i)
                y.append(t["end_deposit"])

            plt.figure()
            plt.plot(x, y)

            path = "equity.png"
            plt.savefig(path)
            plt.close()

            await update.message.reply_photo(photo=open(path, "rb"))
            return

        # 🧹 reset
        if parts[0] == "/reset":
            weekly_log[user_id] = []
            save(FILE, weekly_log)
            await update.message.reply_text("очищено")
            return

    except:
        await update.message.reply_text("дубина")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"bot running")


def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


threading.Thread(target=run_server).start()


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
