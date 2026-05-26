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

# ================= MONGO DB =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
orders_col = db["orders"]

# ================= MEMORY TEMP =================
pending_sewa = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ketik /sewabot")

# ================= MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    pending_sewa[uid] = {
        "qty": 1,
        "paket": None,
        "harga": 0,
        "days": 0
    }

    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CALLBACK (FIX TOTAL) =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    print("CALLBACK:", data)

    if uid not in pending_sewa:
        pending_sewa[uid] = {"qty": 1, "paket": None, "harga": 0, "days": 0}

    d = pending_sewa[uid]

    # ================= PILIH PAKET =================
    if data == "paket_mingguan":
        d["paket"] = "MINGGUAN"
        d["harga"] = 5000
        d["days"] = 7

    elif data == "paket_bulanan":
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

        # SIMPAN ORDER KE MONGO
        orders_col.update_one(
            {"uid": uid},
            {"$set": {
                "uid": uid,
                "data": d,
                "status": "WAITING_PAYMENT",
                "time": time.time()
            }},
            upsert=True
        )

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"Qty: {d['qty']}\n"
            f"Total: Rp{total:,}\n\n"
            f"DANA: 085609264485",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
            ])
        )

    # ================= PAID =================
    elif data == "paid":

        orders_col.update_one(
            {"uid": uid},
            {"$set": {"status": "WAITING_GROUP"}}
        )

        await query.edit_message_text(
            "📩 KIRIM ID GRUP\nGunakan /setgrup -100xxxx"
        )

    # ================= UI UPDATE (WAJIB) =================
    if d.get("paket"):

        total = d["qty"] * d["harga"]

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="minus"),
                InlineKeyboardButton(str(d["qty"]), callback_data="noop"),
                InlineKeyboardButton("➕", callback_data="plus"),
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        try:
            await query.edit_message_text(
                f"📦 {d['paket']}\nQty: {d['qty']}\nTotal: Rp{total:,}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass

# ================= SET GRUP =================
async def setgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    if len(context.args) < 1:
        return await update.message.reply_text("Format: /setgrup -100xxxx")

    gid = context.args[0]

    order = orders_col.find_one({"uid": uid, "status": "WAITING_GROUP"})

    if not order:
        return await update.message.reply_text("❌ Tidak ada order")

    d = order["data"]

    # EXPIRE
    expire = time.time() + (d["days"] * 86400)

    # 🔥 SYNC KE KINGZAA DB
    groups_col = db["groups"]

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

    orders_col.update_one(
        {"uid": uid},
        {"$set": {"status": "ACTIVE", "group": gid}}
    )

    await update.message.reply_text("✅ SUCCESS ACTIVE DI KINGZAA")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("setgrup", setgrup))

app.add_handler(CallbackQueryHandler(callback_router))

print("KESUK BOT FINAL + MONGO READY 🚀")
app.run_polling()
