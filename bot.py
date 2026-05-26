import os
import time
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

client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
groups_col = db["groups"]

# ================= MEMORY =================
pending_sewa = {}
pending_payment = {}
pending_group = {}
pending_owner = {}

# ================= SAFE EDIT =================
async def safe_edit(q, text, keyboard=None):
    try:
        await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    except:
        await q.message.reply_text(text)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BOT AKTIF\n/sewabot untuk mulai")

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

# ================= CEK ID GROUP =================
async def cekidgrup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    keyboard = [
        [InlineKeyboardButton("📋 COPY ID", callback_data=f"copy_{chat_id}")]
    ]

    await update.message.reply_text(
        f"🆔 ID GROUP:\n`{chat_id}`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= CALLBACK =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()  # 🔥 WAJIB (anti tombol mati)

    uid = q.from_user.id
    data = q.data

    # ================= COPY =================
    if data.startswith("copy_"):
        await q.answer(text=data.split("_")[1], show_alert=True)
        return

    # ================= PILIH PAKET =================
    if data in ["mingguan", "bulanan"]:
        if data == "mingguan":
            pending_sewa[uid] = {"paket": "MINGGUAN", "harga": 5000, "days": 7}
        else:
            pending_sewa[uid] = {"paket": "BULANAN", "harga": 15000, "days": 30}

        d = pending_sewa[uid]

        keyboard = [[InlineKeyboardButton("🛒 BUY", callback_data="buy")]]

        await safe_edit(
            q,
            f"📦 {d['paket']}\n💰 Rp{d['harga']:,}\n\nKlik BUY untuk lanjut",
            keyboard
        )
        return

    # ================= BUY =================
    if data == "buy":
        if uid not in pending_sewa:
            return await q.answer("Session habis, ulangi /sewabot", show_alert=True)

        d = pending_sewa[uid]

        pending_payment[uid] = d

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH BAYAR", callback_data="paid")]
        ]

        text = (
            "💳 PAYMENT\n\n"
            f"📦 {d['paket']}\n"
            f"💰 Rp{d['harga']:,}\n\n"
            "DANA: 085609264485\n"
            "GOPAY: -"
        )

        await safe_edit(q, text, keyboard)
        return

    # ================= PAID =================
    if data == "paid":
        if uid not in pending_payment:
            return await q.answer("Data tidak ditemukan", show_alert=True)

        pending_group[uid] = pending_payment[uid]

        await safe_edit(
            q,
            "📩 KIRIM ID GROUP SEKARANG\ncontoh: -100123456789"
        )
        return

    # ================= OWNER APPROVE =================
    if data.startswith("approve_"):
        if uid != OWNER_ID:
            return

        user_id = int(data.split("_")[1])
        req = pending_owner.get(user_id)

        if not req:
            return await q.edit_message_text("DATA HILANG")

        gid = req["group_id"]

        g = groups_col.find_one({"chat_id": str(gid)}) or {
            "chat_id": str(gid),
            "premium_users": {}
        }

        expire = time.time() + req["days"] * 86400

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

        await context.bot.send_message(user_id, "✅ APPROVED PREMIUM")
        pending_owner.pop(user_id, None)

        await q.edit_message_text("APPROVED")
        return

    # ================= REJECT =================
    if data.startswith("reject_"):
        if uid != OWNER_ID:
            return

        user_id = int(data.split("_")[1])

        await context.bot.send_message(user_id, "❌ PAYMENT DITOLAK")
        pending_owner.pop(user_id, None)

        await q.edit_message_text("REJECTED")
        return

# ================= HANDLE GROUP ID =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id

    if uid not in pending_group:
        return

    data = pending_group.pop(uid)

    pending_owner[uid] = {
        "group_id": msg.text,
        "paket": data["paket"],
        "days": data["days"],
        "name": msg.from_user.first_name
    }

    keyboard = [
        [
            InlineKeyboardButton("APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("REJECT", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_message(
        OWNER_ID,
        f"💰 KONFIRMASI\nUser: {msg.from_user.first_name}\nID: {uid}\nGroup: {msg.text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await msg.reply_text("⏳ Menunggu approval owner...")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sewabot", sewabot))
app.add_handler(CommandHandler("cekidgrup", cekidgrup))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("BOT RUNNING (ANTI BUG VERSION)")
app.run_polling()
