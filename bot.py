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

# =================== KONFIGURASI =================== #
TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")

# Ganti ID di bawah ini sesuai yang boleh mengakses bot
AUTHORIZED_IDS = [5425205882, 2092596833, -1002757263947]

# Link data parfum
NAMA_PARFUM_SHEET_URL = "https://docs.google.com/spreadsheets/d/1P4BO2jswz3xcngKspWrJeEm70MqalEN7P_BUMBSH7Ns/gviz/tq?tqx=out:json&gid=0"

CHOOSING, INPUT_DATA, SEARCH_PARFUM = range(3)
user_data = {}
ukuran_botol = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']
jenis_campuran = ['Absolute', 'Isopropyl', 'Alkohol', 'Fixative']


# =================== FUNGSI =================== #
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
                result[nama.strip().lower()] = kategori
        return result
    except Exception as e:
        print("Gagal ambil nama parfum:", e)
        return {}

def cari_parfum(keyword, parfum_map):
    keyword = keyword.lower()
    return [nama.title() for nama in parfum_map if keyword in nama]


# =================== HANDLER =================== #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if not is_authorized(uid):
        await update.message.reply_text("❌ Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📝 Penjualan", callback_data="Penjualan")],
        [InlineKeyboardButton("📦 Pembelian", callback_data="Pembelian")],
        [InlineKeyboardButton("🔍 Cari Nama Parfum", callback_data="CariParfum")]
    ]
    await update.message.reply_text(
        "Halo! Mau mencatat apa hari ini?\n\nSilakan pilih salah satu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING

async def pilih_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id
    mode = query.data

    if mode == "CariParfum":
        await query.edit_message_text("🔍 Silakan ketik nama parfum yang ingin dicari:")
        return SEARCH_PARFUM

    user_data[uid] = {
        'mode': mode,
        'step': 'nama'
    }

    await query.edit_message_text("👤 Masukkan nama pelanggan (Penjualan) atau seller (Pembelian):")
    return INPUT_DATA

async def search_parfum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text
    parfum_map = context.bot_data.get("parfum_map", {})
    hasil = cari_parfum(keyword, parfum_map)

    if hasil:
        buttons = [[KeyboardButton(nama)] for nama in hasil]
        await update.message.reply_text("🧴 Hasil pencarian:", reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))
    else:
        await update.message.reply_text("⛔ Tidak ditemukan. Coba lagi.")

    return ConversationHandler.END


async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    msg = update.message.text
    data = user_data.get(uid, {})
    step = data.get('step')
    mode = data.get('mode')
    parfum_map = context.bot_data.get("parfum_map", {})

    if step == 'nama':
        data['nama'] = msg
        data['tanggal'] = datetime.now().strftime("%d-%m-%Y")
        data['step'] = 'no_hp'
        await update.message.reply_text("📞 Nomor HP (opsional):")
        return INPUT_DATA

    if step == 'no_hp':
        data['no_hp'] = msg
        data['step'] = 'alamat'
        await update.message.reply_text("📍 Alamat (opsional):")
        return INPUT_DATA

    if step == 'alamat':
        if mode == "Penjualan":
            data['step'] = 'nama_barang'
            await update.message.reply_text("🧴 Masukkan nama parfum:")
        else:
            data['step'] = 'kategori'
            await update.message.reply_text("📂 Masukkan kategori: Bibit / Botol / Campuran")
        return INPUT_DATA

    if step == 'kategori':
        kategori = msg.strip().lower()
        data['kategori'] = kategori
        if kategori == "bibit":
            data['step'] = 'nama_barang'
            await update.message.reply_text("🧴 Masukkan nama parfum:")
        elif kategori == "botol":
            data['step'] = 'varian'
            await update.message.reply_text("📐 Pilih ukuran botol:", reply_markup=InlineKeyboardMarkup.from_column(ukuran_botol))
        elif kategori == "campuran":
            data['step'] = 'varian'
            await update.message.reply_text("⚗️ Pilih jenis campuran:", reply_markup=InlineKeyboardMarkup.from_column(jenis_campuran))
        else:
            await update.message.reply_text("❌ Kategori tidak valid. Gunakan: Bibit, Botol, Campuran")
        return INPUT_DATA

    if step == 'nama_barang':
        data['nama_barang'] = msg
        kategori = parfum_map.get(msg.lower())
        if kategori:
            data['kategori'] = kategori
        data['step'] = 'varian'
        await update.message.reply_text("🧪 Masukkan varian:")
        return INPUT_DATA

    if step == 'varian':
        data['varian'] = msg
        data['step'] = 'qty'
        await update.message.reply_text("🔢 Jumlah (Qty):")
        return INPUT_DATA

    if step == 'qty':
        try:
            data['qty'] = int(msg)
            data['step'] = 'harga_total'
            await update.message.reply_text("💰 Harga total (contoh: Rp 100000):")
        except:
            await update.message.reply_text("❗ Masukkan angka yang valid untuk Qty.")
        return INPUT_DATA

    if step == 'harga_total':
        data['harga_total'] = msg
        try:
            angka = int(''.join(filter(str.isdigit, msg)))
            satuan = angka // data['qty']
            data['harga_satuan'] = f"Rp {satuan:,}"
        except:
            data['harga_satuan'] = "Rp -"

        if mode == "Pembelian":
            data['step'] = 'link'
            await update.message.reply_text("🔗 Link pembelian (opsional):")
            return INPUT_DATA
        else:
            return await simpan_data(update, context)

    if step == 'link':
        data['link'] = msg
        return await simpan_data(update, context)


async def simpan_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    data = user_data[uid]
    payload = {
        "mode": data['mode'],
        "tanggal": data['tanggal'],
        "nama": data['nama'],
        "no_hp": data.get("no_hp", ""),
        "alamat": data.get("alamat", ""),
        "kategori": data.get("kategori", ""),
        "nama_barang": data.get("nama_barang", ""),
        "varian": data['varian'],
        "qty": str(data['qty']),
        "harga_total": data['harga_total'],
        "harga_satuan": data['harga_satuan'],
        "link": data.get("link", "")
    }

    try:
        requests.post(SCRIPT_URL, data=payload)
        ringkasan = "\n".join([f"{k}: {v}" for k, v in payload.items()])
        await update.message.reply_text(f"✅ Data berhasil disimpan:\n\n{ringkasan}")
    except:
        await update.message.reply_text("❌ Gagal mengirim data ke spreadsheet.")
    return ConversationHandler.END


# =================== START BOT =================== #
async def preload_parfum(app):
    app.bot_data["parfum_map"] = ambil_nama_parfum()

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(pilih_mode)],
            INPUT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_data)],
            SEARCH_PARFUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_parfum)]
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
