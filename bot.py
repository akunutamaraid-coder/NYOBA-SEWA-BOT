import os
import time
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= DATABASE =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SEWA BOT AKTIF\n\n/sewabot untuk mulai"
    )

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET SEWA:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= AUTO CANCEL =================
async def auto_cancel(uid: int):
    await asyncio.sleep(300)
    pending_payment.pop(uid, None)
    pending_sewa.pop(uid, None)

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    # ================= PILIH PAKET =================
    if data == "paket_mingguan":
        pending_sewa[uid] = {
            "paket": "MINGGUAN",
            "qty": 1,
            "harga": 5000,
            "days": 7
        }

    elif data == "paket_bulanan":
        pending_sewa[uid] = {
            "paket": "BULANAN",
            "qty": 1,
            "harga": 15000,
            "days": 30
        }

    elif data == "plus":
        if uid in pending_sewa:
            pending_sewa[uid]["qty"] += 1

    elif data == "minus":
        if uid in pending_sewa and pending_sewa[uid]["qty"] > 1:
            pending_sewa[uid]["qty"] -= 1

    # ================= BUY =================
    elif data == "buy":
        if uid not in pending_sewa:
            return

        d = pending_sewa[uid]
        total = d["qty"] * d["harga"]

        pending_payment[uid] = {
            "data": d,
            "time": time.time()
        }

        asyncio.create_task(auto_cancel(uid))

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH TRANSFER", callback_data="paid")]
        ]

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"📊 {d['qty']}x\n"
            f"💰 Rp{total:,}\n\n"
            f"⏳ Auto cancel 5 menit",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= PAID (SYNC KE KINGZAA) =================
    elif data == "paid":
        if uid not in pending_payment:
            await query.edit_message_text("❌ Payment expired")
            return

        d = pending_payment[uid]["data"]
        total_days = d["qty"] * d["days"]
        expire_time = time.time() + (total_days * 86400)

        # 🔥 SYNC KE KINGZAA DATABASE
        groups_col.update_one(
            {"chat_id": "GLOBAL"},
            {
                "$set": {
                    # PREMIUM
                    f"premium_users.{uid}": {
                        "name": query.from_user.first_name,
                        "paket": d["paket"],
                        "expire": expire_time
                    },

                    # LIST USER (ACCESS BOT)
                    f"allowed_users.{uid}": query.from_user.first_name.lower()
                }
            },
            upsert=True
        )

        pending_payment.pop(uid, None)
        pending_sewa.pop(uid, None)

        await query.edit_message_text(
            "✅ PAYMENT BERHASIL\n\n🔥 USER MASUK LIST PREMIUM + LIST USER KINGZAA"
        )
        return

    # ================= UI UPDATE =================
    if uid not in pending_sewa:
        return

    d = pending_sewa[uid]
    total = d["qty"] * d["harga"]

    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data="minus"),
            InlineKeyboardButton(str(d["qty"]), callback_data="none"),
            InlineKeyboardButton("➕", callback_data="plus")
        ],
        [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
    ]

    await query.edit_message_text(
        f"📦 {d['paket']}\n"
        f"Qty: {d['qty']}\n"
        f"Total: Rp{total:,}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CallbackQueryHandler(callback_router))

print("🤖 BOT KESUK RUNNING...")
app.run_polling()
