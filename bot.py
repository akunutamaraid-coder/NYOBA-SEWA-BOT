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
OWNER_USERNAME = "@KINGZAAASLI"

# ================= DATABASE (SHARED KINGZAA) =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY KESUK =================
pending_sewa = {}
pending_payment = {}
pending_group = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 KESUK BOT ACTIVE\nKetik /sewabot")

# ================= SEWA =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= AUTO CANCEL =================
async def auto_cancel(uid: int):
    await asyncio.sleep(300)
    pending_sewa.pop(uid, None)
    pending_payment.pop(uid, None)
    pending_group.pop(uid, None)

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    # ================= PILIH PAKET =================
    if data == "mingguan":
        pending_sewa[uid] = {
            "paket": "MINGGUAN",
            "days": 7,
            "harga": 5000
        }

    elif data == "bulanan":
        pending_sewa[uid] = {
            "paket": "BULANAN",
            "days": 30,
            "harga": 15000
        }

    # ================= BUY =================
    elif data == "buy":

        if uid not in pending_sewa:
            await query.edit_message_text("❌ Pilih paket dulu")
            return

        d = pending_sewa[uid]

        pending_payment[uid] = {
            "data": d,
            "time": time.time()
        }

        asyncio.create_task(auto_cancel(uid))

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"💰 Rp{d['harga']}\n\n"
            f"DANA: 085609264485\n\n"
            "Klik sudah bayar jika sudah transfer",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
            ])
        )

    # ================= PAID =================
    elif data == "paid":

        if uid not in pending_payment:
            await query.edit_message_text("❌ Payment expired")
            return

        d = pending_payment[uid]["data"]

        pending_payment.pop(uid)

        pending_group[uid] = {
            "data": d
        }

        await query.edit_message_text(
            "📩 KIRIM ID GRUP SEKARANG\n\n"
            "Contoh: /setgrup -100123456789"
        )

    # ================= APPROVE OWNER =================
    elif data.startswith("approve_"):

        target_uid = int(data.split("_")[1])

        if target_uid not in pending_group:
            await query.edit_message_text("❌ DATA HILANG")
            return

        d = pending_group[target_uid]["data"]
        gid = pending_group[target_uid]["group_id"]

        expire_time = time.time() + (d["days"] * 86400)

        # 🔥 INI AUTO SYNC KE KINGZAA
        groups_col.update_one(
            {"chat_id": str(gid)},
            {
                "$set": {
                    f"premium_users.{target_uid}": {
                        "name": d["paket"],
                        "expire": expire_time
                    }
                }
            },
            upsert=True
        )

        pending_group.pop(target_uid)

        await query.edit_message_text("✅ APPROVED & ACTIVE DI KINGZAA")

    # ================= REJECT =================
    elif data.startswith("reject_"):

        target_uid = int(data.split("_")[1])
        pending_group.pop(target_uid, None)

        await query.edit_message_text("❌ REJECTED")

# ================= SET GRUP =================
async def setgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    if uid not in pending_group and uid not in pending_payment:
        return await update.message.reply_text("❌ Tidak ada transaksi")

    if len(context.args) < 1:
        return await update.message.reply_text("Format: /setgrup -100xxxx")

    gid = context.args[0]

    # ambil data dari pending
    if uid in pending_group:
        d = pending_group[uid]["data"]
    else:
        d = pending_sewa[uid]

    pending_group[uid] = {
        "data": d,
        "group_id": gid
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_message(
        OWNER_ID,
        f"📥 ORDER BARU\nUID: {uid}\nGRUP: {gid}\nPaket: {d['paket']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("⏳ MENUNGGU APPROVAL OWNER")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("setgrup", setgrup))

app.add_handler(CallbackQueryHandler(callback_router))

print("KESUK BOT RUNNING (SYNC KINGZAA)")
app.run_polling()
