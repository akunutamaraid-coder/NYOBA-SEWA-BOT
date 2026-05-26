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

# ================= STORAGE =================
pending_sewa = {}        # user memilih paket
pending_payment = {}     # menunggu approval owner

premium_db = {}          # multi group premium storage


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BOT SEWA AKTIF\n\n/sewabot untuk mulai"
    )


# ================= MENU SEWA =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "PILIH PAKET SEWA:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= LIST PREMIUM =================
async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return await update.message.reply_text("KHUSUS OWNER")

    if not premium_db:
        return await update.message.reply_text("LIST PREMIUM KOSONG")

    text = "📌 LIST PREMIUM (MULTI GROUP)\n\n"

    for chat_id, users in premium_db.items():
        text += f"📍 GROUP: {chat_id}\n\n"

        for uid, d in users.items():
            if d["expire"] == -1:
                status = "SELAMANYA"
            else:
                sisa = int((d["expire"] - time.time()) / 86400)
                status = f"{sisa} hari"

            text += (
                f"👤 {d['name']}\n"
                f"🆔 {uid}\n"
                f"📦 {d['paket']}\n"
                f"⏳ {status}\n\n"
            )

    await update.message.reply_text(text)


# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = str(query.message.chat.id)
    data = query.data

    logging.info(f"{uid} | {chat_id} -> {data}")

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

    # ================= QTY =================
    elif data == "plus" and uid in pending_sewa:
        pending_sewa[uid]["qty"] += 1

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

    # ================= PAID (WAIT OWNER APPROVAL) =================
    elif data == "paid":
        if uid not in pending_sewa:
            return

        d = pending_sewa[uid]
        total_days = d["qty"] * d["days"]

        pending_payment[uid] = {
            "chat_id": chat_id,
            "name": query.from_user.first_name,
            "paket": d["paket"],
            "expire": time.time() + (total_days * 86400)
        }

        del pending_sewa[uid]

        # kirim ke owner
        keyboard = [
            [
                InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
            ]
        ]

        await context.bot.send_message(
            OWNER_ID,
            f"📥 REQUEST SEWA\n\n"
            f"👤 {query.from_user.first_name}\n"
            f"🆔 {uid}\n"
            f"📦 {d['paket']}\n"
            f"📅 {total_days} hari\n"
            f"💰 STATUS: MENUNGGU APPROVAL",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return await query.edit_message_text(
            "⏳ PAYMENT DITERIMA\nTunggu approval OWNER..."
        )

    # ================= OWNER APPROVE =================
    elif data.startswith("approve_"):
        if uid != OWNER_ID:
            return

        target_uid = data.split("_")[1]

        if target_uid not in pending_payment:
            return await query.edit_message_text("DATA TIDAK DITEMUKAN")

        p = pending_payment[target_uid]
        chat = p["chat_id"]

        if chat not in premium_db:
            premium_db[chat] = {}

        premium_db[chat][target_uid] = {
            "name": p["name"],
            "paket": p["paket"],
            "expire": p["expire"]
        }

        del pending_payment[target_uid]

        await context.bot.send_message(
            int(target_uid),
            "✅ PAYMENT DISETUJUI OWNER\n\nKamu sekarang PREMIUM 🔥"
        )

        return await query.edit_message_text("APPROVED ✅")

    # ================= OWNER REJECT =================
    elif data.startswith("reject_"):
        if uid != OWNER_ID:
            return

        target_uid = data.split("_")[1]

        if target_uid in pending_payment:
            del pending_payment[target_uid]

        await context.bot.send_message(
            int(target_uid),
            "❌ PAYMENT DITOLAK OWNER"
        )

        return await query.edit_message_text("REJECTED ❌")

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
app.add_handler(CommandHandler("listpremium", listpremium))
app.add_handler(CallbackQueryHandler(callback_router))

print("BOT RUNNING...")
app.run_polling()
