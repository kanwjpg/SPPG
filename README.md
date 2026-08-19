# SPPG Manager

Sistem manajemen operasional SPPG (Satuan Pelayanan Pemenuhan Gizi) - Program Makan Bergizi Gratis (MBG).
Dibuat untuk lomba Python - mencakup alur operasional penuh: dari perencanaan menu & gizi, stok bahan baku,
checklist keamanan pangan, sampai distribusi porsi ke sekolah oleh armada van tiap cabang.

## Fitur

**Distribusi (pusat kendali)**
- Jadwalkan pengantaran: cabang asal, kendaraan, sopir, sekolah tujuan, menu, dan jumlah porsi.
- Pantau van yang sedang di jalan lengkap dengan progress bar dan estimasi waktu tiba.
- Progres diperbarui otomatis tiap 15 detik lewat endpoint `GET /api/distribusi/live` (tanpa reload halaman).
- Alur status: Dijadwalkan -> Berjalan -> Selesai, dengan opsi pembatalan.
- Papan status armada: Tersedia / Dalam Perjalanan / Perawatan.

**Pelacakan van di peta**
- Peta live (Leaflet + OpenStreetMap, gratis tanpa API key) menampilkan posisi van, cabang asal, dan sekolah tujuan.
- Posisi van diperbarui otomatis tiap 10 detik lewat `GET /api/pelacakan/posisi`.
- Posisi dihitung dengan interpolasi antara koordinat cabang dan sekolah berdasarkan progres waktu tempuh
  (perkiraan operasional, bukan GPS perangkat).
- Jarak antar titik dihitung otomatis memakai rumus haversine.

**Data sekolah**
- Setiap sekolah menyimpan alamat, titik koordinat, dan catatan pengantaran.
- Titik lokasi dipilih dengan klik di peta atau dicari otomatis dari alamat (geocoding Nominatim); penanda bisa digeser.
- Sekolah tanpa titik lokasi ditandai jelas di daftar dan tidak muncul di peta pelacakan.
- Catatan pengantaran tampil di halaman detail perjalanan agar terbaca sopir.

**Cabang & Tim**
- Daftar dapur SPPG beserta status operasional (Beroperasi / Standby / Nonaktif) dan beban kapasitas harian.
- Kelola pekerja per cabang (kepala dapur, juru masak, sopir, QC gizi, admin) beserta shift dan status bertugas.
- Kelola armada per cabang, termasuk menandai kendaraan masuk perawatan.

**Menu, stok, dan keamanan pangan** (fitur dasar)
- Perhitungan kalori & protein per menu, kartu stok bahan baku dengan peringatan stok menipis,
  dan checklist keamanan pangan pra-distribusi.

### Aturan bisnis yang dijaga sistem
- Menu yang belum lolos checklist keamanan pangan tidak bisa diberangkatkan.
- Satu kendaraan tidak bisa menjalankan dua perjalanan sekaligus.
- Jumlah porsi tidak boleh melebihi kapasitas kendaraan (divalidasi di browser dan di server).
- Kendaraan yang sedang di jalan tidak bisa diubah statusnya menjadi perawatan.
- Kode cabang dan plat nomor bersifat unik.

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

## Akun demo
- Username: `admin`
- Password: `sppg2026`

Data contoh (3 cabang, 12 pekerja, 5 kendaraan, 5 jadwal distribusi) terisi otomatis saat pertama kali dijalankan,
jadi dashboard langsung berisi tanpa perlu menjalankan `seed.py`.

## Catatan
- Database default: SQLite (file lokal `sppg.db`). Di Render, database ini akan reset tiap deploy ulang karena filesystem-nya ephemeral - cukup untuk demo lomba, tapi untuk produksi sungguhan sebaiknya pakai PostgreSQL (tinggal set env var `DATABASE_URL`).
- Ganti `SECRET_KEY` dan password admin sebelum dipakai sungguhan.
