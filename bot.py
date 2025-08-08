# ===== bot.py Part 1 =====

import os
import requests
import json
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from datetime import datetime

# ========== KONFIGURASI ========== #
TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")

AUTHORIZED_IDS = [5425205882, 2092596833, -1002757263947]
NAMA_PARFUM_SHEET_URL = "https://docs.google.com/spreadsheets/d/1P4BO2jswz3xcngKspWrJeEm70MqalEN7P_BUMBSH7Ns/gviz/tq?tqx=out:json&gid=0"

CHOOSING, INPUT_DATA = range(2)
user_data = {}

ukuran_botol = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']
jenis_campuran = ['Absolute', 'Isopropyl', 'Alkohol', 'Fixative']

# ========== UTILITAS ========== #
def is_authorized(chat_id):
    return chat_id in AUTHORIZED_IDS

def ambil_nama_parfum():
    try:
        raw = requests.get(NAMA_PARFUM_SHEET_URL).text
        json_data = json.loads(raw[47:-2])
        result = {}
        for row in json_data["table"]["rows"]:
            nama = row["c"][0]["v"] if row["c"][0] else ""
            kategori = row["c"][1]["v"] if row["c"][1] else ""
            if nama:
                result[nama.lower()] = kategori
        return result
    except Exception as e:
        print("Gagal ambil nama parfum:", e)
        return {}
# ===== bot.py Part 2 =====

# ========== HANDLER START ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if not is_authorized(uid):
        await update.message.reply_text("❌ Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🛍 Catat Penjualan", callback_data="Penjualan"),
         InlineKeyboardButton("📦 Catat Pembelian", callback_data="Pembelian")],
        [InlineKeyboardButton("🔍 Cari Parfum", callback_data="cari_parfum")]
    ]
    await update.message.reply_text(
        "👋 Selamat datang di Bot Manajemen Parfum!\n\nSilakan pilih menu di bawah ini:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING

# ========== HANDLER PILIH MENU ==========
async def pilih_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id
    pilihan = query.data

    if pilihan == "cari_parfum":
        await query.edit_message_text("🔍 Silakan ketik nama parfum yang ingin dicari:")
        user_data[uid] = {"mode": "cari"}
        return INPUT_DATA

    user_data[uid] = {
        'mode': pilihan,
        'step': 'nama'
    }
    await query.edit_message_text("👤 Langkah 1/8\nMasukkan nama pembeli/seller:")
    return INPUT_DATA
    # ===== bot.py Part 3 =====

async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    msg = update.message.text
    data = user_data.get(uid, {})
    step = data.get('step')
    mode = data.get('mode')
    parfum_map = context.bot_data.get("parfum_map", {})

    # 🔍 Mode pencarian nama parfum
    if mode == "cari":
        keyword = msg.lower()
        hasil = [nama for nama in parfum_map if keyword in nama]
        if hasil:
            tombol = [[InlineKeyboardButton(nama.upper(), callback_data=f"pilih_parfum_{nama}")] for nama in hasil[:10]]
            tombol.append([InlineKeyboardButton("❌ Batal", callback_data="batal")])
            await update.message.reply_text("🔎 Hasil pencarian:", reply_markup=InlineKeyboardMarkup(tombol))
        else:
            await update.message.reply_text("🚫 Tidak ditemukan. Coba lagi.")
        return INPUT_DATA

    # STEP 1
    if step == 'nama':
        data['nama'] = msg
        data['tanggal'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['step'] = 'no_hp'
        await update.message.reply_text("📞 Langkah 2/8\nMasukkan nomor HP:")
        return INPUT_DATA

    # STEP 2
    if step == 'no_hp':
        data['no_hp'] = msg
        data['step'] = 'alamat'
        await update.message.reply_text("📍 Langkah 3/8\nMasukkan alamat:")
        return INPUT_DATA

    # STEP 3
    if step == 'alamat':
        data['alamat'] = msg
        data['step'] = 'nama_barang'
        await update.message.reply_text("🧴 Langkah 4/8\nTulis nama parfum atau klik 🔍 Cari parfum.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Cari parfum", callback_data="cari_parfum")],
                [InlineKeyboardButton("❌ Batal", callback_data="batal")]
            ])
        )
        return INPUT_DATA

    # STEP 4
    if step == 'nama_barang':
        data['nama_barang'] = msg
        kategori = parfum_map.get(msg.lower())
        data['kategori'] = kategori if kategori else "Manual"
        data['step'] = 'varian'

        if mode == "Penjualan" or kategori == "Botol":
            tombol = [[InlineKeyboardButton(ukuran, callback_data=f"varian_{ukuran}")] for ukuran in ukuran_botol]
            await update.message.reply_text("📐 Langkah 5/8\nPilih varian botol:",
                reply_markup=InlineKeyboardMarkup(tombol))
        elif kategori == "Campuran":
            tombol = [[InlineKeyboardButton(jenis, callback_data=f"varian_{jenis}")] for jenis in jenis_campuran]
            await update.message.reply_text("⚗️ Langkah 5/8\nPilih jenis campuran:",
                reply_markup=InlineKeyboardMarkup(tombol))
        else:
            await update.message.reply_text("🧪 Langkah 5/8\nMasukkan varian:")
        return INPUT_DATA

    # STEP 5 (jika input manual varian)
    if step == 'varian':
        data['varian'] = msg
        data['step'] = 'qty'
        await update.message.reply_text("🔢 Langkah 6/8\nMasukkan jumlah (Qty):")
        return INPUT_DATA

    # STEP 6
    if step == 'qty':
        try:
            data['qty'] = int(msg)
            data['step'] = 'harga_total'
            await update.message.reply_text("💰 Langkah 7/8\nMasukkan harga total (cth: 10000):")
        except:
            await update.message.reply_text("❗ Masukkan angka valid untuk Qty.")
        return INPUT_DATA

    # STEP 7
    if step == 'harga_total':
        try:
            total = int(''.join(filter(str.isdigit, msg)))
            data['harga_total'] = f"Rp. {total:,}".replace(",", ".")
            satuan = total // data['qty']
            data['harga_satuan'] = f"Rp. {satuan:,}".replace(",", ".")
        except:
            data['harga_total'] = msg
            data['harga_satuan'] = "Rp. -"

        if mode == "Pembelian":
            data['step'] = 'link'
            await update.message.reply_text("🔗 Langkah 8/8\nMasukkan link pembelian (boleh dikosongkan):")
            return INPUT_DATA
        else:
            return await simpan_data(update, context)

    # STEP 8 (link pembelian)
    if step == 'link':
        data['link'] = msg
        return await simpan_data(update, context)
        # ===== bot.py Part 4 =====

async def simpan_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    data = user_data.get(uid)
    if not data:
        await update.message.reply_text("❌ Data tidak ditemukan.")
        return ConversationHandler.END

    payload = {
        "mode": data['mode'],
        "tanggal": data['tanggal'],
        "nama": data['nama'],
        "no_hp": data.get("no_hp", ""),
        "alamat": data.get("alamat", ""),
        "kategori": data.get("kategori", ""),
        "nama_barang": data['nama_barang'],
        "varian": data['varian'],
        "qty": str(data['qty']),
        "harga_total": data['harga_total'],
        "harga_satuan": data['harga_satuan'],
        "link": data.get("link", "")
    }

    # Kirim ke Google Apps Script
    try:
        requests.post(SCRIPT_URL, data=payload)
        ringkasan = "\n".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in payload.items()])
        await update.message.reply_text(f"✅ Data berhasil disimpan:\n\n{ringkasan}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal simpan data: {e}")

    user_data.pop(uid, None)
    return ConversationHandler.END

# Callback dari tombol varian (ex: varian_15ml)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id
    data = user_data.get(uid, {})
    callback_data = query.data

    if callback_data.startswith("varian_"):
        varian = callback_data.replace("varian_", "")
        data["varian"] = varian
        data["step"] = "qty"
        await query.edit_message_text("🔢 Langkah 6/8\nMasukkan jumlah (Qty):")
        return INPUT_DATA

    if callback_data.startswith("pilih_parfum_"):
        nama = callback_data.replace("pilih_parfum_", "")
        data = user_data[uid]
        data["nama_barang"] = nama
        data["kategori"] = context.bot_data["parfum_map"].get(nama.lower(), "Manual")
        data["step"] = "varian"
        await query.edit_message_text(f"✅ Parfum dipilih: {nama}\n\n🧪 Sekarang masukkan varian:")
        return INPUT_DATA

    if callback_data == "cari_parfum":
        data["mode"] = "cari"
        await query.edit_message_text("🔍 Silakan ketik nama parfum yang ingin dicari:")
        return INPUT_DATA

    if callback_data == "batal":
        user_data.pop(uid, None)
        await query.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END

# Perintah /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    user_data.pop(uid, None)
    await update.message.reply_text("❌ Input dibatalkan.")
    return ConversationHandler.END

# Preload nama parfum dari sheet
async def preload_parfum(app):
    app.bot_data["parfum_map"] = ambil_nama_parfum()

# MAIN
def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(pilih_mode)],
            INPUT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_data),
                CallbackQueryHandler(handle_callback)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
