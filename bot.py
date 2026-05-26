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

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}
premium_users = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SEWA BOT AKTIF\n\n/sewabot untuk mulai"
    )

# ================= MENU SEWA =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "Pilih paket:",
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

    data = query.data
    uid = query.from_user.id

    handled = False

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
            [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
        ]

        await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"📊 {d['qty']}x\n"
            f"💰 Rp{total:,}\n\n"
            f"📌 Transfer ke:\n"
            f"DANA: 085609264485\n\n"
            f"⏳ Auto cancel 5 menit",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        handled = True

    # ================= PAID =================
    elif data == "paid":
        handled = True

        if uid not in pending_payment:
            await query.edit_message_text("❌ Payment expired / tidak ditemukan")
            return

        d = pending_payment[uid]["data"]
        total_days = d["qty"] * d["days"]

        premium_users[str(uid)] = {
            "name": query.from_user.first_name,
            "paket": d["paket"],
            "expire": time.time() + (total_days * 86400)
        }

        pending_payment.pop(uid, None)
        pending_sewa.pop(uid, None)

        await query.edit_message_text(
            "✅ PAYMENT BERHASIL\n\nKamu sekarang PREMIUM 🔥"
        )

        await context.bot.send_message(
            chat_id=uid,
            text="🎉 Premium kamu sudah aktif!"
        )

    # ================= UI UPDATE (ANTI BUG) =================
    if handled:
        return

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

# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    if not premium_users:
        return await update.message.reply_text("LIST PREMIUM KOSONG")

    text = "📌 LIST PREMIUM:\n\n"

    for uid, data in premium_users.items():
        if data["expire"] == -1:
            status = "SELAMANYA"
        else:
            sisa = int((data["expire"] - time.time()) / 86400)
            status = f"{sisa} hari"

        text += (
            f"👤 {data['name']}\n"
            f"🆔 {uid}\n"
            f"📦 {data['paket']}\n"
            f"⏳ {status}\n\n"
        )

    await update.message.reply_text(text)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("listpremium", listpremium))

app.add_handler(CallbackQueryHandler(callback_router))

print("BOT RUNNING...")
app.run_polling()
