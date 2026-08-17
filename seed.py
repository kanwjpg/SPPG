"""Isi data dummy realistis untuk demo lomba."""
from datetime import date, timedelta
from app import app, db, Sekolah, Menu, MenuItem, BahanBaku, StokTransaksi, ChecklistKeamanan

with app.app_context():
    if Sekolah.query.count() == 0:
        sekolahs = [
            Sekolah(nama="SDN 1 Purwodadi", jumlah_siswa=310),
            Sekolah(nama="SDN 3 Grobogan", jumlah_siswa=245),
            Sekolah(nama="SMPN 2 Purwodadi", jumlah_siswa=480),
        ]
        db.session.add_all(sekolahs)
        db.session.commit()

    if BahanBaku.query.count() == 0:
        bahans = [
            BahanBaku(nama="Beras", satuan="kg", stok_saat_ini=180, stok_minimum=100),
            BahanBaku(nama="Ayam", satuan="kg", stok_saat_ini=25, stok_minimum=40),  # menipis, sengaja
            BahanBaku(nama="Telur", satuan="butir", stok_saat_ini=600, stok_minimum=300),
            BahanBaku(nama="Bayam", satuan="kg", stok_saat_ini=15, stok_minimum=20),  # menipis, sengaja
            BahanBaku(nama="Minyak Goreng", satuan="liter", stok_saat_ini=40, stok_minimum=15),
        ]
        db.session.add_all(bahans)
        db.session.commit()
        for b in bahans:
            db.session.add(StokTransaksi(bahan_id=b.id, jenis="masuk", jumlah=b.stok_saat_ini, keterangan="Stok awal"))
        db.session.commit()

    if Menu.query.count() == 0:
        sekolah1 = Sekolah.query.first()
        m1 = Menu(nama_menu="Nasi Ayam Sayur Bayam", tanggal=date.today(), sekolah_id=sekolah1.id, status="Disiapkan")
        db.session.add(m1)
        db.session.flush()
        db.session.add_all([
            MenuItem(menu_id=m1.id, nama_bahan="Nasi Putih", gram_per_porsi=150, kalori=195, protein=3.6),
            MenuItem(menu_id=m1.id, nama_bahan="Ayam Goreng", gram_per_porsi=80, kalori=200, protein=18),
            MenuItem(menu_id=m1.id, nama_bahan="Tumis Bayam", gram_per_porsi=60, kalori=35, protein=2.5),
        ])

        m2 = Menu(nama_menu="Nasi Telur Balado", tanggal=date.today() - timedelta(days=1), sekolah_id=sekolah1.id, status="Terdistribusi")
        db.session.add(m2)
        db.session.flush()
        db.session.add_all([
            MenuItem(menu_id=m2.id, nama_bahan="Nasi Putih", gram_per_porsi=150, kalori=195, protein=3.6),
            MenuItem(menu_id=m2.id, nama_bahan="Telur Balado", gram_per_porsi=60, kalori=140, protein=9),
        ])
        db.session.commit()

        db.session.add(ChecklistKeamanan(
            menu_id=m2.id, suhu_ok=True, sampel_disimpan=True, waktu_saji_ok=True,
            kebersihan_ok=True, petugas="Siti Aminah"
        ))
        db.session.commit()

    print("Seed data berhasil ditambahkan.")
