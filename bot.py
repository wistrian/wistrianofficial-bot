# ======================= bot.py =======================
import os, json, requests
from math import ceil
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove, InlineQueryResultArticle, InputTextMessageContent, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    InlineQueryHandler, filters, ContextTypes, ConversationHandler
)

# =============== KONFIGURASI ===============
TOKEN = os.getenv("BOT_TOKEN")
SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")

# Hanya ID ini yang boleh pakai bot (user/grup)
AUTHORIZED_IDS = [5425205882, 2092596833, -1002757263947]

# Link sheet nama parfum (gviz json)
NAMA_PARFUM_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1P4BO2jswz3xcngKspWrJeEm70MqalEN7P_BUMBSH7Ns/gviz/tq?tqx=out:json&gid=0"
)

# List opsi
VARIAN_BOTOL = ['Roll On', '15ml', '25ml', '35ml', '55ml', '65ml', '100ml']
VARIAN_CAMPURAN = ['Absolute', 'Isopropyl', 'Alkohol', 'Fixative']
KATEGORI_PEMBELIAN = ['Bibit', 'Botol', 'Campuran']

# State
CHOOSING, INPUT_DATA, PARFUM_LIST, PARFUM_SEARCH, FAST_PENJUALAN, FAST_PEMBELIAN = range(6)

user_data = {}  # data sementara per chat


# =============== UTILITIES ===============
def is_authorized(chat_id: int) -> bool:
    return chat_id in AUTHORIZED_IDS

def _format_rp(n):
    try:
        angka = int(''.join(ch for ch in str(n) if ch.isdigit()))
        return "Rp {:,}".format(angka).replace(",", ".")
    except:
        return str(n)

def _parse_block_to_dict(text: str) -> dict:
    mapping = {
        "nama": "nama",
        "no hp": "no_hp", "no_hp": "no_hp",
        "alamat": "alamat",
        "kategori": "kategori",
        "nama parfum": "nama_parfum",
        "nama_parfum": "nama_parfum",
        "nama barang": "nama_barang",
        "nama_barang": "nama_barang",
        "varian": "varian",
        "qty": "qty", "jumlah": "qty",
        "harga total": "harga_total", "harga_total": "harga_total",
        "harga satuan": "harga_satuan", "harga_satuan": "harga_satuan",
        "link": "link",
    }
    d = {}
    for line in text.splitlines():
        if ":" not in line: continue
        k, v = line.split(":", 1)
        key = k.strip().lower()
        val = v.strip()
        key2 = key.replace(" ", "")
        norm = mapping.get(key) or mapping.get(key2)
        if norm:
            d[norm] = val
    # normalisasi nama_parfum → nama_barang jika perlu
    if "nama_parfum" in d and "nama_barang" not in d:
        d["nama_barang"] = d["nama_parfum"]
    return d

def ambil_data_parfum() -> list:
    try:
        raw = requests.get(NAMA_PARFUM_SHEET_URL, timeout=10).text
        data = json.loads(raw[47:-2])
        names = []
        for row in data["table"]["rows"]:
            nama = row["c"][0]["v"] if row["c"][0] else ""
            if nama: names.append(nama.strip())
        return sorted(names)
    except Exception as e:
        print("Gagal ambil data parfum:", e)
        return []

def cari_parfum(keyword: str, daftar: list) -> list:
    kw = (keyword or "").lower().strip()
    if not kw: return daftar
    return [x for x in daftar if kw in x.lower()]

def parfum_page_markup(parfum_list: list, page: int, per_page: int = 6):
    total = len(parfum_list)
    max_page = max(1, ceil(total / per_page))
    page = max(1, min(page, max_page))
    start, end = (page - 1) * per_page, (page - 1) * per_page + per_page
    items = parfum_list[start:end]
    rows = [[InlineKeyboardButton(n, callback_data=f"parfum|{n}")] for n in items]
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"page|{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️ Selanjutnya", callback_data=f"page|{page+1}"))
    nav.append(InlineKeyboardButton("🔍 Cari", callback_data="search|parfum"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


# =============== START & MENU ===============
async def set_commands(app):
    cmds = [
        BotCommand("start", "Mulai bot & tampilkan menu utama"),
        BotCommand("penjualan", "Catat penjualan"),
        BotCommand("pembelian", "Catat pembelian/stok"),
        BotCommand("cari", "Cari nama parfum"),
        BotCommand("formpenjualan", "Input cepat penjualan (blok teks)"),
        BotCommand("formpembelian", "Input cepat pembelian (blok teks)"),
        BotCommand("batal", "Batalkan proses"),
        BotCommand("bantuan", "Bantuan & panduan"),
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton("🛍 Penjualan", callback_data="mode|Penjualan"),
         InlineKeyboardButton("📦 Pembelian", callback_data="mode|Pembelian")],
        [InlineKeyboardButton("🔍 Cari Parfum", callback_data="search|parfum")],
    ]
    await update.message.reply_text(
        "👋 Selamat datang!\nSilakan pilih menu:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return CHOOSING


# =============== COMMANDS (menu) ===============
async def penjualan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    user_data[cid] = {"mode": "Penjualan", "step": "nama"}
    await update.message.reply_text("🛍 Mode Penjualan\n👤 Masukkan nama pembeli:")
    return INPUT_DATA

async def pembelian_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    user_data[cid] = {"mode": "Pembelian", "step": "nama"}
    await update.message.reply_text("📦 Mode Pembelian\n👤 Masukkan nama seller:")
    return INPUT_DATA

async def cari_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    await update.message.reply_text("🔍 Ketik keyword parfum untuk mencari:")
    return PARFUM_SEARCH

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Bantuan:\n"
        "/start – Menu utama\n"
        "/penjualan – Catat penjualan\n"
        "/pembelian – Catat pembelian\n"
        "/cari – Cari parfum\n"
        "/formpenjualan – Input cepat penjualan (blok teks)\n"
        "/formpembelian – Input cepat pembelian (blok teks)\n"
        "/batal – Batalkan proses"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    user_data.pop(cid, None)
    await update.message.reply_text("❌ Proses dibatalkan.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# =============== CALLBACK (tombol) ===============
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat.id
    data = q.data

    if data.startswith("mode|"):
        mode = data.split("|", 1)[1]
        user_data[cid] = {"mode": mode, "step": "nama"}
        await q.edit_message_text(f"📝 Mode {mode}\n👤 Masukkan nama {'pembeli' if mode=='Penjualan' else 'seller'}:")
        return INPUT_DATA

    if data.startswith("page|"):
        page = int(data.split("|", 1)[1])
        parfums = context.bot_data.get("parfum_list", [])
        await q.edit_message_text("🧴 Pilih nama parfum:", reply_markup=parfum_page_markup(parfums, page))
        user_data[cid]["parfum_page"] = page
        return PARFUM_LIST

    if data.startswith("parfum|"):
        nama = data.split("|", 1)[1]
        user_data[cid]["nama_barang"] = nama
        user_data[cid]["step"] = "varian"
        await q.edit_message_text(f"🧴 Parfum dipilih: {nama}\n📐 Masukkan/pilih varian:")
        return INPUT_DATA

    if data == "search|parfum":
        await q.edit_message_text("🔍 Ketik keyword parfum untuk mencari:")
        return PARFUM_SEARCH

    # Konfirmasi simpan/cancel untuk flow biasa
    if data == "save_data":
        payload = user_data.get(cid, {}).get("payload_confirm")
        if not payload:
            await q.edit_message_text("⚠️ Data tidak ditemukan.")
            return ConversationHandler.END
        try:
            requests.post(SCRIPT_URL, data=payload)
            await q.edit_message_text("✅ Data berhasil disimpan.")
        except Exception as e:
            await q.edit_message_text(f"❌ Gagal menyimpan: {e}")
        user_data.pop(cid, None)
        return ConversationHandler.END
    if data == "cancel_data":
        user_data.pop(cid, None)
        await q.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END

    # Fast mode callbacks (penjualan/pembelian)
    if data == "fast_cancel":
        user_data.pop(cid, None)
        await q.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END
    if data in ("fast_save_penjualan", "fast_save_pembelian"):
        payload = user_data.get(cid, {}).get("fast_payload")
        if not payload:
            await q.edit_message_text("⚠️ Data tidak ditemukan.")
            return ConversationHandler.END
        try:
            requests.post(SCRIPT_URL, data=payload)
            await q.edit_message_text("✅ Data berhasil disimpan.")
        except Exception as e:
            await q.edit_message_text(f"❌ Gagal menyimpan: {e}")
        user_data.pop(cid, None)
        return ConversationHandler.END


# =============== INPUT STEP-BY-STEP ===============
async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    text = update.message.text
    data = user_data.get(cid, {})
    step = data.get("step")
    mode = data.get("mode")

    if step == "nama":
        data["nama"] = text
        data["tanggal"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data["step"] = "no_hp"
        await update.message.reply_text("📞 Masukkan No. HP:")
        return INPUT_DATA

    if step == "no_hp":
        data["no_hp"] = text
        data["step"] = "alamat"
        await update.message.reply_text("📍 Masukkan alamat:")
        return INPUT_DATA

    if step == "alamat":
        data["alamat"] = text
        if mode == "Pembelian":
            data["step"] = "kategori"
            kb = [[InlineKeyboardButton(k, callback_data=f"kategori|{k}")] for k in KATEGORI_PEMBELIAN]
            await update.message.reply_text("📂 Pilih kategori:", reply_markup=InlineKeyboardMarkup(kb))
            return INPUT_DATA
        else:
            # Penjualan → pilih parfum
            parfums = context.bot_data.get("parfum_list", [])
            data["step"] = "parfum"
            await update.message.reply_text("🧴 Pilih nama parfum:", reply_markup=parfum_page_markup(parfums, 1))
            return PARFUM_LIST

    if step == "parfum":
        # kalau user ketik manual
        data["nama_barang"] = text
        data["step"] = "varian"
        await update.message.reply_text("📐 Masukkan varian:")
        return INPUT_DATA

    if step == "kategori":
        kat = text.strip().capitalize()
        if kat not in KATEGORI_PEMBELIAN:
            await update.message.reply_text("❗ Pilih: Bibit / Botol / Campuran")
            return INPUT_DATA
        data["kategori"] = kat
        if kat == "Bibit":
            parfums = context.bot_data.get("parfum_list", [])
            data["step"] = "parfum"
            await update.message.reply_text("🧴 Pilih nama parfum:", reply_markup=parfum_page_markup(parfums, 1))
            return PARFUM_LIST
        elif kat == "Botol":
            data["step"] = "varian"
            kb = [[InlineKeyboardButton(x, callback_data=f"varian|{x}")] for x in VARIAN_BOTOL]
            await update.message.reply_text("📐 Pilih ukuran botol:", reply_markup=InlineKeyboardMarkup(kb))
            return INPUT_DATA
        else:  # Campuran
            data["step"] = "varian"
            kb = [[InlineKeyboardButton(x, callback_data=f"varian|{x}")] for x in VARIAN_CAMPURAN]
            await update.message.reply_text("⚗️ Pilih jenis campuran:", reply_markup=InlineKeyboardMarkup(kb))
            return INPUT_DATA

    if step == "varian":
        data["varian"] = text
        data["step"] = "qty"
        await update.message.reply_text("🔢 Masukkan Qty:")
        return INPUT_DATA

    if step == "qty":
        try:
            data["qty"] = int(''.join(ch for ch in text if ch.isdigit()))
        except:
            await update.message.reply_text("❗ Qty harus angka.")
            return INPUT_DATA
        data["step"] = "harga"
        if mode == "Penjualan":
            await update.message.reply_text("💸 Masukkan *harga satuan* (contoh: 25000):", parse_mode="Markdown")
        else:
            await update.message.reply_text("💰 Masukkan *harga total* (contoh: 100000):", parse_mode="Markdown")
        return INPUT_DATA

    if step == "harga":
        if mode == "Penjualan":
            satuan_int = int(''.join(ch for ch in text if ch.isdigit())) if text else 0
            total_int = satuan_int * int(data["qty"])
            data["harga_satuan"] = _format_rp(satuan_int)
            data["harga_total"] = _format_rp(total_int)
            return await _konfirmasi_and_wait(update, context, data)
        else:
            total_int = int(''.join(ch for ch in text if ch.isdigit())) if text else 0
            qty = int(data["qty"]) or 1
            satuan_int = total_int // qty
            data["harga_total"] = _format_rp(total_int)
            data["harga_satuan"] = _format_rp(satuan_int)
            data["step"] = "link"
            await update.message.reply_text("🔗 Masukkan link pembelian (opsional):")
            return INPUT_DATA

    if step == "link":
        data["link"] = text
        return await _konfirmasi_and_wait(update, context, data)


async def _konfirmasi_and_wait(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict):
    mode = data.get("mode")
    text = (
        "📝 Konfirmasi data:\n\n"
        f"*mode: {mode}*\n"
        f"tanggal: {data.get('tanggal')}\n"
        f"nama: {data.get('nama')}\n"
        f"no_hp: {data.get('no_hp')}\n"
        f"alamat: {data.get('alamat')}\n"
        + (f"kategori: {data.get('kategori')}\n" if mode == "Pembelian" else "")
        + f"nama_barang: {data.get('nama_barang')}\n"
        + f"varian: {data.get('varian')}\n"
        + f"qty: {data.get('qty')}\n"
        + f"harga_satuan: {data.get('harga_satuan')}\n"
        + f"harga_total: {data.get('harga_total')}\n"
        + (f"link: {data.get('link','')}\n" if mode == "Pembelian" else "")
    )
    payload = {
        "mode": mode,
        "tanggal": data.get("tanggal"),
        "nama": data.get("nama"),
        "no_hp": data.get("no_hp",""),
        "alamat": data.get("alamat",""),
        "kategori": data.get("kategori",""),
        "nama_barang": data.get("nama_barang",""),
        "varian": data.get("varian",""),
        "qty": str(data.get("qty","")),
        "harga_satuan": data.get("harga_satuan",""),
        "harga_total": data.get("harga_total",""),
        "link": data.get("link",""),
    }
    user_data[update.effective_chat.id]["payload_confirm"] = payload

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Simpan", callback_data="save_data"),
                                InlineKeyboardButton("❌ Batal", callback_data="cancel_data")]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return INPUT_DATA


# =============== PENCARIAN (prompt) ===============
async def parfum_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kw = update.message.text
    daftar = context.bot_data.get("parfum_list", [])
    hasil = cari_parfum(kw, daftar)
    if not hasil:
        await update.message.reply_text("❌ Tidak ditemukan. Coba keyword lain.")
        return PARFUM_SEARCH
    rows = [[InlineKeyboardButton(n, callback_data=f"parfum|{n}")] for n in hasil[:12]]
    rows.append([InlineKeyboardButton("🔁 Cari lagi", callback_data="search|parfum")])
    await update.message.reply_text(f"🔍 Hasil: {kw}", reply_markup=InlineKeyboardMarkup(rows))
    return PARFUM_LIST


# =============== FAST MODE: PENJUALAN (blok teks) ===============
async def form_penjualan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    template = (
        "🧾 *Input Cepat Penjualan*\n"
        "Salin & isi, lalu kirim sebagai *1 pesan*:\n\n"
        "nama: \n"
        "no_hp: \n"
        "alamat: \n"
        "nama_parfum: \n"
        "varian: \n"
        "qty: \n"
        "harga_satuan: \n\n"
        "_Catatan_: *tanggal* otomatis, *harga_total* = qty × harga_satuan."
    )
    await update.message.reply_text(template, parse_mode="Markdown")
    user_data[cid] = {"mode": "Penjualan", "step": "fast_wait_block"}
    return FAST_PENJUALAN

async def fast_penjualan_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if user_data.get(cid, {}).get("step") != "fast_wait_block" or user_data[cid]["mode"] != "Penjualan":
        await update.message.reply_text("❗ Gunakan /formpenjualan terlebih dahulu.")
        return ConversationHandler.END

    d = _parse_block_to_dict(update.message.text)
    required = ["nama", "nama_barang", "varian", "qty", "harga_satuan"]
    miss = [x for x in required if not d.get(x)]
    if miss:
        await update.message.reply_text("⚠️ Field wajib belum lengkap: " + ", ".join(miss))
        return FAST_PENJUALAN

    try:
        qty = int(''.join(ch for ch in str(d["qty"]) if ch.isdigit()))
        satuan = int(''.join(ch for ch in str(d["harga_satuan"]) if ch.isdigit()))
    except:
        await update.message.reply_text("❗ qty & harga_satuan harus angka.")
        return FAST_PENJUALAN

    total = qty * satuan
    payload = {
        "mode": "Penjualan",
        "tanggal": datetime.now().strftime("%d-%m-%Y"),
        "nama": d.get("nama",""),
        "no_hp": d.get("no_hp",""),
        "alamat": d.get("alamat",""),
        "kategori": "",
        "nama_barang": d.get("nama_barang",""),
        "varian": d.get("varian",""),
        "qty": str(qty),
        "harga_satuan": _format_rp(satuan),
        "harga_total": _format_rp(total),
        "link": ""
    }
    user_data[cid] = {"fast_payload": payload}

    text = (
        "Berikut data yang akan disimpan;\n\n"
        "*mode: Penjualan*\n"
        f"tanggal: {payload['tanggal']}\n"
        f"nama: {payload['nama']}\n"
        f"no_hp: {payload['no_hp']}\n"
        f"alamat: {payload['alamat']}\n"
        f"nama_parfum: {payload['nama_barang']}\n"
        f"varian: {payload['varian']}\n"
        f"qty: {payload['qty']}\n"
        f"harga_satuan: {payload['harga_satuan']}\n"
        f"harga_total: {payload['harga_total']}\n"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Lanjut simpan", callback_data="fast_save_penjualan"),
                                InlineKeyboardButton("❌ Cancel", callback_data="fast_cancel")]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return FAST_PENJUALAN


# =============== FAST MODE: PEMBELIAN (blok teks) ===============
async def form_pembelian_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END

    template = (
        "🧾 *Input Cepat Pembelian*\n"
        "Salin & isi, lalu kirim sebagai *1 pesan*:\n\n"
        "nama: \n"
        "no_hp: \n"
        "alamat: \n"
        "kategori: \n"
        "nama_barang: \n"
        "varian: \n"
        "qty: \n"
        "harga_total: \n"
        "link: \n\n"
        "_Catatan_: kategori tulis salah satu **Bibit / Botol / Campuran**.\n"
        "- Jika *Bibit*: `nama_barang` = nama parfum (pakai inline search).\n"
        "- Jika *Botol*: `nama_barang` = ukuran (15ml, 25ml, …).\n"
        "- Jika *Campuran*: `varian` = jenis (Absolute, Alkohol, …).\n"
        "Tanggal & *harga_satuan* dihitung otomatis."
    )
    await update.message.reply_text(template, parse_mode="Markdown")
    user_data[cid] = {"mode": "Pembelian", "step": "fast_wait_block"}
    return FAST_PEMBELIAN

async def fast_pembelian_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if user_data.get(cid, {}).get("step") != "fast_wait_block" or user_data[cid]["mode"] != "Pembelian":
        await update.message.reply_text("❗ Gunakan /formpembelian terlebih dahulu.")
        return ConversationHandler.END

    d = _parse_block_to_dict(update.message.text)
    for_alias = {"nama_barang": d.get("nama_barang", d.get("nama_parfum",""))}
    d.update(for_alias)

    req = ["nama", "kategori", "qty", "harga_total"]
    miss = [x for x in req if not d.get(x)]
    if miss:
        await update.message.reply_text("⚠️ Field wajib belum lengkap: " + ", ".join(miss))
        return FAST_PEMBELIAN

    try:
        qty = int(''.join(ch for ch in str(d["qty"]) if ch.isdigit()))
        total = int(''.join(ch for ch in str(d["harga_total"]) if ch.isdigit()))
    except:
        await update.message.reply_text("❗ qty & harga_total harus angka.")
        return FAST_PEMBELIAN

    satuan = total // qty if qty else 0
    payload = {
        "mode": "Pembelian",
        "tanggal": datetime.now().strftime("%d-%m-%Y"),
        "nama": d.get("nama",""),
        "no_hp": d.get("no_hp",""),
        "alamat": d.get("alamat",""),
        "kategori": d.get("kategori",""),
        "nama_barang": d.get("nama_barang",""),
        "varian": d.get("varian",""),
        "qty": str(qty),
        "harga_total": _format_rp(total),
        "harga_satuan": _format_rp(satuan),
        "link": d.get("link",""),
    }
    user_data[cid] = {"fast_payload": payload}

    text = (
        "Berikut data yang akan disimpan;\n\n"
        "*mode: Pembelian*\n"
        f"tanggal: {payload['tanggal']}\n"
        f"nama: {payload['nama']}\n"
        f"no_hp: {payload['no_hp']}\n"
        f"alamat: {payload['alamat']}\n"
        f"kategori: {payload['kategori']}\n"
        f"nama_barang: {payload['nama_barang']}\n"
        f"varian: {payload['varian']}\n"
        f"qty: {payload['qty']}\n"
        f"harga_total: {payload['harga_total']}\n"
        f"harga_satuan: {payload['harga_satuan']}\n"
        f"link: {payload['link']}\n"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Lanjut simpan", callback_data="fast_save_pembelian"),
                                InlineKeyboardButton("❌ Cancel", callback_data="fast_cancel")]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return FAST_PEMBELIAN


# =============== INLINE MODE (search) ===============
async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.inline_query
    user_id = q.from_user.id
    # batasi akses
    if AUTHORIZED_IDS and user_id not in AUTHORIZED_IDS:
        await q.answer([], cache_time=1, is_personal=True,
                       switch_pm_text="Buka bot untuk akses", switch_pm_parameter="start")
        return
    daftar = context.bot_data.get("parfum_list", [])
    hasil = cari_parfum(q.query, daftar)[:50]

    results = []
    for i, nama in enumerate(hasil):
        content = InputTextMessageContent(nama)
        results.append(
            InlineQueryResultArticle(
                id=f"p{i}", title=nama,
                description="Pilih untuk kirim nama parfum",
                input_message_content=content
            )
        )
    await q.answer(results, cache_time=0, is_personal=True,
                   switch_pm_text="Buka bot untuk input lengkap", switch_pm_parameter="start")


# =============== MAIN ===============
async def preload_parfum(app):
    app.bot_data["parfum_list"] = ambil_data_parfum()
    await set_commands(app)

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("penjualan", penjualan_cmd),
            CommandHandler("pembelian", pembelian_cmd),
            CommandHandler("cari", cari_cmd),
            CommandHandler("formpenjualan", form_penjualan_cmd),
            CommandHandler("formpembelian", form_pembelian_cmd),
            CommandHandler("batal", cancel),
            CommandHandler("bantuan", bantuan),
        ],
        states={
            CHOOSING: [CallbackQueryHandler(handle_callback)],
            PARFUM_LIST: [CallbackQueryHandler(handle_callback)],
            PARFUM_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, parfum_search_input)],
            INPUT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_data),
                CallbackQueryHandler(handle_callback),
            ],
            FAST_PENJUALAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fast_penjualan_receive),
                CallbackQueryHandler(handle_callback, pattern="^fast_"),
            ],
            FAST_PEMBELIAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fast_pembelian_receive),
                CallbackQueryHandler(handle_callback, pattern="^fast_"),
            ],
        },
        fallbacks=[CommandHandler("batal", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(InlineQueryHandler(handle_inline_query))  # inline mode
    app.run_polling()

if __name__ == "__main__":
    main()
# ===================== end =====================
