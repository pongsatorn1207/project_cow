from flask import Flask, render_template, request, redirect, url_for, session, send_file, Response, jsonify
import sqlite3, json, os, io
from datetime import datetime
import pandas as pd
import xlsxwriter

app = Flask(__name__)
app.secret_key = 'secret_key'

DB = "cow_data.db"
USERS_FILE = "users.json"
PI_STREAM_BASE = os.getenv("PI_STREAM_BASE", "http://192.168.1.130:5001")

# -------------------- DB helpers -------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_data(date=None, temp_min=None, start_time=None, end_time=None):
    conn = get_db()
    q = "SELECT * FROM cow_data WHERE 1=1"
    params = []
    if date:
        q += " AND DATE(timestamp)=?"
        params.append(date)
    if temp_min:
        q += " AND temperature>=?"
        params.append(temp_min)
    if start_time:
        q += " AND time(timestamp)>=?"
        params.append(start_time)
    if end_time:
        q += " AND time(timestamp)<=?"
        params.append(end_time)
    q += " ORDER BY id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# -------------------- Routes: auth ------------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        users = load_users()
        if u in users and users[u]['password'] == p:
            session['user'] = u
            session['role'] = users[u]['role']
            return redirect(url_for('dashboard'))
        return "ชื่อผู้ใช้หรือรหัสผานไม่ถูกต้อง"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- Routes: dashboard -------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    date = request.args.get('date') or None
    temp_min = request.args.get('temp_min') or None
    start_time = request.args.get('start_time') or None
    end_time = request.args.get('end_time') or None
    data = get_data(date, temp_min, start_time, end_time)
    return render_template(
        'dashboard.html',
        data=data,
        active_page='dashboard',
        role=session.get('role'),
        username=session.get('user'),
        date_val=(date or ""),
        temp_min_val=(temp_min or ""),
        start_time_val=(start_time or ""),
        end_time_val=(end_time or "")
    )

# -------------------- Download Excel ----------------------
@app.route('/download_xlsx')
def download_xlsx():
    if 'user' not in session:
        return redirect(url_for('login'))

    date = request.args.get('date') or None
    temp_min = request.args.get('temp_min') or None
    start_time = request.args.get('start_time') or None
    end_time = request.args.get('end_time') or None
    rows = get_data(date, temp_min, start_time, end_time)
    if not rows:
        return "ไม่พบข้อมูลตามเงื่อนไขม", 404

    out = io.BytesIO()
    wb = xlsxwriter.Workbook(out, {'in_memory': True})
    ws = wb.add_worksheet("cow_data")

    headers = ["เวลา", "อุณหภูมิ (°C)", "รูปภาพ"]
    for c, h in enumerate(headers):
        ws.write(0, c, h)

    ws.set_column(0, 0, 22)
    ws.set_column(1, 1, 13)
    ws.set_column(2, 2, 20)

    r_excel = 1
    for r in rows:
        ws.write(r_excel, 0, r['timestamp'])
        try:
            ws.write_number(r_excel, 1, float(r['temperature']))
        except:
            ws.write(r_excel, 1, r['temperature'])

        img_path = r['image_path']
        if img_path and os.path.exists(img_path):
            ws.set_row(r_excel, 80)
            ws.insert_image(r_excel, 2, img_path, {'x_scale': 0.4, 'y_scale': 0.4})

        r_excel += 1

    wb.close()
    out.seek(0)

    filename = f"cow_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        out,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# -------------------- Users -------------------------------
@app.route('/users')
def users_page():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('users.html', users=load_users(), active_page='users')

@app.route('/add_user', methods=['GET','POST'])
def add_user():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        r = request.form['role']
        users = load_users()
        if u in users:
            return "ผู้ใช้นี้มีอยู่แล้ว"
        users[u] = {'password': p, 'role': r}
        save_users(users)
        return redirect(url_for('users_page'))
    return render_template('add_user.html', active_page='users')

@app.route('/edit_user/<username>', methods=['GET','POST'])
def edit_user(username):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    users = load_users()
    if username not in users:
        return "ไม่พบผู้ใช้"
    if request.method == 'POST':
        users[username]['password'] = request.form['password']
        users[username]['role'] = request.form['role']
        save_users(users)
        return redirect(url_for('users_page'))
    return render_template('edit_user.html', username=username, user=users[username], active_page='users')

@app.route('/delete_user/<username>')
def delete_user(username):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if username == session.get('user'):
        return "ลบตัวเองไม่ได้"
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
    return redirect(url_for('users_page'))

# -------------------- Upload API --------------------------
@app.route('/upload', methods=['POST'])
def upload():
    from werkzeug.utils import secure_filename
    image = request.files.get('image')
    temperature = request.form.get('temperature')
    if not image or not temperature:
        return "Missing image or temperature", 400

    fname = secure_filename(image.filename or f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    save_path = os.path.join('static', 'images', fname)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    image.save(save_path)

    conn = get_db()
    conn.execute(
        "INSERT INTO cow_data (temperature, timestamp, image_path) VALUES (?, datetime('now','localtime'), ?)",
        (temperature, save_path)
    )
    conn.commit()
    conn.close()
    return "บันทึกสำเร็จ", 200

# -------------------- Delete Image ------------------------
@app.route('/delete_image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    if 'user' not in session:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    conn = get_db()
    row = conn.execute("SELECT image_path FROM cow_data WHERE id=?", (image_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'error': 'not_found'}), 404

    img_path = row['image_path']
    try:
        if img_path and os.path.exists(img_path):
            os.remove(img_path)
    except Exception:
        pass

    conn.execute("DELETE FROM cow_data WHERE id=?", (image_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# -------------------- Realtime ----------------------------
@app.route('/realtime')
def realtime_camera():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('realtime.html', active_page='realtime', pi_stream_base=PI_STREAM_BASE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
