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

# 📅 неделя
def current_week():
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.strftime(f"%Y %B W{week}")

# 💾 файлы
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

def check_week():
    global weekly_log, archive_log, week_id

    now = current_week()

    if now != week_id:
        archive_log.append({"week": week_id, "trades": weekly_log})
        save(ARCHIVE, archive_log)

        weekly_log = []
        save(FILE, weekly_log)

        week_id = now


# 🟢 START + МЕНЮ КОМАНД
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_week()

    await update.message.reply_text(
f"""🤖 TRADING JOURNAL BOT

📅 Неделя: {week_id}

📌 ДОСТУПНЫЕ КОМАНДЫ:

/deposit 100
➡️ Установить депозит (фиксируется на неделю)

/trade 2 3 BTCUSDT
➡️ Новая сделка:
   2 = риск %
   3 = RR
   BTCUSDT = тикер

/close 1 50
➡️ Закрыть сделку:
   1 = номер сделки
   50 = PnL в $

/week
➡️ Статистика недели (winrate, прибыль)

/stats
➡️ Полная статистика

/equity
➡️ График депозита

/reset
➡️ Очистить недельные сделки
"""
    )


# 🧠 обработчик
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global weekly_log

    check_week()

    text = update.message.text
    parts = text.split()

    # 💰 депозит
    if parts[0] == "/deposit":
        try:
            context.user_data["deposit"] = float(parts[1])
            await update.message.reply_text(f"💰 депозит установлен: {parts[1]}$")
        except:
            await update.message.reply_text("пример: /deposit 100")
        return

    # 📊 сделка
    if parts[0] == "/trade":
        try:
            risk = float(parts[1])
            rr = float(parts[2])
            ticker = parts[3]

            deposit = context.user_data.get("deposit", 0)

            trade = {
                "id": len(weekly_log) + 1,
                "risk": risk,
                "rr": rr,
                "ticker": ticker,
                "start_deposit": deposit,
                "end_deposit": None
            }

            weekly_log.append(trade)
            save(FILE, weekly_log)

            await update.message.reply_text(
f"""📊 СДЕЛКА #{trade['id']}

💰 депозит: {deposit}$
⚠️ риск: {risk}%
📈 RR: {rr}
📊 тикер: {ticker}
"""
            )

        except:
            await update.message.reply_text("пример: /trade 2 3 BTCUSDT")
        return

    # 📌 закрытие
    if parts[0] == "/close":
        try:
            trade_id = int(parts[1])
            pnl = float(parts[2])

            for t in weekly_log:
                if t["id"] == trade_id:
                    t["end_deposit"] = t["start_deposit"] + pnl
                    break

            save(FILE, weekly_log)
            await update.message.reply_text("сделка закрыта")

        except:
            await update.message.reply_text("пример: /close 1 50")
        return

    # 📅 неделя
    if parts[0] == "/week":
        closed = [t for t in weekly_log if t.get("end_deposit")]

        wins = sum(1 for t in closed if t["end_deposit"] > t["start_deposit"])
        losses = len(closed) - wins

        winrate = (wins / len(closed) * 100) if closed else 0

        await update.message.reply_text(
f"""📊 НЕДЕЛЯ

📈 сделок: {len(weekly_log)}
🏆 winrate: {winrate:.1f}%
🟢 wins: {wins}
🔴 losses: {losses}
"""
        )
        return

    # 📊 stats
    if parts[0] == "/stats":
        closed = [t for t in weekly_log if t.get("end_deposit")]

        wins = sum(1 for t in closed if t["end_deposit"] > t["start_deposit"])
        losses = len(closed) - wins

        await update.message.reply_text(
f"""📊 STATS

🟢 wins: {wins}
🔴 losses: {losses}
📈 total: {len(closed)}
"""
        )
        return

    # 📈 equity
    if parts[0] == "/equity":
        closed = [t for t in weekly_log if t.get("end_deposit")]

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
        plt.title("Equity")
        plt.grid()

        path = "equity.png"
        plt.savefig(path)
        plt.close()

        await update.message.reply_photo(photo=open(path, "rb"))
        return

    # 🧹 reset
    if parts[0] == "/reset":
        weekly_log = []
        save(FILE, weekly_log)
        await update.message.reply_text("очищено")
        return


# 🌐 render web service порт
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


# 🚀 bot
app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(CommandHandler("start", start))

app.run_polling()
