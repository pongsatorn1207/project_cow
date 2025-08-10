from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, json, os

app = Flask(__name__)
app.secret_key = 'secret_key'

def get_data():
    conn = sqlite3.connect("cow_data.db")
    conn.row_factory = sqlite3.Row
    data = conn.execute("SELECT * FROM cow_data ORDER BY id DESC").fetchall()
    conn.close()
    return data

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if os.path.exists('users.json'):
            with open('users.json') as f:
                users = json.load(f)
        else:
            users = {}

        if username in users and users[username]['password'] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            return redirect(url_for('dashboard'))
        return "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    data = get_data()
    if session['role'] == 'admin':
        with open("users.json") as f:
            users = json.load(f)
        return render_template('dashboard_admin.html', data=data, users=users, username=session['user'])
    return render_template('dashboard_user.html', data=data, username=session['user'])

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if session.get('role') != 'admin':
        return "คุณไม่มีสิทธิ์"
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if os.path.exists('users.json'):
            with open('users.json') as f:
                users = json.load(f)
        else:
            users = {}

        if username in users:
            return "ผู้ใช้นี้มีอยู่แล้ว"
        users[username] = {'password': password, 'role': role}
        with open('users.json', 'w') as f:
            json.dump(users, f, indent=4)
        return redirect(url_for('dashboard'))

    return render_template('add_user.html')

@app.route('/edit_user/<username>', methods=['GET', 'POST'])
def edit_user(username):
    if session.get('role') != 'admin':
        return "คุณไม่มีสิทธิ์"
    with open("users.json") as f:
        users = json.load(f)

    if username not in users:
        return "ไม่พบผู้ใช้"

    if request.method == 'POST':
        users[username]['password'] = request.form['password']
        users[username]['role'] = request.form['role']
        with open('users.json', 'w') as f:
            json.dump(users, f, indent=4)
        return redirect(url_for('dashboard'))

    return render_template('edit_user.html', username=username, role=users[username]['role'])

@app.route('/delete_user/<username>', methods=['GET'])
def delete_user(username):
    if session.get('role') != 'admin':
        return "คุณไม่มีสิทธิ์"
    with open("users.json") as f:
        users = json.load(f)
    if username in users:
        if username == session['user']:
            return "ลบตัวเองไม่ได้"
        del users[username]
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)
    return redirect(url_for('dashboard'))

@app.route('/upload', methods=['POST'])
def upload():
    from werkzeug.utils import secure_filename
    image = request.files.get('image')
    temperature = request.form.get('temperature')

    if not image or not temperature:
        return "Missing image or temperature", 400

    filename = secure_filename(image.filename)
    save_path = os.path.join('static/images', filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    image.save(save_path)

    conn = sqlite3.connect("cow_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO cow_data (temperature, timestamp, image_path) VALUES (?, datetime('now', 'localtime'), ?)",
              (temperature, save_path))
    conn.commit()
    conn.close()

    return "บันทึกสำเร็จ", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
