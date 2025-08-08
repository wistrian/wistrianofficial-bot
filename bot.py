import os
import requests
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from datetime import datetime

# ===== Konfigurasi =====
TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")

# Hanya ID berikut yang bisa mengakses bot
AUTHORIZED_IDS = [5425205882, 2092596833, -1002757263947]

# Link publikasi sheet Nama Parfum (ubah sesuai publish-to-web link)
NAMA_PARFUM_SHEET_URL = "https://docs.google.com/spreadsheets/d/1P4BO2jswz3xcngKspWrJeEm70MqalEN7P_BUMBSH7Ns/gviz/tq?tqx=out:json&gid=0"

CHOOSING, INPUT_DATA = range(2)
user_data = {}

# Data tetap
ukuran_botol = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']
jenis_campuran = ['Absolute', 'Isopropyl', 'Alkohol', 'Fixative']

# Fungsi cek ID
def is_authorized(chat_id):
    return chat_id in AUTHORIZED_IDS

# Fungsi ambil nama parfum & kategorinya
def ambil_nama_parfum():
    try:
        res = requests.get(NAMA_PARFUM_SHEET_URL)
        text = res.text.replace("/*O_o*/", "").split("(", 1)[1].rsplit(")", 1)[0]
        json_data = json.loads(text)
        rows = json_data['table']['rows']
        parfum_map = {}
        for row in rows[1:]:
            if row and len(row) > 2:
                nama = row['c'][1]['v'] if row['c'][1] else ""
                kategori = row['c'][2]['v'] if row['c'][2] else ""
                if nama:
                    parfum_map[nama] = kategori
        return parfum_map
    except:
        return {}

# ===== Handlers =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        await update.message.reply_text("❌ Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return ConversationHandler.END

    keyboard = [['Penjualan'], ['Pembelian']]
    await update.message.reply_text(
        "Halo! Mau mencatat apa hari ini?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return CHOOSING

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_chat.id] = {
        'mode': update.message.text,
        'step': 'nama'
    }
    await update.message.reply_text("Baik, siapa namanya?", reply_markup=ReplyKeyboardRemove())
    return INPUT_DATA

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
        await update.message.reply_text("Nomor HP (opsional):")
        return INPUT_DATA

    if step == 'no_hp':
        data['no_hp'] = msg
        data['step'] = 'alamat'
        await update.message.reply_text("Alamat (opsional):")
        return INPUT_DATA

    if step == 'alamat':
        data['alamat'] = msg
        data['step'] = 'nama_barang'
        await update.message.reply_text("Tulis atau pilih nama barang (parfum):")
        return INPUT_DATA

    if step == 'nama_barang':
        data['nama_barang'] = msg
        kategori = parfum_map.get(msg)
        if kategori:
            data['kategori'] = kategori
        else:
            if mode == "Pembelian":
                data['step'] = 'kategori_manual'
                await update.message.reply_text("Kategori belum tersedia. Masukkan kategori (Botol / Campuran / Bibit):")
                return INPUT_DATA
        if mode == "Penjualan":
            data['step'] = 'varian'
            await update.message.reply_text("Pilih varian:", reply_markup=ReplyKeyboardMarkup([ukuran_botol], one_time_keyboard=True))
        else:
            if data.get('kategori') == "Botol":
                data['step'] = 'varian'
                await update.message.reply_text("Pilih ukuran botol:", reply_markup=ReplyKeyboardMarkup([ukuran_botol], one_time_keyboard=True))
            elif data.get('kategori') == "Campuran":
                data['step'] = 'varian'
                await update.message.reply_text("Pilih jenis campuran:", reply_markup=ReplyKeyboardMarkup([jenis_campuran], one_time_keyboard=True))
            else:
                data['step'] = 'varian'
                await update.message.reply_text("Masukkan varian:")
        return INPUT_DATA

    if step == 'kategori_manual':
        data['kategori'] = msg
        if msg == "Botol":
            await update.message.reply_text("Pilih ukuran botol:", reply_markup=ReplyKeyboardMarkup([ukuran_botol], one_time_keyboard=True))
        elif msg == "Campuran":
            await update.message.reply_text("Pilih jenis campuran:", reply_markup=ReplyKeyboardMarkup([jenis_campuran], one_time_keyboard=True))
        else:
            await update.message.reply_text("Masukkan varian:")
        data['step'] = 'varian'
        return INPUT_DATA

    if step == 'varian':
        data['varian'] = msg
        data['step'] = 'qty'
        await update.message.reply_text("Jumlah (Qty):")
        return INPUT_DATA

    if step == 'qty':
        try:
            data['qty'] = int(msg)
            data['step'] = 'harga_total'
            await update.message.reply_text("Harga total (contoh: Rp 100000):")
        except:
            await update.message.reply_text("❗ Masukkan angka untuk Qty.")
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
            await update.message.reply_text("Masukkan link pembelian (opsional):")
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
        "nama_barang": data['nama_barang'],
        "varian": data['varian'],
        "qty": str(data['qty']),
        "harga_total": data['harga_total'],
        "harga_satuan": data['harga_satuan'],
        "link": data.get("link", "")
    }
    requests.post(SCRIPT_URL, data=payload)
    ringkasan = "\n".join([f"{k}: {v}" for k, v in payload.items()])
    await update.message.reply_text(f"✅ Data berhasil disimpan:\n\n{ringkasan}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def preload_parfum(app):
    app.bot_data["parfum_map"] = ambil_nama_parfum()

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()
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
