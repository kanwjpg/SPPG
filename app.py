import os
from datetime import datetime, date
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

    bahan = db.relationship('BahanBaku', backref='transaksi')


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
    return dict(current_user_nama=nama)


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
    return render_template('dashboard.html',
                            total_menu_hari_ini=total_menu_hari_ini,
                            bahan_menipis=bahan_menipis,
                            total_sekolah=total_sekolah,
                            total_siswa=total_siswa,
                            menu_belum_checklist=menu_belum_checklist)


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


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
