import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sppg-dev-secret-key-ganti-di-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'sppg.db')).replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nama = db.Column(db.String(120), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Sekolah(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(150), nullable=False)
    jumlah_siswa = db.Column(db.Integer, nullable=False, default=0)


class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False, default=date.today)
    nama_menu = db.Column(db.String(150), nullable=False)
    sekolah_id = db.Column(db.Integer, db.ForeignKey('sekolah.id'), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Disiapkan')  # Disiapkan / Siap Distribusi / Terdistribusi

    sekolah = db.relationship('Sekolah', backref='menus')
    items = db.relationship('MenuItem', backref='menu', cascade='all, delete-orphan')
    checklist = db.relationship('ChecklistKeamanan', backref='menu', uselist=False, cascade='all, delete-orphan')

    @property
    def total_kalori(self):
        return sum(i.kalori for i in self.items)

    @property
    def total_protein(self):
        return sum(i.protein for i in self.items)


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    nama_bahan = db.Column(db.String(120), nullable=False)
    gram_per_porsi = db.Column(db.Float, nullable=False, default=0)
    kalori = db.Column(db.Float, nullable=False, default=0)
    protein = db.Column(db.Float, nullable=False, default=0)


class BahanBaku(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(120), nullable=False)
    satuan = db.Column(db.String(20), nullable=False, default='kg')
    stok_saat_ini = db.Column(db.Float, nullable=False, default=0)
    stok_minimum = db.Column(db.Float, nullable=False, default=0)

    @property
    def status_stok(self):
        return 'MENIPIS' if self.stok_saat_ini <= self.stok_minimum else 'AMAN'


class StokTransaksi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bahan_id = db.Column(db.Integer, db.ForeignKey('bahan_baku.id'), nullable=False)
    jenis = db.Column(db.String(10), nullable=False)  # masuk / keluar
    jumlah = db.Column(db.Float, nullable=False)
    tanggal = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    keterangan = db.Column(db.String(200))

    bahan = db.relationship('BahanBaku', backref=db.backref('transaksi', cascade='all, delete-orphan'))


class ChecklistKeamanan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False, unique=True)
    suhu_ok = db.Column(db.Boolean, default=False)
    sampel_disimpan = db.Column(db.Boolean, default=False)
    waktu_saji_ok = db.Column(db.Boolean, default=False)
    kebersihan_ok = db.Column(db.Boolean, default=False)
    petugas = db.Column(db.String(120))
    dicatat_pada = db.Column(db.DateTime)

    @property
    def lolos(self):
        return all([self.suhu_ok, self.sampel_disimpan, self.waktu_saji_ok, self.kebersihan_ok])


class Cabang(db.Model):
    """Dapur / unit SPPG. Satu cabang punya pekerja, armada, dan jadwal distribusi."""
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(150), nullable=False)
    kode = db.Column(db.String(20), unique=True, nullable=False)
    alamat = db.Column(db.String(250))
    kapasitas_porsi = db.Column(db.Integer, nullable=False, default=0)
    kepala = db.Column(db.String(120))
    telepon = db.Column(db.String(30))
    aktif = db.Column(db.Boolean, default=True)

    pekerja = db.relationship('Pekerja', backref='cabang', cascade='all, delete-orphan')
    kendaraan = db.relationship('Kendaraan', backref='cabang', cascade='all, delete-orphan')
    distribusi = db.relationship('Distribusi', backref='cabang', cascade='all, delete-orphan')

    @property
    def distribusi_berjalan(self):
        return [d for d in self.distribusi if d.status == 'Berjalan']

    @property
    def porsi_hari_ini(self):
        return sum(d.jumlah_porsi for d in self.distribusi if d.tanggal == date.today())

    @property
    def beban_kapasitas(self):
        """Persen pemakaian kapasitas dapur hari ini."""
        if not self.kapasitas_porsi:
            return 0
        return min(100, round(self.porsi_hari_ini / self.kapasitas_porsi * 100))

    @property
    def status_operasional(self):
        if not self.aktif:
            return 'Nonaktif'
        return 'Beroperasi' if self.distribusi_berjalan else 'Standby'

    @property
    def pekerja_bertugas(self):
        return [p for p in self.pekerja if p.bertugas]


class Pekerja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(120), nullable=False)
    peran = db.Column(db.String(50), nullable=False, default='Juru Masak')  # Kepala Dapur / Juru Masak / Sopir / QC Gizi / Admin
    cabang_id = db.Column(db.Integer, db.ForeignKey('cabang.id'), nullable=False)
    telepon = db.Column(db.String(30))
    shift = db.Column(db.String(20), default='Pagi')  # Pagi / Siang
    bertugas = db.Column(db.Boolean, default=True)

    @property
    def inisial(self):
        bagian = [b for b in self.nama.split() if b]
        if len(bagian) >= 2:
            return (bagian[0][0] + bagian[1][0]).upper()
        return self.nama[:2].upper() if self.nama else '?'


class Kendaraan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plat = db.Column(db.String(20), unique=True, nullable=False)
    jenis = db.Column(db.String(60), nullable=False, default='Van')  # Van / Pikap / Motor Box
    model = db.Column(db.String(80))
    kapasitas_porsi = db.Column(db.Integer, nullable=False, default=0)
    cabang_id = db.Column(db.Integer, db.ForeignKey('cabang.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Tersedia')  # Tersedia / Dalam Perjalanan / Perawatan

    distribusi = db.relationship('Distribusi', backref='kendaraan')

    @property
    def perjalanan_aktif(self):
        return next((d for d in self.distribusi if d.status == 'Berjalan'), None)


class Distribusi(db.Model):
    """Satu perjalanan pengantaran: dari cabang ke satu sekolah."""
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(30), unique=True, nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=date.today)
    cabang_id = db.Column(db.Integer, db.ForeignKey('cabang.id'), nullable=False)
    kendaraan_id = db.Column(db.Integer, db.ForeignKey('kendaraan.id'), nullable=False)
    sopir_id = db.Column(db.Integer, db.ForeignKey('pekerja.id'), nullable=True)
    sekolah_id = db.Column(db.Integer, db.ForeignKey('sekolah.id'), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=True)
    jumlah_porsi = db.Column(db.Integer, nullable=False, default=0)
    jarak_km = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), nullable=False, default='Dijadwalkan')  # Dijadwalkan / Berjalan / Selesai / Batal
    berangkat_pada = db.Column(db.DateTime)
    tiba_pada = db.Column(db.DateTime)
    catatan = db.Column(db.String(250))

    sopir = db.relationship('Pekerja', backref='perjalanan')
    sekolah = db.relationship('Sekolah', backref='distribusi')
    menu = db.relationship('Menu', backref='distribusi')

    ESTIMASI_MENIT = 45  # perkiraan durasi satu rit

    @property
    def menit_berjalan(self):
        if not self.berangkat_pada:
            return 0
        akhir = self.tiba_pada or datetime.utcnow()
        return max(0, int((akhir - self.berangkat_pada).total_seconds() // 60))

    @property
    def progres(self):
        """Perkiraan progres perjalanan dalam persen, untuk progress bar live."""
        if self.status == 'Selesai':
            return 100
        if self.status != 'Berjalan':
            return 0
        return max(5, min(95, round(self.menit_berjalan / self.ESTIMASI_MENIT * 100)))

    @property
    def sisa_menit(self):
        return max(0, self.ESTIMASI_MENIT - self.menit_berjalan)

    @property
    def warna_status(self):
        return {
            'Dijadwalkan': 'secondary',
            'Berjalan': 'warning',
            'Selesai': 'success',
            'Batal': 'danger',
        }.get(self.status, 'secondary')


# ---------------- AUTH HELPERS ----------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_user():
    nama = session.get('nama')
    sidebar_menu_hari_ini = 0
    sidebar_stok_menipis = 0
    sidebar_distribusi_jalan = 0
    if session.get('user_id'):
        sidebar_menu_hari_ini = Menu.query.filter_by(tanggal=date.today()).count()
        sidebar_stok_menipis = len([b for b in BahanBaku.query.all() if b.stok_saat_ini <= b.stok_minimum])
        sidebar_distribusi_jalan = Distribusi.query.filter_by(status='Berjalan').count()
    return dict(current_user_nama=nama,
                sidebar_menu_hari_ini=sidebar_menu_hari_ini,
                sidebar_stok_menipis=sidebar_stok_menipis,
                sidebar_distribusi_jalan=sidebar_distribusi_jalan)


# ---------------- ROUTES: AUTH ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['nama'] = user.nama
            return redirect(url_for('dashboard'))
        flash('Username atau password salah', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- ROUTES: DASHBOARD ----------------

@app.route('/')
@login_required
def dashboard():
    total_menu_hari_ini = Menu.query.filter_by(tanggal=date.today()).count()
    bahan_menipis = BahanBaku.query.all()
    bahan_menipis = [b for b in bahan_menipis if b.stok_saat_ini <= b.stok_minimum]
    total_sekolah = Sekolah.query.count()
    total_siswa = db.session.query(db.func.sum(Sekolah.jumlah_siswa)).scalar() or 0
    menu_belum_checklist = Menu.query.filter(~Menu.checklist.has()).count()

    # Data tren menu 7 hari terakhir (untuk grafik)
    tren_labels = []
    tren_data = []
    for i in range(6, -1, -1):
        tgl = date.today() - timedelta(days=i)
        jumlah = Menu.query.filter_by(tanggal=tgl).count()
        tren_labels.append(tgl.strftime('%d/%m'))
        tren_data.append(jumlah)

    # Distribusi status menu (untuk grafik donat)
    status_counts = {'Disiapkan': 0, 'Siap Distribusi': 0, 'Terdistribusi': 0}
    for m in Menu.query.all():
        status_counts[m.status] = status_counts.get(m.status, 0) + 1

    # ---- Data distribusi & cabang ----
    distribusi_hari_ini = Distribusi.query.filter_by(tanggal=date.today()).all()
    distribusi_berjalan = Distribusi.query.filter_by(status='Berjalan').all()
    porsi_terkirim = sum(d.jumlah_porsi for d in distribusi_hari_ini if d.status == 'Selesai')
    porsi_dijadwalkan = sum(d.jumlah_porsi for d in distribusi_hari_ini)
    persen_tersalur = round(porsi_terkirim / porsi_dijadwalkan * 100) if porsi_dijadwalkan else 0

    cabangs = Cabang.query.order_by(Cabang.nama).all()
    armada = Kendaraan.query.all()
    armada_counts = {
        'Tersedia': len([k for k in armada if k.status == 'Tersedia']),
        'Dalam Perjalanan': len([k for k in armada if k.status == 'Dalam Perjalanan']),
        'Perawatan': len([k for k in armada if k.status == 'Perawatan']),
    }

    # Porsi tersalur 7 hari terakhir (untuk grafik batang)
    porsi_labels, porsi_data = [], []
    for i in range(6, -1, -1):
        tgl = date.today() - timedelta(days=i)
        total = sum(d.jumlah_porsi for d in Distribusi.query.filter_by(tanggal=tgl, status='Selesai').all())
        porsi_labels.append(tgl.strftime('%d/%m'))
        porsi_data.append(total)

    return render_template('dashboard.html',
                            total_menu_hari_ini=total_menu_hari_ini,
                            bahan_menipis=bahan_menipis,
                            total_sekolah=total_sekolah,
                            total_siswa=total_siswa,
                            menu_belum_checklist=menu_belum_checklist,
                            tren_labels=tren_labels,
                            tren_data=tren_data,
                            status_counts=status_counts,
                            distribusi_berjalan=distribusi_berjalan,
                            distribusi_hari_ini=distribusi_hari_ini,
                            porsi_terkirim=porsi_terkirim,
                            porsi_dijadwalkan=porsi_dijadwalkan,
                            persen_tersalur=persen_tersalur,
                            cabangs=cabangs,
                            armada_counts=armada_counts,
                            porsi_labels=porsi_labels,
                            porsi_data=porsi_data,
                            total_pekerja_bertugas=Pekerja.query.filter_by(bertugas=True).count())


# ---------------- ROUTES: MENU + GIZI ----------------

@app.route('/menu')
@login_required
def menu_list():
    menus = Menu.query.order_by(Menu.tanggal.desc()).all()
    return render_template('menu_list.html', menus=menus)


@app.route('/menu/tambah', methods=['GET', 'POST'])
@login_required
def menu_tambah():
    sekolahs = Sekolah.query.all()
    if request.method == 'POST':
        nama_menu = request.form.get('nama_menu', '').strip()
        tanggal_str = request.form.get('tanggal')
        sekolah_id = request.form.get('sekolah_id') or None
        tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date() if tanggal_str else date.today()

        menu = Menu(nama_menu=nama_menu, tanggal=tanggal, sekolah_id=sekolah_id)
        db.session.add(menu)
        db.session.flush()  # dapatkan menu.id sebelum commit

        nama_bahan_list = request.form.getlist('nama_bahan[]')
        gram_list = request.form.getlist('gram_per_porsi[]')
        kalori_list = request.form.getlist('kalori[]')
        protein_list = request.form.getlist('protein[]')

        for i in range(len(nama_bahan_list)):
            if not nama_bahan_list[i].strip():
                continue
            item = MenuItem(
                menu_id=menu.id,
                nama_bahan=nama_bahan_list[i].strip(),
                gram_per_porsi=float(gram_list[i] or 0),
                kalori=float(kalori_list[i] or 0),
                protein=float(protein_list[i] or 0),
            )
            db.session.add(item)

        db.session.commit()
        flash(f'Menu "{nama_menu}" berhasil disimpan dengan {len(nama_bahan_list)} bahan.', 'success')
        return redirect(url_for('menu_list'))

    return render_template('menu_form.html', sekolahs=sekolahs)


@app.route('/menu/<int:menu_id>')
@login_required
def menu_detail(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    return render_template('menu_detail.html', menu=menu)


@app.route('/menu/<int:menu_id>/hapus', methods=['POST'])
@login_required
def menu_hapus(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    nama = menu.nama_menu
    db.session.delete(menu)  # cascade otomatis hapus MenuItem & ChecklistKeamanan terkait
    db.session.commit()
    flash(f'Menu "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('menu_list'))


# ---------------- ROUTES: STOK BAHAN BAKU ----------------

@app.route('/stok')
@login_required
def stok_list():
    bahans = BahanBaku.query.order_by(BahanBaku.nama).all()
    return render_template('stok_list.html', bahans=bahans)


@app.route('/stok/tambah', methods=['GET', 'POST'])
@login_required
def stok_tambah():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        satuan = request.form.get('satuan', 'kg')
        stok_awal = float(request.form.get('stok_awal') or 0)
        stok_minimum = float(request.form.get('stok_minimum') or 0)
        bahan = BahanBaku(nama=nama, satuan=satuan, stok_saat_ini=stok_awal, stok_minimum=stok_minimum)
        db.session.add(bahan)
        db.session.commit()
        flash(f'Bahan baku "{nama}" ditambahkan.', 'success')
        return redirect(url_for('stok_list'))
    return render_template('stok_form.html')


@app.route('/stok/<int:bahan_id>/transaksi', methods=['POST'])
@login_required
def stok_transaksi(bahan_id):
    bahan = BahanBaku.query.get_or_404(bahan_id)
    jenis = request.form.get('jenis')
    jumlah = float(request.form.get('jumlah') or 0)
    keterangan = request.form.get('keterangan', '')

    if jenis == 'masuk':
        bahan.stok_saat_ini += jumlah
    elif jenis == 'keluar':
        bahan.stok_saat_ini = max(0, bahan.stok_saat_ini - jumlah)

    trx = StokTransaksi(bahan_id=bahan.id, jenis=jenis, jumlah=jumlah, keterangan=keterangan)
    db.session.add(trx)
    db.session.commit()
    flash(f'Transaksi stok "{bahan.nama}" tercatat.', 'success')
    return redirect(url_for('stok_list'))


@app.route('/stok/<int:bahan_id>/hapus', methods=['POST'])
@login_required
def stok_hapus(bahan_id):
    bahan = BahanBaku.query.get_or_404(bahan_id)
    nama = bahan.nama
    db.session.delete(bahan)  # cascade otomatis hapus riwayat transaksi terkait
    db.session.commit()
    flash(f'Bahan baku "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('stok_list'))


# ---------------- ROUTES: CHECKLIST KEAMANAN PANGAN ----------------

@app.route('/checklist')
@login_required
def checklist_list():
    menus = Menu.query.order_by(Menu.tanggal.desc()).all()
    return render_template('checklist_list.html', menus=menus)


@app.route('/checklist/<int:menu_id>', methods=['GET', 'POST'])
@login_required
def checklist_form(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    checklist = menu.checklist or ChecklistKeamanan(menu_id=menu.id)

    if request.method == 'POST':
        checklist.suhu_ok = 'suhu_ok' in request.form
        checklist.sampel_disimpan = 'sampel_disimpan' in request.form
        checklist.waktu_saji_ok = 'waktu_saji_ok' in request.form
        checklist.kebersihan_ok = 'kebersihan_ok' in request.form
        checklist.petugas = request.form.get('petugas', '')
        checklist.dicatat_pada = datetime.utcnow()

        if checklist.id is None:
            db.session.add(checklist)

        if checklist.lolos:
            menu.status = 'Siap Distribusi'
        else:
            menu.status = 'Disiapkan'

        db.session.commit()
        flash('Checklist keamanan pangan tersimpan.', 'success')
        return redirect(url_for('checklist_list'))

    return render_template('checklist_form.html', menu=menu, checklist=checklist)


@app.route('/checklist/<int:menu_id>/distribusikan', methods=['POST'])
@login_required
def checklist_distribusikan(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    if menu.checklist and menu.checklist.lolos:
        menu.status = 'Terdistribusi'
        db.session.commit()
        flash(f'Menu "{menu.nama_menu}" ditandai terdistribusi.', 'success')
    else:
        flash('Checklist keamanan pangan belum lolos, tidak bisa didistribusikan.', 'error')
    return redirect(url_for('checklist_list'))


@app.route('/petugas')
@login_required
def petugas_list():
    checklists = ChecklistKeamanan.query.filter(
        ChecklistKeamanan.petugas.isnot(None), ChecklistKeamanan.petugas != ''
    ).order_by(ChecklistKeamanan.dicatat_pada.desc()).all()

    ringkasan = {}
    for c in checklists:
        ringkasan.setdefault(c.petugas, []).append(c)

    return render_template('petugas_list.html', ringkasan=ringkasan, checklists=checklists)


# ---------------- ROUTES: DISTRIBUSI ----------------

def _kode_distribusi():
    urut = Distribusi.query.count() + 1
    return f"DST-{date.today().strftime('%y%m%d')}-{urut:03d}"


@app.route('/distribusi')
@login_required
def distribusi_list():
    filter_status = request.args.get('status', 'semua')
    query = Distribusi.query
    if filter_status != 'semua':
        query = query.filter_by(status=filter_status)
    perjalanan = query.order_by(Distribusi.tanggal.desc(), Distribusi.id.desc()).all()

    semua = Distribusi.query.all()
    ringkasan = {
        'berjalan': len([d for d in semua if d.status == 'Berjalan']),
        'dijadwalkan': len([d for d in semua if d.status == 'Dijadwalkan']),
        'selesai_hari_ini': len([d for d in semua if d.status == 'Selesai' and d.tanggal == date.today()]),
        'porsi_terkirim': sum(d.jumlah_porsi for d in semua if d.status == 'Selesai' and d.tanggal == date.today()),
    }
    armada = Kendaraan.query.order_by(Kendaraan.plat).all()
    return render_template('distribusi_list.html',
                           perjalanan=perjalanan,
                           ringkasan=ringkasan,
                           armada=armada,
                           filter_status=filter_status)


@app.route('/distribusi/tambah', methods=['GET', 'POST'])
@login_required
def distribusi_tambah():
    if request.method == 'POST':
        kendaraan = Kendaraan.query.get(request.form.get('kendaraan_id'))
        jumlah_porsi = int(request.form.get('jumlah_porsi') or 0)

        if kendaraan and kendaraan.kapasitas_porsi and jumlah_porsi > kendaraan.kapasitas_porsi:
            flash(f'Porsi melebihi kapasitas {kendaraan.plat} ({kendaraan.kapasitas_porsi} porsi). Kurangi porsi atau pilih kendaraan lain.', 'error')
            return redirect(url_for('distribusi_tambah'))

        d = Distribusi(
            kode=_kode_distribusi(),
            tanggal=datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date() if request.form.get('tanggal') else date.today(),
            cabang_id=int(request.form['cabang_id']),
            kendaraan_id=int(request.form['kendaraan_id']),
            sopir_id=int(request.form['sopir_id']) if request.form.get('sopir_id') else None,
            sekolah_id=int(request.form['sekolah_id']),
            menu_id=int(request.form['menu_id']) if request.form.get('menu_id') else None,
            jumlah_porsi=jumlah_porsi,
            jarak_km=float(request.form.get('jarak_km') or 0),
            catatan=request.form.get('catatan', '').strip(),
        )
        db.session.add(d)
        db.session.commit()
        flash(f'Jadwal distribusi {d.kode} dibuat.', 'success')
        return redirect(url_for('distribusi_list'))

    return render_template('distribusi_form.html',
                           cabangs=Cabang.query.filter_by(aktif=True).all(),
                           armada=Kendaraan.query.filter(Kendaraan.status != 'Perawatan').all(),
                           sopirs=Pekerja.query.filter_by(peran='Sopir').all(),
                           sekolahs=Sekolah.query.all(),
                           menus=Menu.query.order_by(Menu.tanggal.desc()).limit(20).all(),
                           hari_ini=date.today().isoformat())


@app.route('/distribusi/<int:distribusi_id>')
@login_required
def distribusi_detail(distribusi_id):
    d = Distribusi.query.get_or_404(distribusi_id)
    riwayat = Distribusi.query.filter_by(kendaraan_id=d.kendaraan_id, status='Selesai') \
        .order_by(Distribusi.tiba_pada.desc()).limit(5).all()
    return render_template('distribusi_detail.html', d=d, riwayat=riwayat)


@app.route('/distribusi/<int:distribusi_id>/berangkat', methods=['POST'])
@login_required
def distribusi_berangkat(distribusi_id):
    d = Distribusi.query.get_or_404(distribusi_id)

    if d.menu and not (d.menu.checklist and d.menu.checklist.lolos):
        flash(f'{d.kode} belum bisa berangkat: menu "{d.menu.nama_menu}" belum lolos checklist keamanan pangan.', 'error')
        return redirect(request.referrer or url_for('distribusi_list'))

    if d.kendaraan.perjalanan_aktif:
        flash(f'{d.kendaraan.plat} masih dalam perjalanan lain. Selesaikan dulu perjalanan tersebut.', 'error')
        return redirect(request.referrer or url_for('distribusi_list'))

    d.status = 'Berjalan'
    d.berangkat_pada = datetime.utcnow()
    d.kendaraan.status = 'Dalam Perjalanan'
    db.session.commit()
    flash(f'{d.kode} berangkat menuju {d.sekolah.nama}.', 'success')
    return redirect(request.referrer or url_for('distribusi_list'))


@app.route('/distribusi/<int:distribusi_id>/tiba', methods=['POST'])
@login_required
def distribusi_tiba(distribusi_id):
    d = Distribusi.query.get_or_404(distribusi_id)
    d.status = 'Selesai'
    d.tiba_pada = datetime.utcnow()
    d.kendaraan.status = 'Tersedia'
    if d.menu:
        d.menu.status = 'Terdistribusi'
    db.session.commit()
    flash(f'{d.kode} tiba di {d.sekolah.nama}. {d.jumlah_porsi} porsi tersalurkan.', 'success')
    return redirect(request.referrer or url_for('distribusi_list'))


@app.route('/distribusi/<int:distribusi_id>/batal', methods=['POST'])
@login_required
def distribusi_batal(distribusi_id):
    d = Distribusi.query.get_or_404(distribusi_id)
    d.status = 'Batal'
    if d.kendaraan.status == 'Dalam Perjalanan':
        d.kendaraan.status = 'Tersedia'
    db.session.commit()
    flash(f'{d.kode} dibatalkan.', 'success')
    return redirect(request.referrer or url_for('distribusi_list'))


@app.route('/api/distribusi/live')
@login_required
def api_distribusi_live():
    """Dipakai panel live di dashboard & halaman distribusi untuk refresh tanpa reload."""
    aktif = Distribusi.query.filter_by(status='Berjalan').all()
    return {
        'jumlah': len(aktif),
        'perjalanan': [{
            'id': d.id,
            'kode': d.kode,
            'plat': d.kendaraan.plat,
            'model': d.kendaraan.model or d.kendaraan.jenis,
            'sopir': d.sopir.nama if d.sopir else 'Belum ditugaskan',
            'cabang': d.cabang.nama,
            'tujuan': d.sekolah.nama,
            'porsi': d.jumlah_porsi,
            'progres': d.progres,
            'sisa_menit': d.sisa_menit,
        } for d in aktif]
    }


# ---------------- ROUTES: CABANG & PEKERJA ----------------

@app.route('/cabang')
@login_required
def cabang_list():
    cabangs = Cabang.query.order_by(Cabang.nama).all()
    return render_template('cabang_list.html', cabangs=cabangs)


@app.route('/cabang/tambah', methods=['GET', 'POST'])
@login_required
def cabang_tambah():
    if request.method == 'POST':
        kode = request.form.get('kode', '').strip().upper()
        if Cabang.query.filter_by(kode=kode).first():
            flash(f'Kode cabang "{kode}" sudah dipakai. Gunakan kode lain.', 'error')
            return redirect(url_for('cabang_tambah'))
        c = Cabang(
            nama=request.form.get('nama', '').strip(),
            kode=kode,
            alamat=request.form.get('alamat', '').strip(),
            kapasitas_porsi=int(request.form.get('kapasitas_porsi') or 0),
            kepala=request.form.get('kepala', '').strip(),
            telepon=request.form.get('telepon', '').strip(),
        )
        db.session.add(c)
        db.session.commit()
        flash(f'Cabang "{c.nama}" ditambahkan.', 'success')
        return redirect(url_for('cabang_detail', cabang_id=c.id))
    return render_template('cabang_form.html')


@app.route('/cabang/<int:cabang_id>')
@login_required
def cabang_detail(cabang_id):
    c = Cabang.query.get_or_404(cabang_id)
    perjalanan = Distribusi.query.filter_by(cabang_id=c.id) \
        .order_by(Distribusi.tanggal.desc(), Distribusi.id.desc()).limit(10).all()
    return render_template('cabang_detail.html', c=c, perjalanan=perjalanan)


@app.route('/cabang/<int:cabang_id>/pekerja/tambah', methods=['POST'])
@login_required
def pekerja_tambah(cabang_id):
    c = Cabang.query.get_or_404(cabang_id)
    p = Pekerja(
        nama=request.form.get('nama', '').strip(),
        peran=request.form.get('peran', 'Juru Masak'),
        shift=request.form.get('shift', 'Pagi'),
        telepon=request.form.get('telepon', '').strip(),
        cabang_id=c.id,
    )
    db.session.add(p)
    db.session.commit()
    flash(f'{p.nama} ditambahkan ke {c.nama}.', 'success')
    return redirect(url_for('cabang_detail', cabang_id=c.id))


@app.route('/pekerja/<int:pekerja_id>/status', methods=['POST'])
@login_required
def pekerja_status(pekerja_id):
    p = Pekerja.query.get_or_404(pekerja_id)
    p.bertugas = not p.bertugas
    db.session.commit()
    flash(f'{p.nama} ditandai {"bertugas" if p.bertugas else "libur"}.', 'success')
    return redirect(url_for('cabang_detail', cabang_id=p.cabang_id))


@app.route('/cabang/<int:cabang_id>/kendaraan/tambah', methods=['POST'])
@login_required
def kendaraan_tambah(cabang_id):
    c = Cabang.query.get_or_404(cabang_id)
    plat = request.form.get('plat', '').strip().upper()
    if Kendaraan.query.filter_by(plat=plat).first():
        flash(f'Kendaraan dengan plat {plat} sudah terdaftar.', 'error')
        return redirect(url_for('cabang_detail', cabang_id=c.id))
    k = Kendaraan(
        plat=plat,
        jenis=request.form.get('jenis', 'Van'),
        model=request.form.get('model', '').strip(),
        kapasitas_porsi=int(request.form.get('kapasitas_porsi') or 0),
        cabang_id=c.id,
    )
    db.session.add(k)
    db.session.commit()
    flash(f'Kendaraan {k.plat} ditambahkan.', 'success')
    return redirect(url_for('cabang_detail', cabang_id=c.id))


@app.route('/kendaraan/<int:kendaraan_id>/perawatan', methods=['POST'])
@login_required
def kendaraan_perawatan(kendaraan_id):
    k = Kendaraan.query.get_or_404(kendaraan_id)
    if k.perjalanan_aktif:
        flash(f'{k.plat} sedang dalam perjalanan, tidak bisa diubah ke perawatan.', 'error')
    else:
        k.status = 'Tersedia' if k.status == 'Perawatan' else 'Perawatan'
        db.session.commit()
        flash(f'Status {k.plat} diubah menjadi {k.status}.', 'success')
    return redirect(url_for('cabang_detail', cabang_id=k.cabang_id))


# ---------------- ROUTES: SEKOLAH (pendukung) ----------------

@app.route('/sekolah')
@login_required
def sekolah_list():
    sekolahs = Sekolah.query.all()
    return render_template('sekolah_list.html', sekolahs=sekolahs)


@app.route('/sekolah/tambah', methods=['GET', 'POST'])
@login_required
def sekolah_tambah():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        jumlah_siswa = int(request.form.get('jumlah_siswa') or 0)
        db.session.add(Sekolah(nama=nama, jumlah_siswa=jumlah_siswa))
        db.session.commit()
        flash(f'Sekolah "{nama}" ditambahkan.', 'success')
        return redirect(url_for('sekolah_list'))
    return render_template('sekolah_form.html')


# ---------------- INIT DB ----------------

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin', nama='Admin SPPG')
        u.set_password('sppg2026')
        db.session.add(u)
        db.session.commit()

    # Auto-isi data contoh kalau database masih kosong (berguna di paket
    # hosting gratis yang tidak menyediakan akses Shell untuk jalankan seed.py manual)
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
            BahanBaku(nama="Ayam", satuan="kg", stok_saat_ini=25, stok_minimum=40),
            BahanBaku(nama="Telur", satuan="butir", stok_saat_ini=600, stok_minimum=300),
            BahanBaku(nama="Bayam", satuan="kg", stok_saat_ini=15, stok_minimum=20),
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

    if Cabang.query.count() == 0:
        cabangs = [
            Cabang(nama="SPPG Purwodadi Kota", kode="PWD-01", alamat="Jl. R. Suprapto No. 12, Purwodadi",
                   kapasitas_porsi=1200, kepala="Rahmat Hidayat", telepon="0812-3300-1101"),
            Cabang(nama="SPPG Grobogan Barat", kode="GBR-02", alamat="Jl. Diponegoro No. 45, Grobogan",
                   kapasitas_porsi=800, kepala="Nurul Aini", telepon="0812-3300-2202"),
            Cabang(nama="SPPG Toroh", kode="TRH-03", alamat="Jl. Raya Toroh KM 4, Toroh",
                   kapasitas_porsi=600, kepala="Bagas Prakoso", telepon="0812-3300-3303"),
        ]
        db.session.add_all(cabangs)
        db.session.commit()

        pekerja = [
            ("Rahmat Hidayat", "Kepala Dapur", "Pagi", 0), ("Siti Aminah", "QC Gizi", "Pagi", 0),
            ("Joko Susilo", "Sopir", "Pagi", 0), ("Dewi Lestari", "Juru Masak", "Pagi", 0),
            ("Agus Salim", "Juru Masak", "Siang", 0), ("Nurul Aini", "Kepala Dapur", "Pagi", 1),
            ("Bambang Wijaya", "Sopir", "Pagi", 1), ("Rina Marlina", "Juru Masak", "Pagi", 1),
            ("Hendra Gunawan", "QC Gizi", "Siang", 1), ("Bagas Prakoso", "Kepala Dapur", "Pagi", 2),
            ("Yusuf Maulana", "Sopir", "Pagi", 2), ("Ika Puspita", "Juru Masak", "Pagi", 2),
        ]
        for nama, peran, shift, idx in pekerja:
            db.session.add(Pekerja(nama=nama, peran=peran, shift=shift, cabang_id=cabangs[idx].id))

        armada = [
            ("B 9021 SPG", "Van", "Daihatsu Gran Max Box", 450, 0),
            ("B 9188 SPG", "Van", "Suzuki APV Blind Van", 380, 0),
            ("K 8834 GBR", "Van", "Daihatsu Gran Max Box", 450, 1),
            ("K 8901 GBR", "Pikap", "Mitsubishi L300", 500, 1),
            ("K 7712 TRH", "Van", "Isuzu Traga Box", 600, 2),
        ]
        for plat, jenis, model, kap, idx in armada:
            db.session.add(Kendaraan(plat=plat, jenis=jenis, model=model,
                                     kapasitas_porsi=kap, cabang_id=cabangs[idx].id))
        db.session.commit()

        sekolah_all = Sekolah.query.all()
        van_all = Kendaraan.query.all()
        sopir_all = Pekerja.query.filter_by(peran='Sopir').all()
        menu_hari_ini = Menu.query.filter_by(tanggal=date.today()).first()
        # Untuk jadwal yang belum berangkat, pakai menu yang checklist-nya sudah lolos
        # supaya tombol "Berangkat" bisa langsung dicoba tanpa terhalang guard keamanan.
        menu_siap = next((m for m in Menu.query.all() if m.checklist and m.checklist.lolos), menu_hari_ini)
        sekarang = datetime.utcnow()

        jadwal = [
            # (cabang, kendaraan, sopir, sekolah, porsi, jarak, status, menit_lalu_berangkat)
            (0, 0, 0, 0, 310, 4.2, 'Berjalan', 18),
            (1, 2, 1, 1, 245, 7.8, 'Berjalan', 32),
            (2, 4, 2, 2, 480, 11.5, 'Dijadwalkan', None),
            (0, 1, 0, 1, 245, 6.1, 'Selesai', 190),
            (1, 3, 1, 2, 300, 9.0, 'Selesai', 240),
        ]
        for i, (ci, ki, si, ski, porsi, jarak, status, menit) in enumerate(jadwal, start=1):
            d = Distribusi(
                kode=f"DST-{date.today().strftime('%y%m%d')}-{i:03d}",
                tanggal=date.today(),
                cabang_id=cabangs[ci].id,
                kendaraan_id=van_all[ki].id,
                sopir_id=sopir_all[si].id,
                sekolah_id=sekolah_all[ski % len(sekolah_all)].id,
                menu_id=(menu_siap.id if status == 'Dijadwalkan' and menu_siap
                         else (menu_hari_ini.id if menu_hari_ini else None)),
                jumlah_porsi=porsi,
                jarak_km=jarak,
                status=status,
            )
            if status == 'Berjalan':
                d.berangkat_pada = sekarang - timedelta(minutes=menit)
                van_all[ki].status = 'Dalam Perjalanan'
            elif status == 'Selesai':
                d.berangkat_pada = sekarang - timedelta(minutes=menit)
                d.tiba_pada = sekarang - timedelta(minutes=menit - 42)
            db.session.add(d)
        db.session.commit()


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
