import os
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzdgMYjD2Ux3QeGBM0yJ9wSq62ol6tepHzZsJPXrybEcjmL5dIWB_fgc7Xng-aYmiY-3g/exec"

CHOOSING, INPUT_DATA = range(2)
user_data = {}

list_barang = ['Parfum A', 'Parfum B', 'Parfum C']
list_varian = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['Penjualan'], ['Pembelian']]
    await update.message.reply_text(
        "Halo! Mau mencatat apa hari ini?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return CHOOSING

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    user_data[update.effective_chat.id] = {'mode': choice}
    await update.message.reply_text("Baik, mari kita mulai. Siapa namanya?")
    return INPUT_DATA

async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = user_data[update.effective_chat.id]
    mode = data['mode']
    msg = update.message.text

    if 'nama' not in data:
        data['nama'] = msg
        data['tanggal'] = datetime.now().strftime("%d-%m-%Y")
        await update.message.reply_text("Nomor HP (opsional):")
        return INPUT_DATA

    elif 'no_hp' not in data:
        data['no_hp'] = msg
        await update.message.reply_text("Alamat (opsional):")
        return INPUT_DATA

    elif 'alamat' not in data:
        data['alamat'] = msg
        await update.message.reply_text("Pilih Nama Barang:", reply_markup=ReplyKeyboardMarkup([list_barang], one_time_keyboard=True))
        return INPUT_DATA

    elif 'nama_barang' not in data:
        data['nama_barang'] = msg
        if mode == 'Penjualan':
            await update.message.reply_text("Pilih Varian:", reply_markup=ReplyKeyboardMarkup([list_varian], one_time_keyboard=True))
        else:
            await update.message.reply_text("Kategori (Botol, Campuran, Bibit):")
        return INPUT_DATA

    elif mode == 'Pembelian' and 'kategori' not in data:
        data['varian'] = msg  # gunakan varian sebagai kategori juga
        await update.message.reply_text("Qty:")
        return INPUT_DATA

    elif mode == 'Penjualan' and 'varian' not in data:
        data['varian'] = msg
        await update.message.reply_text("Qty:")
        return INPUT_DATA

    elif 'qty' not in data:
        try:
            data['qty'] = int(msg)
        except:
            await update.message.reply_text("Masukkan angka untuk Qty.")
            return INPUT_DATA
        await update.message.reply_text("Harga total? (contoh: Rp 100000):")
        return INPUT_DATA

    elif 'harga' not in data:
        data['harga'] = msg
        try:
            harga_angka = int(''.join(filter(str.isdigit, msg)))
            satuan = harga_angka // data['qty']
            data['harga_satuan'] = f"Rp {satuan:,}"
        except:
            data['harga_satuan'] = "Rp -"
        if mode == 'Pembelian':
            await update.message.reply_text("Link pembelian (opsional):")
            return INPUT_DATA
        else:
            return await simpan_data(update)

    elif mode == 'Pembelian' and 'link' not in data:
        data['link'] = msg
        return await simpan_data(update)

async def simpan_data(update: Update):
    data = user_data[update.effective_chat.id]
    payload = {
        "mode": data['mode'],
        "tanggal": data['tanggal'],
        "nama": data['nama'],
        "no_hp": data['no_hp'],
        "alamat": data['alamat'],
        "nama_barang": data['nama_barang'],
        "varian": data['varian'],
        "qty": str(data['qty']),
        "harga_total": data['harga'],
        "harga_satuan": data['harga_satuan'],
        "link": data.get("link", "")
    }
    requests.post(SCRIPT_URL, data=payload)

    result = "\n".join([f"{k}: {v}" for k, v in payload.items()])
    await update.message.reply_text(f"✅ Data berhasil disimpan:\n\n{result}")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            INPUT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_data)],
        },
        fallbacks=[]
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()