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
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}
pending_group = {}
pending_owner_approval = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BOT SEWA AKTIF\n\nGunakan /sewabot untuk mulai"
    )

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CEK ID GROUP =================
async def cekidgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = str(chat.id)

    text = (
        "📌 INFO GROUP ID\n\n"
        f"🆔 ID GROUP:\n`{chat_id}`\n\n"
        "👇 tekan tombol untuk copy"
    )

    keyboard = [
        [InlineKeyboardButton("📋 COPY ID", callback_data=f"copy_{chat_id}")]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    # ================= COPY ID =================
    if data.startswith("copy_"):
        chat_id = data.split("_", 1)[1]
        await q.answer(text=f"ID: {chat_id}", show_alert=True)
        return

    # ================= PILIH PAKET =================
    if data == "mingguan":
        pending_sewa[uid] = {"paket": "MINGGUAN", "harga": 5000, "days": 7}

    elif data == "bulanan":
        pending_sewa[uid] = {"paket": "BULANAN", "harga": 15000, "days": 30}

    # ================= BUY =================
    elif data == "buy":
        if uid not in pending_sewa:
            return

        d = pending_sewa[uid]

        text = (
            "💳 PAYMENT INFO\n\n"
            f"📦 Paket: {d['paket']}\n"
            f"💰 Harga: Rp{d['harga']:,}\n\n"
            "💳 DANA: 085609264485\n"
            "💳 GOPAY: -\n"
            "💳 SEABANK: -\n\n"
            "👉 Klik jika sudah bayar"
        )

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
        ]

        pending_payment[uid] = d

        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ================= SUDAH BAYAR =================
    elif data == "paid":
        if uid not in pending_payment:
            return await q.edit_message_text("❌ Transaksi tidak ditemukan")

        pending_group[uid] = pending_payment[uid]

        await q.edit_message_text(
            "📩 KIRIM ID GROUP ANDA SEKARANG\n\nContoh: -100123456789"
        )
        return

    # ================= APPROVE OWNER =================
    elif data.startswith("approve_"):
        if uid != OWNER_ID:
            return

        user_id = int(data.split("_")[1])
        req = pending_owner_approval.get(user_id)

        if not req:
            return await q.edit_message_text("DATA TIDAK DITEMUKAN")

        gid = req["group_id"]

        g = groups_col.find_one({"chat_id": str(gid)})
        if not g:
            g = {"chat_id": str(gid), "premium_users": {}}

        expire = time.time() + (req["days"] * 86400)

        if "premium_users" not in g:
            g["premium_users"] = {}

        g["premium_users"][str(user_id)] = {
            "name": req["name"],
            "expire": expire,
            "paket": req["paket"]
        }

        groups_col.update_one(
            {"chat_id": str(gid)},
            {"$set": g},
            upsert=True
        )

        await context.bot.send_message(
            user_id,
            "✅ PAYMENT DISETUJUI OWNER\nPREMIUM AKTIF 🔥"
        )

        pending_owner_approval.pop(user_id, None)
        return await q.edit_message_text("APPROVED")

    # ================= REJECT OWNER =================
    elif data.startswith("reject_"):
        if uid != OWNER_ID:
            return

        user_id = int(data.split("_")[1])

        await context.bot.send_message(
            user_id,
            "❌ PAYMENT DITOLAK OWNER"
        )

        pending_owner_approval.pop(user_id, None)
        return await q.edit_message_text("REJECTED")

# ================= HANDLE GROUP ID =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id

    if uid not in pending_group:
        return

    group_id = msg.text
    data = pending_group.pop(uid)

    pending_owner_approval[uid] = {
        "group_id": group_id,
        "paket": data["paket"],
        "days": data["days"],
        "name": msg.from_user.first_name
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_message(
        OWNER_ID,
        f"💰 KONFIRMASI PEMBAYARAN\n\n"
        f"User: {msg.from_user.first_name}\n"
        f"ID: {uid}\n"
        f"Group: {group_id}\n"
        f"Paket: {data['paket']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await msg.reply_text("⏳ Menunggu konfirmasi owner...")

# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    text = "📌 PREMIUM USERS\n\n"

    for g in groups_col.find():
        for uid, d in g.get("premium_users", {}).items():
            sisa = int((d["expire"] - time.time()) / 86400)
            text += f"{d['name']} | {uid} | {g['chat_id']} | {sisa} hari\n"

    await update.message.reply_text(text)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("listpremium", listpremium))
app.add_handler(CommandHandler("cekidgrup", cekidgrup))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("BOT KESUK RUNNING...")
app.run_polling()
