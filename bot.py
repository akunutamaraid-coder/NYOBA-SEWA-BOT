import os
import time
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6818257079
OWNER_USERNAME = "@KINGZAAASLI"

# ================= DB =================
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 SEWA BOT AKTIF\n\n/sewabot untuk mulai")

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]
    await update.message.reply_text("Pilih paket:", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= COPY ID GRUP =================
async def cekidgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id

    keyboard = [
        [InlineKeyboardButton("📋 COPY ID GRUP", callback_data=f"copy_{chat_id}")]
    ]

    await update.message.reply_text(
        f"ID GRUP: `{chat_id}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= AUTO CANCEL =================
async def auto_cancel(uid):
    await asyncio.sleep(300)
    pending_payment.pop(uid, None)
    pending_sewa.pop(uid, None)

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    uid = query.from_user.id

    logging.info(f"CALLBACK: {data}")

    try:

        # ================= COPY ID =================
        if data.startswith("copy_"):
            group_id = data.split("_")[1]
            await query.answer(text=f"ID: {group_id}", show_alert=True)
            return

        # ================= PILIH PAKET =================
        if data == "paket_mingguan":
            pending_sewa[uid] = {"paket": "MINGGUAN", "qty": 1, "harga": 5000, "days": 7}

        elif data == "paket_bulanan":
            pending_sewa[uid] = {"paket": "BULANAN", "qty": 1, "harga": 15000, "days": 30}

        # ================= PLUS MINUS =================
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

            pending_payment[uid] = {"data": d, "time": time.time()}
            asyncio.create_task(auto_cancel(uid))

            keyboard = [
                [InlineKeyboardButton("💳 KONFIRMASI PEMBAYARAN", callback_data="paid")]
            ]

            await query.edit_message_text(
                f"💳 PAYMENT\n\n"
                f"DANA: 085609264485\n"
                f"GOPAY: -\n"
                f"SEABANK: -\n\n"
                f"📦 {d['paket']}\n"
                f"📊 {d['qty']}x\n"
                f"💰 Rp{total:,}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # ================= PAID =================
        elif data == "paid":
            if uid not in pending_payment:
                await query.edit_message_text("❌ Payment expired")
                return

            await query.edit_message_text("📩 Kirim ID GRUP kamu")

            context.user_data["await_group"] = True
            return

        # ================= UI UPDATE =================
        if uid in pending_sewa:
            d = pending_sewa[uid]
            total = d["qty"] * d["harga"]

            keyboard = [
                [
                    InlineKeyboardButton("➖", callback_data="minus"),
                    InlineKeyboardButton(str(d["qty"]), callback_data="none"),
                    InlineKeyboardButton("➕", callback_data="plus"),
                ],
                [InlineKeyboardButton("🛒 BUY", callback_data="buy")]
            ]

            await query.edit_message_text(
                f"📦 {d['paket']}\nQty: {d['qty']}\nTotal: Rp{total:,}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        print("CALLBACK ERROR:", e)

# ================= HANDLE GROUP ID =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id

    if context.user_data.get("await_group"):
        group_id = msg.text
        d = pending_payment.get(uid)

        if not d:
            return

        await msg.reply_text("⏳ Menunggu approval owner...")

        keyboard = [
            [
                InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}_{group_id}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
            ]
        ]

        await context.bot.send_message(
            OWNER_ID,
            f"📩 REQUEST SEWA\nUser: {uid}\nGroup: {group_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data["await_group"] = False

# ================= OWNER APPROVE =================
async def owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # APPROVE
    if data.startswith("approve_"):
        _, uid, group_id = data.split("_")

        d = pending_payment.get(int(uid))
        if not d:
            return

        total_days = d["data"]["qty"] * d["data"]["days"]
        expire = time.time() + (total_days * 86400)

        groups_col.update_one(
            {"chat_id": str(group_id)},
            {"$set": {
                f"premium_users.{uid}": {
                    "name": "USER",
                    "expire": expire
                }
            }},
            upsert=True
        )

        await query.edit_message_text("✅ APPROVED - USER PREMIUM AKTIF")

    # REJECT
    elif data.startswith("reject_"):
        uid = data.split("_")[1]
        await query.edit_message_text("❌ REJECTED")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("cekidgrup", cekidgrup))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(CallbackQueryHandler(owner_callback, pattern="^(approve_|reject_)"))
print("BOT KESUK RUNNING...")
app.run_polling(drop_pending_updates=True)
