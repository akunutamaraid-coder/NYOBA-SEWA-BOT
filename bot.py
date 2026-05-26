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

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= DATABASE =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]

payments_col = db["payments"]
premium_col = db["premium_users"]

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 KESUK BOT AKTIF\n\n/sewabot untuk mulai"
    )

# ================= SEWABOT =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET SEWA:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CALLBACK =================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    # ================= PILIH PAKET =================
    if data in ["paket_mingguan", "paket_bulanan"]:

        paket = "MINGGUAN" if data == "paket_mingguan" else "BULANAN"
        harga = 5000 if paket == "MINGGUAN" else 15000
        days = 7 if paket == "MINGGUAN" else 30

        payments_col.update_one(
            {"uid": uid},
            {"$set": {
                "uid": uid,
                "paket": paket,
                "harga": harga,
                "qty": 1,
                "days": days,
                "status": "pending"
            }},
            upsert=True
        )

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="min"),
                InlineKeyboardButton("1", callback_data="none"),
                InlineKeyboardButton("➕", callback_data="plus")
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        await q.edit_message_text(
            f"📦 {paket}\n💰 Rp{harga:,}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= QTY =================
    if data in ["plus", "min"]:
        p = payments_col.find_one({"uid": uid})
        if not p:
            return

        qty = p.get("qty", 1)

        if data == "plus":
            qty += 1
        elif data == "min" and qty > 1:
            qty -= 1

        payments_col.update_one({"uid": uid}, {"$set": {"qty": qty}})

        total = qty * p["harga"]

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="min"),
                InlineKeyboardButton(str(qty), callback_data="none"),
                InlineKeyboardButton("➕", callback_data="plus")
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        await q.edit_message_text(
            f"📦 {p['paket']}\nQty: {qty}\nTotal: Rp{total:,}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= BUY =================
    if data == "buy":
        p = payments_col.find_one({"uid": uid})
        if not p:
            return

        total = p["qty"] * p["harga"]

        payments_col.update_one(
            {"uid": uid},
            {"$set": {"status": "waiting"}}
        )

        keyboard = [
            [InlineKeyboardButton("📋 KONFIRMASI PEMBAYARAN", callback_data="confirm_owner")]
        ]

        await q.edit_message_text(
            f"""💳 PAYMENT

DANA: 085609264485
GOPAY: -
SEABANK: -

💰 TOTAL: Rp{total:,}

Klik jika sudah transfer""",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= CONFIRM OWNER =================
    if data == "confirm_owner":
        p = payments_col.find_one({"uid": uid})
        if not p:
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ TERIMA", callback_data=f"acc_{uid}"),
                InlineKeyboardButton("❌ TOLAK", callback_data=f"rej_{uid}")
            ]
        ]

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"""
🔥 PAYMENT MASUK

User ID: {uid}
Paket: {p['paket']}
Qty: {p['qty']}
Total: Rp{p['qty'] * p['harga']:,}
""",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await q.edit_message_text("⏳ Menunggu konfirmasi owner...")
        return

    # ================= OWNER ACTION =================
    if data.startswith("acc_") or data.startswith("rej_"):
        if uid != OWNER_ID:
            return

        target = int(data.split("_")[1])
        p = payments_col.find_one({"uid": target})
        if not p:
            return

        if data.startswith("acc_"):
            payments_col.update_one(
                {"uid": target},
                {"$set": {"status": "approved"}}
            )

            await context.bot.send_message(
                chat_id=target,
                text="✅ PAYMENT DITERIMA\n\nKirim ID GRUP kamu sekarang:"
            )

        else:
            payments_col.delete_one({"uid": target})
            await context.bot.send_message(
                chat_id=target,
                text="❌ PAYMENT DITOLAK"
            )

# ================= INPUT ID GRUP (FIX BUG DIEM) =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    uid = msg.from_user.id
    text = msg.text.strip()

    p = payments_col.find_one({"uid": uid, "status": "approved"})
    if not p:
        return

    premium_col.update_one(
        {"uid": uid},
        {"$set": {
            "uid": uid,
            "group_id": text,
            "paket": p["paket"],
            "expire": time.time() + (p["days"] * 86400)
        }},
        upsert=True
    )

    payments_col.delete_one({"uid": uid})

    await msg.reply_text("🎉 PREMIUM AKTIF\nID GRUP BERHASIL DISIMPAN")

# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    data = premium_col.find()
    text = "📌 LIST PREMIUM:\n\n"

    for d in data:
        if d["expire"] == -1:
            status = "SELAMANYA"
        else:
            sisa = int((d["expire"] - time.time()) / 86400)
            status = f"{sisa} hari"

        text += (
            f"👤 {d['uid']}\n"
            f"📦 {d['paket']}\n"
            f"⏳ {status}\n\n"
        )

    await update.message.reply_text(text)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("listpremium", listpremium))

app.add_handler(CallbackQueryHandler(callback))

# 🔥 FIX PENTING: ini biang bug kamu tadi
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("KESUK BOT RUNNING...")
app.run_polling()
