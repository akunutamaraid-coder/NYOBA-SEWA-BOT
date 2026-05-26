import os
import time
import asyncio
import logging

from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079

# ================= DATABASE =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY =================
pending = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 KESUK BOT AKTIF\nKetik /sewabot")

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    pending[uid] = {
        "paket": None,
        "qty": 1,
        "harga": 0,
        "days": 0,
        "step": "choose"
    }

    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if uid not in pending:
        pending[uid] = {"paket": None, "qty": 1, "harga": 0, "days": 0, "step": "choose"}

    d = pending[uid]

    print("CALLBACK:", data)

    # ================= PILIH PAKET =================
    if data == "mingguan":
        d["paket"] = "MINGGUAN"
        d["harga"] = 5000
        d["days"] = 7

    elif data == "bulanan":
        d["paket"] = "BULANAN"
        d["harga"] = 15000
        d["days"] = 30

    # ================= PLUS =================
    elif data == "plus":
        d["qty"] += 1

    # ================= MINUS =================
    elif data == "minus":
        if d["qty"] > 1:
            d["qty"] -= 1

    # ================= BUY =================
    elif data == "buy":

        if not d["paket"]:
            await query.edit_message_text("❌ PILIH PAKET DULU")
            return

        total = d["qty"] * d["harga"]

        d["step"] = "payment"

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
        ]

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"Qty: {d['qty']}\n"
            f"Total: Rp{total:,}\n\n"
            f"DANA: 085609264485",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= PAID =================
    elif data == "paid":

        d["step"] = "group"

        await query.edit_message_text(
            "📩 KIRIM ID GRUP\nGunakan /setgrup -100xxxx"
        )
        return

    # ================= UI UPDATE (AMAN - NO LOOP) =================
    if d.get("paket") and d.get("step") == "choose":

        total = d["qty"] * d["harga"]

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="minus"),
                InlineKeyboardButton(str(d["qty"]), callback_data="noop"),
                InlineKeyboardButton("➕", callback_data="plus"),
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        await query.edit_message_text(
            f"📦 {d['paket']}\nQty: {d['qty']}\nTotal: Rp{total:,}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================= SET GRUP =================
async def setgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    if uid not in pending:
        return await update.message.reply_text("❌ Tidak ada transaksi")

    if len(context.args) < 1:
        return await update.message.reply_text("Format: /setgrup -100xxxx")

    gid = context.args[0]

    d = pending[uid]

    if d.get("step") != "group":
        return await update.message.reply_text("❌ Belum payment")

    expire = time.time() + (d["days"] * 86400)

    groups_col.update_one(
        {"chat_id": str(gid)},
        {
            "$set": {
                f"premium_users.{uid}": {
                    "name": d["paket"],
                    "expire": expire
                }
            }
        },
        upsert=True
    )

    pending.pop(uid, None)

    await update.message.reply_text("✅ PREMIUM AKTIF (KESUK SYNC OK)")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("setgrup", setgrup))

app.add_handler(CallbackQueryHandler(callback_router))

print("KESUK BOT STABLE RUNNING 🚀")
app.run_polling()
