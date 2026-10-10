import os
import sqlite3
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "afterparty_secret_key_change_me"

DB_FILE = "afterparty_database.db"
HOST_EMAIL = "kushagramishra.pcvn@gmail.com"
ADMIN_PASSWORD = "afterpartyadmin"  # Password to access /admin

# Optional: configure Gmail 16-character App Password to enable email alerts
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = HOST_EMAIL
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")

# --- SQL DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Pending',
            registered_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- EMAIL HELPERS ---
def send_email(to_email, subject, html_content):
    if not SENDER_PASSWORD:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

# --- ROUTES ---

@app.route("/")
def guest_portal():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Afterparty Access</title>
      <style>
        body { background: #070d1e; color: #fff; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .card { width: 100%; max-width: 460px; background: rgba(13, 23, 46, 0.9); border: 1px solid rgba(99, 137, 214, 0.3); border-radius: 20px; padding: 40px 32px; box-shadow: 0 20px 50px rgba(0,0,0,0.8); }
        h1 { font-size: 26px; text-align: center; margin-bottom: 6px; }
        .sub { text-align: center; color: #94a3b8; font-size: 13.5px; margin-bottom: 24px; }
        .alert-box { background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 10px; font-size: 12px; color: #cbd5e1; margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 600; color: #f1f5f9; margin-bottom: 6px; }
        input { width: 100%; box-sizing: border-box; background: #091124; border: 1px solid #1e293b; border-radius: 10px; padding: 12px 14px; color: #fff; margin-bottom: 16px; outline: none; }
        input:focus { border-color: #3b82f6; }
        button { width: 100%; background: linear-gradient(135deg, #1e40af, #3b82f6); border: none; border-radius: 12px; color: #fff; padding: 14px; font-weight: 700; font-size: 15px; cursor: pointer; }
        .err { color: #ef4444; font-size: 13px; margin-bottom: 14px; display: none; }
        .success { text-align: center; display: none; }
      </style>
    </head>
    <body>
      <div class="card">
        <div id="formSection">
          <h1>Afterparty Access</h1>
          <p class="sub">Exclusive guestlist. Strictly 1 registration allowed per person.</p>
          <div class="alert-box">🔒 <b>Notice:</b> Duplicate submissions with the same phone or Gmail are blocked.</div>
          <div id="errMsg" class="err"></div>
          <form id="regForm">
            <label>Name (As on Official ID)</label>
            <input type="text" id="name" placeholder="e.g. Kushagra Mishra" required>
            <label>Mobile Number</label>
            <input type="tel" id="phone" placeholder="e.g. 9876543210" required>
            <label>Gmail ID</label>
            <input type="email" id="email" placeholder="e.g. yourname@gmail.com" required>
            <button type="submit" id="btn">Submit Request</button>
          </form>
        </div>
        <div id="successSection" class="success">
          <h2>Request Logged</h2>
          <p style="color:#94a3b8; font-size:13.5px;">Your details are recorded in the database. The host has been notified for approval.</p>
        </div>
      </div>
      <script>
        document.getElementById('regForm').addEventListener('submit', async (e) => {
          e.preventDefault();
          const errDiv = document.getElementById('errMsg');
          errDiv.style.display = 'none';
          const btn = document.getElementById('btn');
          btn.disabled = true;
          btn.textContent = 'Verifying...';

          const res = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              name: document.getElementById('name').value.trim(),
              phone: document.getElementById('phone').value.trim(),
              email: document.getElementById('email').value.trim()
            })
          });
          const data = await res.json();
          if (data.success) {
            document.getElementById('formSection').style.display = 'none';
            document.getElementById('successSection').style.display = 'block';
          } else {
            errDiv.textContent = data.message;
            errDiv.style.display = 'block';
            btn.disabled = false;
            btn.textContent = 'Submit Request';
          }
        });
      </script>
    </body>
    </html>
    """)

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    phone = re.sub(r"\D", "", str(data.get("phone", "")))
    email = str(data.get("email", "")).strip().lower()

    if len(name) < 2 or len(phone) < 10 or not email.endswith("@gmail.com"):
        return jsonify({"success": False, "message": "Please provide valid ID Name, 10-digit Phone, and @gmail.com ID."}), 400

    conn = get_db()
    cursor = conn.cursor()

    # SQL duplicate check
    cursor.execute("SELECT id FROM guests WHERE phone = ? OR email = ?", (phone, email))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "🚫 You have already submitted a request. Multiple submissions are not allowed."}), 409

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO guests (name, phone, email, status, registered_at) VALUES (?, ?, ?, 'Pending', ?)",
                   (name, phone, email, now))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM guests")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Approved'")
    approved = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Pending'")
    pending = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Rejected'")
    rejected = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM guests ORDER BY id DESC")
    guests = cursor.fetchall()
    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Host Approval Portal</title>
      <style>
        body { background:#070d1e; color:#fff; font-family:-apple-system, sans-serif; margin:0; padding:24px; }
        .kpi-row { display:flex; gap:16px; margin-bottom:24px; }
        .kpi { flex:1; background:#0d172e; border:1px solid rgba(99,137,214,0.25); border-radius:12px; padding:18px; }
        .kpi-num { font-size:28px; font-weight:800; margin-top:6px; }
        table { width:100%; border-collapse:collapse; background:#0d172e; border-radius:12px; overflow:hidden; }
        th, td { padding:14px 18px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.06); font-size:13.5px; }
        th { background:#0a1226; color:#94a3b8; font-size:12px; text-transform:uppercase; }
        .badge { padding:3px 10px; border-radius:100px; font-size:11px; font-weight:700; }
        .Pending { background:rgba(245,158,11,0.2); color:#fbbf24; }
        .Approved { background:rgba(16,185,129,0.2); color:#34d399; }
        .Rejected { background:rgba(239,68,68,0.2); color:#f87171; }
        .btn { padding:6px 12px; border-radius:6px; font-size:12px; font-weight:700; text-decoration:none; margin-right:6px; }
        .btn-app { background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.4); }
        .btn-rej { background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); }
      </style>
    </head>
    <body>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h2>🔒 Host Operations Dashboard</h2>
        <a href="/admin/logout" style="color:#94a3b8; font-size:13px;">Log Out</a>
      </div>
      <div class="kpi-row">
        <div class="kpi" style="border-left:4px solid #3b82f6;"><div>TOTAL REGISTERED</div><div class="kpi-num">{{ total }}</div></div>
        <div class="kpi" style="border-left:4px solid #10b981;"><div>APPROVED</div><div class="kpi-num">{{ approved }}</div></div>
        <div class="kpi" style="border-left:4px solid #f59e0b;"><div>PENDING REVIEW</div><div class="kpi-num">{{ pending }}</div></div>
        <div class="kpi" style="border-left:4px solid #ef4444;"><div>REJECTED</div><div class="kpi-num">{{ rejected }}</div></div>
      </div>
      <table>
        <tr><th>ID</th><th>Name (As on ID)</th><th>Mobile</th><th>Gmail</th><th>Time</th><th>Status</th><th>Actions</th></tr>
        {% for g in guests %}
        <tr>
          <td>#{{ g.id }}</td>
          <td><b>{{ g.name }}</b></td>
          <td>{{ g.phone }}</td>
          <td>{{ g.email }}</td>
          <td style="color:#94a3b8; font-size:12px;">{{ g.registered_at }}</td>
          <td><span class="badge {{ g.status }}">{{ g.status }}</span></td>
          <td>
            {% if g.status != 'Approved' %}<a href="/admin/set/{{ g.id }}/Approved" class="btn btn-app">Approve</a>{% endif %}
            {% if g.status != 'Rejected' %}<a href="/admin/set/{{ g.id }}/Rejected" class="btn btn-rej">Reject</a>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
    </body>
    </html>
    """, total=total, approved=approved, pending=pending, rejected=rejected, guests=guests)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST" and request.form.get("password") == ADMIN_PASSWORD:
        session["is_admin"] = True
        return redirect(url_for("admin"))
    return """
    <body style="background:#070d1e; color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; font-family:sans-serif;">
      <form method="POST" style="background:#0d172e; padding:32px; border-radius:12px; border:1px solid #1e293b; text-align:center;">
        <h3>Host Login</h3>
        <input type="password" name="password" placeholder="Password" style="display:block; margin:16px 0; padding:10px; width:220px; background:#091124; border:1px solid #1e293b; color:#fff; border-radius:8px;">
        <button type="submit" style="background:#2563eb; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer;">Enter</button>
      </form>
    </body>
    """

@app.route("/admin/set/<int:gid>/<status>")
def set_status(gid, status):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    conn.execute("UPDATE guests SET status = ? WHERE id = ?", (status, gid))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
