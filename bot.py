import os
import time
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}
pending_group = {}
pending_confirm = {}
premium_users = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 KESUK BOT AKTIF\nGunakan /sewabot")

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= AUTO CANCEL =================
async def auto_cancel(uid: int):
    await asyncio.sleep(300)

    pending_payment.pop(uid, None)
    pending_sewa.pop(uid, None)
    pending_group.pop(uid, None)

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
            "harga": 5000,
            "days": 7
        }

    elif data == "paket_bulanan":
        pending_sewa[uid] = {
            "paket": "BULANAN",
            "harga": 15000,
            "days": 30
        }

    # ================= BUY =================
    elif data == "buy":

        if uid not in pending_sewa:
            await query.edit_message_text("❌ Pilih paket dulu")
            return

        d = pending_sewa[uid]
        total = d["harga"]

        pending_payment[uid] = {
            "data": d,
            "time": time.time()
        }

        asyncio.create_task(auto_cancel(uid))

        keyboard = [
            [InlineKeyboardButton("💳 SUDAH BAYAR", callback_data="paid")]
        ]

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"💰 Rp{total:,}\n\n"
            f"DANA: 085609264485\n\n"
            f"Klik jika sudah transfer",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= PAID (FIX DISINI) =================
    elif data == "paid":

        if uid not in pending_payment:
            await query.edit_message_text("❌ Payment expired")
            return

        d = pending_payment[uid]["data"]

        pending_sewa[uid] = d
        pending_payment.pop(uid, None)

        keyboard = [
            [InlineKeyboardButton("📩 KIRIM ID GRUP", callback_data="req_group")]
        ]

        await query.edit_message_text(
            "✅ PEMBAYARAN DITERIMA\n\n"
            "📌 SEKARANG KIRIM ID GRUP",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= REQUEST GROUP =================
    elif data == "req_group":

        await query.edit_message_text(
            "📩 KIRIM ID GRUP SEKARANG\n\n"
            "Gunakan:\n/setgrup -100xxxxxxx"
        )

    # ================= OWNER APPROVE =================
    elif data.startswith("approve_"):

        target_uid = int(data.split("_")[1])

        order = pending_group.get(target_uid)
        if not order:
            await query.edit_message_text("❌ Data tidak ditemukan")
            return

        d = order["data"]
        gid = order["group_id"]

        premium_users[str(target_uid)] = {
            "paket": d["paket"],
            "expire": time.time() + (d["days"] * 86400),
            "group_id": gid
        }

        pending_group.pop(target_uid, None)

        await query.edit_message_text("✅ USER PREMIUM AKTIF")

    # ================= OWNER REJECT =================
    elif data.startswith("reject_"):

        target_uid = int(data.split("_")[1])
        pending_group.pop(target_uid, None)

        await query.edit_message_text("❌ DITOLAK")

# ================= SET GRUP =================
async def setgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.message.from_user.id

    if uid not in pending_sewa:
        return await update.message.reply_text("❌ Tidak ada transaksi")

    if len(context.args) < 1:
        return await update.message.reply_text("Format: /setgrup -100xxxx")

    gid = context.args[0]
    d = pending_sewa[uid]

    pending_group[uid] = {
        "group_id": gid,
        "data": d
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

    await update.message.reply_text("⏳ Menunggu approval owner...")

# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    text = "📌 PREMIUM LIST\n\n"

    for uid, d in premium_users.items():

        sisa = int((d["expire"] - time.time()) / 86400)

        text += (
            f"UID: {uid}\n"
            f"GRUP: {d['group_id']}\n"
            f"STATUS: {sisa} hari\n\n"
        )

    await update.message.reply_text(text)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("setgrup", setgrup))
app.add_handler(CommandHandler("listpremium", listpremium))

app.add_handler(CallbackQueryHandler(callback_router))

print("KESUK BOT RUNNING...")
app.run_polling()
