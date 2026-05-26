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

from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= DB =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
premium_col = db["premium_users"]

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}
pending_approval = {}
waiting_group_id = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SEWA BOT AKTIF\n\n/sewabot untuk mulai"
    )

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "💎 PILIH PAKET SEWA:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= AUTO CANCEL =================
async def auto_cancel(uid: str):
    await asyncio.sleep(300)

    if uid in pending_payment:
        pending_payment.pop(uid, None)
        pending_sewa.pop(uid, None)

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    uid = str(query.from_user.id)

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
            [InlineKeyboardButton("💳 KONFIRMASI PEMBAYARAN", callback_data="confirm_pay")]
        ]

        await query.edit_message_text(
            "💰 PAYMENT\n\n"
            f"📦 Paket: {d['paket']}\n"
            f"📊 Qty: {d['qty']}\n"
            f"💰 Total: Rp{total:,}\n\n"
            "💳 DANA: 085609264485\n"
            "GOPAY: -\n"
            "SEABANK: -\n\n"
            "Klik jika sudah transfer",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ================= CONFIRM PAYMENT =================
    elif data == "confirm_pay":
        if uid not in pending_payment:
            await query.edit_message_text("❌ Payment expired")
            return

        waiting_group_id[uid] = pending_payment[uid]["data"]

        await query.edit_message_text(
            "📌 SILAHKAN MASUKKAN ID GRUP\n\n"
            "Kirim ID grup tempat bot akan diaktifkan."
        )
        return

    # ================= APPROVE / REJECT =================
    if data.startswith("approve_") or data.startswith("reject_"):
        if query.from_user.id != OWNER_ID:
            await query.answer("Khusus owner")
            return

        target_id = data.split("_")[1]

        if target_id not in pending_approval:
            await query.edit_message_text("Data sudah expired")
            return

        data_user = pending_approval[target_id]

        if data.startswith("approve_"):
            premium_data = {
                "user_id": target_id,
                "name": data_user["name"],
                "paket": data_user["paket"],
                "group_id": data_user["group_id"],
                "expire": data_user["expire"]
            }

            premium_col.update_one(
                {"user_id": target_id},
                {"$set": premium_data},
                upsert=True
            )

            await context.bot.send_message(
                chat_id=int(target_id),
                text="✅ PREMIUM AKTIF 🔥"
            )

            await query.edit_message_text("USER DIAPPROVE")

        else:
            await context.bot.send_message(
                chat_id=int(target_id),
                text="❌ PREMIUM GAGAL"
            )

            await query.edit_message_text("USER DITOLAK")

        pending_approval.pop(target_id, None)
        return

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

# ================= HANDLE GROUP ID =================
async def handle_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)

    if uid not in waiting_group_id:
        return

    group_id = update.message.text
    d = waiting_group_id[uid]

    pending_approval[uid] = {
        "name": update.message.from_user.first_name,
        "paket": d["paket"],
        "group_id": group_id,
        "expire": time.time() + (d["qty"] * d["days"] * 86400)
    }

    waiting_group_id.pop(uid, None)
    pending_payment.pop(uid, None)

    keyboard = [
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            "💰 KONFIRMASI PEMBAYARAN\n\n"
            f"User: {update.message.from_user.first_name}\n"
            f"ID User: {uid}\n"
            f"ID Grup: {group_id}\n"
            f"Paket: {d['paket']}\n"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("⏳ Menunggu konfirmasi owner...")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_id))

print("BOT KESUK RUNNING...")
app.run_polling()
