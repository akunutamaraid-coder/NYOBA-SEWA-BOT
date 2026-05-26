import os
import time
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

pending_sewa = {}
paid_users = set()  # 🔥 penting biar gak balik UI lagi


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BOT SEWA AKTIF\n\n/sewabot untuk mulai")


# ================= SEWABOT =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "PILIH PAKET:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    logging.info(f"{uid} -> {data}")

    # ❌ kalau sudah selesai, jangan sentuh lagi UI
    if uid in paid_users:
        return

    # ================= PILIH PAKET =================
    if data == "paket_mingguan":
        pending_sewa[uid] = {"paket": "MINGGUAN", "qty": 1, "harga": 5000, "days": 7}

    elif data == "paket_bulanan":
        pending_sewa[uid] = {"paket": "BULANAN", "qty": 1, "harga": 15000, "days": 30}

    # ================= PLUS =================
    elif data == "plus" and uid in pending_sewa:
        pending_sewa[uid]["qty"] += 1

    # ================= MINUS =================
    elif data == "minus" and uid in pending_sewa:
        if pending_sewa[uid]["qty"] > 1:
            pending_sewa[uid]["qty"] -= 1

    # ================= BUY =================
    elif data == "buy":
        if uid not in pending_sewa:
            return

        d = pending_sewa[uid]
        total = d["qty"] * d["harga"]

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH TRANSFER", callback_data="paid")]
        ]

        return await query.edit_message_text(
            f"💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"📊 {d['qty']}x\n"
            f"💰 Rp{total:,}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= PAID =================
    elif data == "paid":
        if uid not in pending_sewa:
            return

        d = pending_sewa[uid]
        total_days = d["qty"] * d["days"]

        paid_users.add(uid)  # 🔥 LOCK USER

        del pending_sewa[uid]

        return await query.edit_message_text(
            "✅ PAYMENT BERHASIL\n\nKamu sekarang PREMIUM 🔥"
        )

    # ================= UI UPDATE (HANYA JIKA BELUM BUY) =================
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

print("BOT RUNNING...")
app.run_polling()
