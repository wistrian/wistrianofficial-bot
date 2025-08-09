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
        if ":" not in line: 
            continue
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

def ambil_data_parfum(retry=2) -> list:
    for _ in range(max(1, retry)):
        try:
            raw = requests.get(NAMA_PARFUM_SHEET_URL, timeout=10).text
            data = json.loads(raw[47:-2])  # potong wrapper gviz
            names = []
            for row in data["table"]["rows"]:
                nama = row["c"][0]["v"] if row["c"][0] else ""
                if nama: names.append(nama.strip())
            names = sorted(set(names))
            if names:
                print(f"✅ Parfum loaded: {len(names)}")
                return names
        except Exception as e:
            print("⚠️ ambil_data_parfum error:", e)
    print("❌ Gagal load dari sheet, gunakan fallback.")
    return []

def cari_parfum(keyword: str, daftar: list) -> list:
    kw = (keyword or "").strip().lower()
    if not kw: return []
    return [x for x in daftar if kw in x.lower()]

def parfum_page_markup(parfum_list: list, page: int, per_page: int = 6):
    total = len(parfum_list)
    max_page = max(1, ceil(total / per_page)) if total else 1
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
        BotCommand("penjualan", "Kirim format input cepat penjualan"),
        BotCommand("pembelian", "Kirim format input cepat pembelian"),
        BotCommand("cari", "Cari nama parfum (prompt)"),
        BotCommand("formpenjualan", "Input cepat penjualan (blok teks)"),
        BotCommand("formpembelian", "Input cepat pembelian (blok teks)"),
        BotCommand("reload", "Muat ulang daftar parfum"),
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


# =============== HELPER KIRIM TEMPLATE ===============
async def kirim_template_pembelian(send_target, cid):
    template = (
        "📦 *Format input pembelian*\n"
        "Silakan salin & isi sebagai *1 pesan*:\n\n"
        "nama:\n"
        "no_hp:\n"
        "alamat:\n"
        "kategori:\n"
        "nama_barang:\n"
        "varian:\n"
        "qty:\n"
        "harga_total:\n"
        "link:\n\n"
        "📝 *Note*: *kategori* tulis salah satu: *Bibit / Botol / Campuran*.\n"
        "- Jika *Bibit*: `nama_barang` = *nama parfum* (pakai inline `@Bot keyword`).\n"
        "- Jika *Botol*: `nama_barang` = *ukuran* (15ml, 25ml, ...).\n"
        "- Jika *Campuran*: `varian` = *jenis* (Absolute, Alkohol, ...)."
    )
    await send_target.reply_text(template, parse_mode="Markdown")
    user_data[cid] = {"mode": "Pembelian", "step": "fast_wait_block"}
    return FAST_PEMBELIAN

async def kirim_template_penjualan(send_target, cid):
    template = (
        "🛍 *Format input penjualan*\n"
        "Silakan salin & isi sebagai *1 pesan*:\n\n"
        "nama:\n"
        "no_hp:\n"
        "alamat:\n"
        "nama_parfum:\n"
        "varian:\n"
        "qty:\n"
        "harga_satuan:\n\n"
        "📝 *Note*: *tanggal* otomatis, *harga_total* = qty × harga_satuan."
    )
    await send_target.reply_text(template, parse_mode="Markdown")
    user_data[cid] = {"mode": "Penjualan", "step": "fast_wait_block"}
    return FAST_PENJUALAN


# =============== COMMANDS (menu) ===============
async def penjualan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    return await kirim_template_penjualan(update.message, cid)

async def pembelian_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END
    return await kirim_template_pembelian(update.message, cid)

async def form_penjualan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await penjualan_cmd(update, context)

async def form_pembelian_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await pembelian_cmd(update, context)

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Bantuan:\n"
        "/start – Menu utama\n"
        "/penjualan – Format cepat penjualan\n"
        "/pembelian – Format cepat pembelian\n"
        "/cari – Cari parfum (prompt)\n"
        "/formpenjualan – Sama dengan /penjualan\n"
        "/formpembelian – Sama dengan /pembelian\n"
        "/reload – Muat ulang data parfum\n"
        "/batal – Batalkan proses"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    user_data.pop(cid, None)
    await update.message.reply_text("❌ Proses dibatalkan.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    daftar = ambil_data_parfum()
    if not daftar:
        daftar = ["Pink Chiffon","Avril Lavigne","1000 Bunga","Guess Pink"]
    context.bot_data["parfum_list"] = daftar
    await update.message.reply_text(f"🔄 Reload: {len(daftar)} parfum.")


# =============== CALLBACK (tombol) ===============
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat.id
    data = q.data

    if data.startswith("mode|"):
        mode = data.split("|", 1)[1]
        if mode == "Penjualan":
            await q.edit_message_text("🛍 Mode Penjualan (input cepat).")
            return await kirim_template_penjualan(q.message, cid)
        else:
            await q.edit_message_text("📦 Mode Pembelian (input cepat).")
            return await kirim_template_pembelian(q.message, cid)

    if data.startswith("page|"):
        page = int(data.split("|", 1)[1])
        parfums = context.bot_data.get("parfum_list", [])
        await q.edit_message_text("🧴 Pilih nama parfum:", reply_markup=parfum_page_markup(parfums, page))
        return PARFUM_LIST

    if data.startswith("parfum|"):
        nama = data.split("|", 1)[1]
        ud = user_data.get(cid, {})
        # jika sedang validasi bibit dan menunggu pilihan
        if "draft" in ud and ud.get("mode") == "Pembelian":
            d = ud["draft"]; d["nama_barang"] = nama
            # set ulang agar diterima ulang oleh fast_pembelian
            user_data[cid] = {"mode": "Pembelian", "step": "fast_wait_block"}
            class FakeMsg: 
                text = "\n".join([f"{k}: {v}" for k,v in d.items()])
            fake_update = Update(update.update_id, message=type("Msg", (), {"text": FakeMsg.text, "chat": q.message.chat}))
            # panggil handler langsung
            return await fast_pembelian_receive(fake_update, context)

        # jalur biasa
        user_data[cid]["nama_barang"] = nama
        await q.edit_message_text(f"🧴 Parfum dipilih: {nama}")
        return ConversationHandler.END

    if data == "search|parfum":
        await q.edit_message_text("🔍 Ketik keyword parfum (contoh: *pink* / *avril*):", parse_mode="Markdown")
        return PARFUM_SEARCH

    # Konfirmasi fast mode / flow umum
    if data in ("fast_save_penjualan", "fast_save_pembelian", "save_data"):
        payload = user_data.get(cid, {}).get("fast_payload") or user_data.get(cid, {}).get("payload_confirm")
        if not payload:
            await q.edit_message_text("⚠️ Data tidak ditemukan.")
            return ConversationHandler.END
        try:
            requests.post(SCRIPT_URL, data=payload, timeout=10)
            await q.edit_message_text("✅ Data berhasil disimpan.")
        except Exception as e:
            await q.edit_message_text(f"❌ Gagal menyimpan: {e}")
        user_data.pop(cid, None)
        return ConversationHandler.END

    if data in ("fast_cancel", "cancel_data"):
        user_data.pop(cid, None)
        await q.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END


# =============== PENCARIAN (PROMPT) ===============
async def cari_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_authorized(cid):
        await update.message.reply_text("❌ Anda tidak diizinkan.")
        return ConversationHandler.END

    if not context.bot_data.get("parfum_list"):
        await update.message.reply_text("⚠️ Data parfum belum termuat. Coba /reload lalu ulangi /cari.")
        return ConversationHandler.END

    await update.message.reply_text("🔍 Ketik keyword parfum (mis: *pink* / *avril*):", parse_mode="Markdown")
    return PARFUM_SEARCH

async def parfum_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kw = update.message.text
    daftar = context.bot_data.get("parfum_list", [])
    if not daftar:
        await update.message.reply_text("⚠️ Data parfum belum termuat. Coba /reload.")
        return ConversationHandler.END

    hasil = cari_parfum(kw, daftar)
    if not hasil:
        await update.message.reply_text("❌ Tidak ditemukan. Coba keyword lain (cukup sebagian kata).")
        return PARFUM_SEARCH

    rows = [[InlineKeyboardButton(n, callback_data=f"parfum|{n}")] for n in hasil[:12]]
    rows.append([InlineKeyboardButton("🔁 Cari lagi", callback_data="search|parfum")])
    await update.message.reply_text(f"🔍 Hasil: *{kw}*", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(rows))
    return PARFUM_LIST


# =============== FAST MODE: PENJUALAN (blok teks) ===============
async def fast_penjualan_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if user_data.get(cid, {}).get("step") != "fast_wait_block" or user_data[cid].get("mode") != "Penjualan":
        await update.message.reply_text("❗ Gunakan /penjualan terlebih dahulu.")
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
async def fast_pembelian_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if user_data.get(cid, {}).get("step") != "fast_wait_block" or user_data[cid].get("mode") != "Pembelian":
        await update.message.reply_text("❗ Gunakan /pembelian terlebih dahulu.")
        return ConversationHandler.END

    d = _parse_block_to_dict(update.message.text)
    if "nama_barang" not in d and "nama_parfum" in d:
        d["nama_barang"] = d["nama_parfum"]

    req = ["nama", "kategori", "qty", "harga_total"]
    miss = [x for x in req if not d.get(x)]
    if miss:
        await update.message.reply_text("⚠️ Field wajib belum lengkap: " + ", ".join(miss))
        return FAST_PEMBELIAN

    kategori = (d.get("kategori") or "").strip().capitalize()
    if kategori not in KATEGORI_PEMBELIAN:
        await update.message.reply_text("❗ Kategori harus *Bibit / Botol / Campuran*.", parse_mode="Markdown")
        return FAST_PEMBELIAN

    # Validasi turunan kategori
    if kategori == "Botol":
        if (d.get("nama_barang") or "") not in VARIAN_BOTOL:
            await update.message.reply_text(
                "⚠️ Untuk *Botol*, `nama_barang` harus salah satu ukuran: " + ", ".join(VARIAN_BOTOL),
                parse_mode="Markdown")
            return FAST_PEMBELIAN
    if kategori == "Campuran":
        if (d.get("varian") or "") not in VARIAN_CAMPURAN:
            await update.message.reply_text(
                "⚠️ Untuk *Campuran*, `varian` harus salah satu: " + ", ".join(VARIAN_CAMPURAN),
                parse_mode="Markdown")
            return FAST_PEMBELIAN
    if kategori == "Bibit":
        daftar = context.bot_data.get("parfum_list", [])
        if daftar and d.get("nama_barang"):
            if not any(d["nama_barang"].lower() == x.lower() for x in daftar):
                suggestions = [x for x in daftar if d["nama_barang"].lower() in x.lower()][:8]
                if suggestions:
                    rows = [[InlineKeyboardButton(x, callback_data=f"parfum|{x}")] for x in suggestions]
                    await update.message.reply_text(
                        "🔎 Nama parfum tidak persis ditemukan. Pilih salah satu:",
                        reply_markup=InlineKeyboardMarkup(rows)
                    )
                    user_data[cid] = {"mode":"Pembelian","draft":d}
                    return PARFUM_LIST
                else:
                    await update.message.reply_text("❌ Nama parfum tidak ditemukan di database. Coba keyword via /cari.")
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
        "kategori": kategori,
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
    if AUTHORIZED_IDS and user_id not in AUTHORIZED_IDS:
        await q.answer([], cache_time=1, is_personal=True,
                       switch_pm_text="Buka bot untuk akses", switch_pm_parameter="start")
        return
    daftar = context.bot_data.get("parfum_list", [])
    if not daftar:
        daftar = ["Pink Chiffon","Avril Lavigne","1000 Bunga","Guess Pink"]
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
    daftar = ambil_data_parfum()
    if not daftar:
        daftar = ["Pink Chiffon","Avril Lavigne","1000 Bunga","Guess Pink"]
        print("⚠️ Pakai fallback parfum sementara.")
    app.bot_data["parfum_list"] = daftar
    await set_commands(app)

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(preload_parfum).build()

    # Commands yang aktif di semua state
    always_cmds = [
        CommandHandler("start", start),
        CommandHandler("penjualan", penjualan_cmd),
        CommandHandler("pembelian", pembelian_cmd),
        CommandHandler("formpenjualan", form_penjualan_cmd),
        CommandHandler("formpembelian", form_pembelian_cmd),
        CommandHandler("cari", cari_cmd),
        CommandHandler("reload", reload_cmd),
        CommandHandler("bantuan", bantuan),
        CommandHandler("batal", cancel),
    ]

    conv = ConversationHandler(
        entry_points=always_cmds,
        states={
            CHOOSING: [CallbackQueryHandler(handle_callback), *always_cmds],
            PARFUM_LIST: [CallbackQueryHandler(handle_callback), *always_cmds],
            PARFUM_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, parfum_search_input),
                CallbackQueryHandler(handle_callback),
                *always_cmds
            ],
            INPUT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: ConversationHandler.END),
                CallbackQueryHandler(handle_callback),
                *always_cmds
            ],
            FAST_PENJUALAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fast_penjualan_receive),
                CallbackQueryHandler(handle_callback, pattern="^fast_"),
                *always_cmds
            ],
            FAST_PEMBELIAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fast_pembelian_receive),
                CallbackQueryHandler(handle_callback, pattern="^fast_"),
                *always_cmds
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
