🚀 Panduan Deploy Bot Telegram Pencatatan ke Heroku

1. Buat akun di https://heroku.com dan login
2. Siapkan token bot Telegram kamu (gunakan config vars)
3. Buat aplikasi baru di Heroku
4. Hubungkan ke GitHub atau upload file ZIP ini
5. Tambahkan Config Vars:
   - BOT_TOKEN = (token bot kamu)

6. Jalankan dyno:
   - Heroku > Resources > aktifkan "worker"

7. Selesai! Bot kamu aktif 24/7 🚀

📌 Semua data disimpan ke Google Sheets melalui Web Apps Script:
   https://script.google.com/macros/s/AKfycbzdgMYjD2Ux3QeGBM0yJ9wSq62ol6tepHzZsJPXrybEcjmL5dIWB_fgc7Xng-aYmiY-3g/exec

Catatan:
- Kamu bisa ubah daftar barang dan varian langsung di kode bot.py
- Semua data dikirim sebagai POST ke Google Apps Script dan masuk ke Sheet 'Penjualan' atau 'Pembelian'