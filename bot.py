import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logging.basicConfig(level=logging.INFO)

pending_sewa = {}

# ================= SEWA MENU =================
async def sewabot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Mingguan", callback_data="paket_mingguan")],
        [InlineKeyboardButton("📅 Bulanan", callback_data="paket_bulanan")]
    ]

    await update.message.reply_text(
        "📦 PILIH PAKET SEWA:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= CALLBACK =================
async def sewa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    logging.info(f"SEWA CALLBACK: {data}")

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

    # kalau belum pilih paket
    if uid not in pending_sewa:
        return

    d = pending_sewa[uid]
    total = d["qty"] * d["harga"]

    # ================= PLUS =================
    if data == "plus":
        d["qty"] += 1

    # ================= MINUS =================
    elif data == "minus":
        if d["qty"] > 1:
            d["qty"] -= 1

    # ================= BUY =================
    elif data == "buy":
        total = d["qty"] * d["harga"]

        keyboard = [
            [InlineKeyboardButton("✅ SUDAH TRANSFER", callback_data="paid")]
        ]

        await query.edit_message_text(
            f"💳 PAYMENT SEWA\n\n"
            f"📦 Paket: {d['paket']}\n"
            f"📊 Qty: {d['qty']}x\n"
            f"💰 Total: Rp{total:,}\n\n"
            f"TRANSFER KE OWNER DAN KLIK KONFIRMASI",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return  # 🔥 WAJIB STOP DI SINI

    # ================= PAID =================
    elif data == "paid":
        total_days = d["qty"] * d["days"]

        await query.edit_message_text(
            "✅ PAYMENT BERHASIL\n\n"
            "🎉 Kamu sekarang PREMIUM!"
        )

        # simpan ke premium (contoh memory)
        print({
            "user_id": uid,
            "paket": d["paket"],
            "expire": time.time() + (total_days * 86400)
        })

        del pending_sewa[uid]
        return

    # ================= UI UPDATE (HANYA SETELAH PILIH PAKET) =================
    if data in ["paket_mingguan", "paket_bulanan", "plus", "minus"]:

        total = d["qty"] * d["harga"]

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="minus"),
                InlineKeyboardButton(str(d["qty"]), callback_data="none"),
                InlineKeyboardButton("➕", callback_data="plus")
            ],
            [
                InlineKeyboardButton("🛒 BUY", callback_data="buy")
            ]
        ]

        await query.edit_message_text(
            f"📦 Paket: {d['paket']}\n"
            f"📊 Qty: {d['qty']}\n"
            f"💰 Total: Rp{total:,}",
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
