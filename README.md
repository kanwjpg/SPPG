# SPPG Manager

Sistem manajemen operasional SPPG (Satuan Pelayanan Pemenuhan Gizi) - Program Makan Bergizi Gratis (MBG).
Dibuat untuk lomba Python - fokus pada manajemen menu & gizi, stok bahan baku, dan checklist keamanan pangan pra-distribusi.

## Menjalankan secara lokal

```
pip install -r requirements.txt
python app.py
```

Buka http://localhost:5000 - login demo: **admin / sppg2026**

Untuk mengisi data contoh (dummy):
```
python seed.py
```

## Deploy ke Render (gratis)

1. Push folder ini ke repo GitHub baru.
2. Buka https://render.com -> New -> Web Service -> hubungkan repo GitHub tadi.
3. Render otomatis mendeteksi `render.yaml`. Kalau tidak, isi manual:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Klik Deploy. Tunggu ~2-3 menit sampai status "Live".
5. Setelah live, jalankan seed data lewat Render Shell (tab "Shell" di dashboard service):
   ```
   python seed.py
   ```

## Catatan
- Database default: SQLite (file lokal `sppg.db`). Di Render, database ini akan reset tiap deploy ulang karena filesystem-nya ephemeral - cukup untuk demo lomba, tapi untuk produksi sungguhan sebaiknya pakai PostgreSQL (tinggal set env var `DATABASE_URL`).
- Ganti `SECRET_KEY` dan password admin sebelum dipakai sungguhan.
