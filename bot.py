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
pending_group_input = {}   # 🔥 STEP INPUT ID GRUP
pending_owner_confirm = {}  # 🔥 OWNER APPROVAL
premium_users = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BOT AKTIF\n/sewabot untuk mulai")

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.chat.type == "private":
        text = "SILAHKAN MASUKAN BOT INI DAN KASIH AKSES ALL ATAU DELETE PESAN"
    else:
        text = "SILAHKAN CHAT @KESUKBOT"

    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="bulanan")]
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    # ========== PILIH PAKET ==========
    if data in ["mingguan", "bulanan"]:

        pending_sewa[uid] = {
            "paket": data,
            "qty": 1,
            "harga": 5000 if data == "mingguan" else 15000,
            "days": 7 if data == "mingguan" else 30
        }

        kb = [
            [
                InlineKeyboardButton("-", callback_data="min"),
                InlineKeyboardButton("1", callback_data="noop"),
                InlineKeyboardButton("+", callback_data="plus"),
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        return await q.edit_message_text("Pilih qty:", reply_markup=InlineKeyboardMarkup(kb))

    # ========== QTY ==========
    if uid in pending_sewa:
        if data == "plus":
            pending_sewa[uid]["qty"] += 1

        elif data == "min":
            if pending_sewa[uid]["qty"] > 1:
                pending_sewa[uid]["qty"] -= 1

        elif data == "buy":
            d = pending_sewa[uid]
            total = d["qty"] * d["harga"]

            pending_payment[uid] = d

            kb = [[InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]]

            return await q.edit_message_text(
                f"💳 PAYMENT\nTotal: Rp{total:,}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        d = pending_sewa[uid]
        kb = [
            [
                InlineKeyboardButton("-", callback_data="min"),
                InlineKeyboardButton(str(d["qty"]), callback_data="noop"),
                InlineKeyboardButton("+", callback_data="plus"),
            ],
            [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
        ]

        return await q.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))

    # ========== PAID ==========
    if data == "paid":

        if uid not in pending_payment:
            return await q.edit_message_text("Payment tidak valid")

        pending_group_input[uid] = pending_payment[uid]
        pending_payment.pop(uid)

        return await q.edit_message_text("📩 SILAHKAN KIRIM ID GRUP")

    # ========== OWNER APPROVE ==========
    if data.startswith("approve_") or data.startswith("reject_"):

        if uid != OWNER_ID:
            return await q.answer("Hanya owner", show_alert=True)

        user_id = int(data.split("_")[1])

        req = pending_owner_confirm.get(user_id)
        if not req:
            return await q.edit_message_text("Request sudah expired")

        if data.startswith("approve_"):

            premium_users[user_id] = {
                "group_id": req["group_id"],
                "expire": time.time() + (req["days"] * 86400)
            }

            await context.bot.send_message(user_id, "✅ PAYMENT DITERIMA\nPREMIUM AKTIF")

            pending_owner_confirm.pop(user_id)

            return await q.edit_message_text("DI APPROVE")

        else:
            await context.bot.send_message(user_id, "❌ PAYMENT DITOLAK")
            pending_owner_confirm.pop(user_id)

            return await q.edit_message_text("DITOLAK")

# ================= HANDLE ID GRUP =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    if uid not in pending_group_input:
        return

    req = pending_group_input.pop(uid)

    pending_owner_confirm[uid] = {
        "group_id": text,
        "days": req["days"]
    }

    kb = [
        [
            InlineKeyboardButton("TERIMA", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("TOLAK", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_message(
        OWNER_ID,
        f"REQUEST PREMIUM\nUSER: {uid}\nGROUP: {text}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await update.message.reply_text("⏳ MENUNGGU APPROVAL OWNER")

# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    text = "LIST PREMIUM:\n\n"

    for uid, data in premium_users.items():
        sisa = int((data["expire"] - time.time()) / 86400)

        text += f"{uid} | {data['group_id']} | {sisa} hari\n"

    await update.message.reply_text(text)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("listpremium", listpremium))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("BOT RUNNING...")
app.run_polling()
