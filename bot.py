# ====== Part 1: Setup & Utilities ======

import os
import requests
import json
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from datetime import datetime
from math import ceil

# =================== KONFIGURASI =================== #
TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")

# User/grup yang boleh akses bot
AUTHORIZED_IDS = [5425205882, 2092596833, -1002757263947]

# Link data parfum
NAMA_PARFUM_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1P4BO2jswz3xcngKspWrJeEm70MqalEN7P_BUMBSH7Ns/"
    "gviz/tq?tqx=out:json&gid=0"
)

# Ukuran untuk penjualan/pembelian
VARIAN_BOTOL = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']
VARIAN_CAMPURAN = ['Absolute', 'Isopropyl', 'Alkohol', 'Fixative']
KATEGORI_PEMBELIAN = ['Bibit', 'Botol', 'Campuran']

# State percakapan
CHOOSING, INPUT_DATA, PARFUM_LIST, PARFUM_SEARCH = range(4)

# Data sementara user
user_data = {}

# =================== FUNGSI UTAMA =================== #

def is_authorized(chat_id: int) -> bool:
    return chat_id in AUTHORIZED_IDS

def ambil_data_parfum() -> list:
    try:
        response = requests.get(NAMA_PARFUM_SHEET_URL)
        raw = response.text[47:-2]
        data = json.loads(raw)

        nama_parfum = []
        for row in data["table"]["rows"]:
            nama = row["c"][0]["v"] if row["c"][0] else ""
            if nama:
                nama_parfum.append(nama.strip())
        return sorted(nama_parfum)
    except Exception as e:
        print("⚠️ Gagal ambil data parfum:", e)
        return []

def cari_parfum(keyword: str, daftar: list) -> list:
    keyword = keyword.lower()
    hasil = [item for item in daftar if keyword in item.lower()]
    return hasil

def get_parfum_page(parfum_list: list, page: int, per_page: int = 6):
    total = len(parfum_list)
    max_page = ceil(total / per_page)
    start = (page - 1) * per_page
    end = start + per_page
    items = parfum_list[start:end]

    buttons = [[InlineKeyboardButton(nama, callback_data=f"parfum|{nama}")]
               for nama in items]

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"page|{page-1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton("➡️ Selanjutnya", callback_data=f"page|{page+1}"))
    nav_buttons.append(InlineKeyboardButton("🔍 Cari", callback_data="search|parfum"))

    if nav_buttons:
        buttons.append(nav_buttons)
    return InlineKeyboardMarkup(buttons)
    # ====== Part 2: Start & Pilih Mode ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        await update.message.reply_text("❌ Anda tidak diizinkan menggunakan bot ini.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🛍 Catat Penjualan", callback_data="mode|Penjualan")],
        [InlineKeyboardButton("📦 Catat Pembelian", callback_data="mode|Pembelian")],
        [InlineKeyboardButton("🔍 Cari Nama Parfum", callback_data="search|parfum")]
    ]
    await update.message.reply_text(
        "Selamat datang! Silakan pilih mode:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id
    data = query.data

    if data.startswith("mode|"):
        mode = data.split("|")[1]
        user_data[uid] = {
            "mode": mode,
            "step": "nama",
            "parfum_page": 1,
        }
        await query.edit_message_text(f"📝 Mode {mode} dipilih.\nMasukkan nama {'pembeli' if mode == 'Penjualan' else 'seller'}:")
        return INPUT_DATA

    elif data.startswith("page|"):
        page = int(data.split("|")[1])
        parfum_list = context.bot_data.get("parfum_list", [])
        markup = get_parfum_page(parfum_list, page)
        await query.edit_message_text("📦 Pilih nama parfum:", reply_markup=markup)
        user_data[uid]['parfum_page'] = page
        return PARFUM_LIST

    elif data.startswith("parfum|"):
        nama = data.split("|")[1]
        user_data[uid]['nama_barang'] = nama
        await query.edit_message_text(f"🧴 Parfum dipilih: {nama}")
        user_data[uid]['step'] = 'varian'
        await update.effective_chat.send_message("📐 Pilih varian/parfum:")
        return INPUT_DATA

    elif data == "search|parfum":
        await query.edit_message_text("🔍 Silakan ketik kata kunci parfum:")
        return PARFUM_SEARCH
        # ====== Part 3: Input Data ======

async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    msg = update.message.text
    data = user_data.get(uid)
    step = data.get("step")
    mode = data.get("mode")

    if step == "nama":
        data["nama"] = msg
        data["tanggal"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["step"] = "no_hp"
        await update.message.reply_text("📞 Masukkan nomor HP:")
        return INPUT_DATA

    if step == "no_hp":
        data["no_hp"] = msg
        data["step"] = "alamat"
        await update.message.reply_text("📍 Masukkan alamat:")
        return INPUT_DATA

    if step == "alamat":
        data["alamat"] = msg
        if mode == "Pembelian":
            data["step"] = "kategori"
            keyboard = [[InlineKeyboardButton(kat, callback_data=f"kategori|{kat}")] for kat in KATEGORI_PEMBELIAN]
            await update.message.reply_text("📂 Pilih kategori:", reply_markup=InlineKeyboardMarkup(keyboard))
            return INPUT_DATA
        else:
            data["step"] = "parfum_page"
            parfum_list = context.bot_data.get("parfum_list", [])
            markup = get_parfum_page(parfum_list, 1)
            await update.message.reply_text("📦 Pilih nama parfum:", reply_markup=markup)
            return PARFUM_LIST

    if step == "varian":
        data["varian"] = msg
        data["step"] = "qty"
        await update.message.reply_text("🔢 Masukkan jumlah (Qty):")
        return INPUT_DATA

    if step == "qty":
        try:
            qty = int(msg)
            data["qty"] = qty
            data["step"] = "harga_total"
            await update.message.reply_text("💰 Masukkan harga total (contoh: 25000):")
        except:
            await update.message.reply_text("❗ Jumlah harus angka.")
        return INPUT_DATA

    if step == "harga_total":
        try:
            total = int(''.join(filter(str.isdigit, msg)))
            data["harga_total"] = f"Rp {total:,}".replace(",", ".")
            satuan = total // int(data["qty"])
            data["harga_satuan"] = f"Rp {satuan:,}".replace(",", ".")
        except:
            data["harga_total"] = msg
            data["harga_satuan"] = "Rp -"

        if mode == "Pembelian":
            data["step"] = "link"
            await update.message.reply_text("🔗 Masukkan link pembelian (boleh kosong):")
            return INPUT_DATA
        else:
            return await konfirmasi_data(update, context)

    if step == "link":
        data["link"] = msg
        return await konfirmasi_data(update, context)
        # ====== Part 4: Konfirmasi, Simpan, Search & Main ======

async def konfirmasi_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    data = user_data[uid]
    mode = data.get("mode")

    text = f"📝 Konfirmasi data yang akan disimpan:\n\n"
    text += f"📅 Tanggal: {data.get('tanggal')}\n"
    text += f"📦 Mode: {mode}\n"
    text += f"👤 Nama: {data.get('nama')}\n"
    text += f"📞 No HP: {data.get('no_hp')}\n"
    text += f"📍 Alamat: {data.get('alamat')}\n"
    if mode == "Pembelian":
        text += f"📂 Kategori: {data.get('kategori')}\n"
    text += f"🧴 Parfum: {data.get('nama_barang')}\n"
    text += f"📐 Varian: {data.get('varian')}\n"
    text += f"🔢 Qty: {data.get('qty')}\n"
    text += f"💸 Harga Total: {data.get('harga_total')}\n"
    text += f"💰 Harga Satuan: {data.get('harga_satuan')}\n"
    if mode == "Pembelian":
        text += f"🔗 Link: {data.get('link', '-')}\n"

    keyboard = [
        [
            InlineKeyboardButton("✅ Simpan", callback_data="save_data"),
            InlineKeyboardButton("❌ Batal", callback_data="cancel_data")
        ]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return INPUT_DATA


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id
    data = user_data.get(uid)

    if query.data == "save_data":
        payload = {
            "mode": data.get("mode"),
            "tanggal": data.get("tanggal"),
            "nama": data.get("nama"),
            "no_hp": data.get("no_hp", ""),
            "alamat": data.get("alamat", ""),
            "kategori": data.get("kategori", ""),
            "nama_barang": data.get("nama_barang"),
            "varian": data.get("varian"),
            "qty": str(data.get("qty")),
            "harga_total": data.get("harga_total"),
            "harga_satuan": data.get("harga_satuan"),
            "link": data.get("link", "")
        }
        try:
            requests.post(SCRIPT_URL, data=payload)
            await query.edit_message_text("✅ Data berhasil disimpan!")
        except Exception as e:
            await query.edit_message_text(f"❌ Gagal menyimpan data.\n{e}")
    else:
        await query.edit_message_text("❌ Data dibatalkan.")
    return ConversationHandler.END


async def parfum_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    keyword = update.message.text.strip()
    all_parfum = context.bot_data.get("parfum_list", [])

    hasil = cari_parfum(keyword, all_parfum)
    if not hasil:
        await update.message.reply_text("❌ Tidak ditemukan. Coba keyword lain.")
        return PARFUM_SEARCH

    tombol = [[InlineKeyboardButton(nama, callback_data=f"parfum|{nama}")]
              for nama in hasil[:10]]  # batasi max 10
    tombol.append([InlineKeyboardButton("🔁 Cari lagi", callback_data="search|parfum")])
    await update.message.reply_text(f"🔍 Hasil pencarian: {keyword}", reply_markup=InlineKeyboardMarkup(tombol))
    return PARFUM_LIST


# ========== Bot Start & Main Handler ==========
async def preload_parfum(app):
    parfum_list = ambil_data_parfum()
    app.bot_data["parfum_list"] = parfum_list

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(handle_callback)],
            PARFUM_LIST: [CallbackQueryHandler(handle_callback)],
            PARFUM_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, parfum_search_input)],
            INPUT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_data),
                CallbackQueryHandler(handle_callback),
                CallbackQueryHandler(handle_confirmation)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
