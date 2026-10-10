import os
import sqlite3
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

# ==============================================================================
# 1. APP & CONFIGURATION
# ==============================================================================
app = Flask(__name__)
# Secret key for admin session management
app.secret_key = os.environ.get("SECRET_KEY", "afterparty_luxury_secret_key_999")

DB_FILE = os.environ.get("DB_PATH", "afterparty_database.db")
HOST_EMAIL = os.environ.get("HOST_EMAIL", "kushagramishra.pcvn@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "afterpartyadmin")

# Optional SMTP Settings for Email Alerts (Set SENDER_PASSWORD in Railway Variables)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = HOST_EMAIL
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")

# ==============================================================================
# 2. SQL DATABASE INITIALIZATION (SQLite - Zero Spreadsheets)
# ==============================================================================
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

# ==============================================================================
# 3. EMAIL DISPATCH HELPERS (Optional)
# ==============================================================================
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
        print(f"Email error: {e}")
        return False

def notify_host_new_guest(name, phone, email):
    subject = f"🎉 New Registration Pending Approval: {name}"
    html = f"""
    <h3>New Afterparty Registration Request</h3>
    <p>A new guest has submitted their details:</p>
    <ul>
        <li><b>Name (As per ID):</b> {name}</li>
        <li><b>Mobile Number:</b> {phone}</li>
        <li><b>Gmail ID:</b> {email}</li>
        <li><b>Status:</b> Pending Approval</li>
    </ul>
    <p>Log in to your host backend (<code>/admin</code>) to review and approve.</p>
    """
    send_email(HOST_EMAIL, subject, html)

def notify_guest_approved(name, guest_email):
    subject = "🎉 You're on the Afterparty Guestlist!"
    html = f"""
    <h2>Access Approved!</h2>
    <p>Hi <b>{name}</b>,</p>
    <p>Your registration for the afterparty has been officially <b>Approved</b> by the host.</p>
    <p><b>Door Verification Policy:</b></p>
    <ul>
        <li>Entry is strictly verified against your official ID matching: <b>{name}</b></li>
        <li>Registered Gmail: <b>{guest_email}</b></li>
    </ul>
    <p>See you at the event!</p>
    """
    send_email(guest_email, subject, html)

# ==============================================================================
# 4. LUXURY DARK BLUE & CRISP WHITE UI TEMPLATES
# ==============================================================================

GUEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Afterparty Guest Registration</title>
  <style>
    :root {
      --bg: #070d1e;
      --card-bg: rgba(13, 23, 46, 0.92);
      --card-border: rgba(99, 137, 214, 0.3);
      --royal-gradient: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%);
      --white: #ffffff;
      --white-sub: #f1f5f9;
      --muted: #94a3b8;
      --input-bg: #091124;
      --input-border: #1e293b;
      --danger: #ef4444;
      --success: #10b981;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: var(--bg);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(30, 64, 175, 0.35) 0%, transparent 60%),
        radial-gradient(circle at 85% 85%, rgba(59, 130, 246, 0.12) 0%, transparent 50%);
      color: var(--white);
      font-family: var(--font);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px 16px;
    }
    .card {
      width: 100%;
      max-width: 480px;
      background: var(--card-bg);
      backdrop-filter: blur(20px);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 44px 34px;
      box-shadow: 0 25px 60px rgba(2, 6, 23, 0.8), 0 0 35px rgba(30, 64, 175, 0.2);
    }
    .badge-bar { text-align: center; margin-bottom: 14px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 14px;
      background: rgba(30, 58, 138, 0.4);
      border: 1px solid rgba(96, 165, 250, 0.3);
      border-radius: 100px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #bfdbfe;
    }
    .badge-dot { width: 6px; height: 6px; background: #60a5fa; border-radius: 50%; box-shadow: 0 0 8px #60a5fa; }
    h1 { font-size: 26px; font-weight: 800; text-align: center; color: var(--white); margin-bottom: 8px; }
    .subtitle { text-align: center; color: var(--muted); font-size: 13.5px; line-height: 1.5; margin-bottom: 24px; }
    .policy-box {
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid rgba(59, 130, 246, 0.25);
      border-radius: 10px;
      padding: 10px 14px;
      margin-bottom: 22px;
      font-size: 12px;
      color: #cbd5e1;
    }
    .form-group { margin-bottom: 18px; }
    label { display: block; font-size: 13px; font-weight: 600; color: var(--white-sub); margin-bottom: 7px; }
    .label-hint { font-weight: 400; color: var(--muted); font-size: 11.5px; }
    input {
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 11px;
      padding: 13px 16px;
      color: var(--white);
      font-size: 14.5px;
      outline: none;
      transition: all 0.2s;
    }
    input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }
    .btn-submit {
      width: 100%;
      padding: 15px;
      background: var(--royal-gradient);
      border: none;
      border-radius: 12px;
      color: var(--white);
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.03em;
      cursor: pointer;
      margin-top: 10px;
      transition: all 0.2s;
      box-shadow: 0 10px 25px rgba(29, 78, 216, 0.4);
    }
    .btn-submit:hover { filter: brightness(1.1); transform: translateY(-1px); }
    .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
    .alert { padding: 12px 14px; border-radius: 10px; font-size: 13px; margin-bottom: 18px; display: none; line-height: 1.5; }
    .alert-error { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #fca5a5; }
    .result-card {
      background: rgba(9, 17, 36, 0.7);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 16px;
      margin: 18px 0;
      text-align: left;
      font-size: 13px;
    }
    .result-row { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .result-row:last-child { border-bottom: none; }
    .tag-pending { background: rgba(245, 158, 11, 0.2); color: #fbbf24; padding: 2px 8px; border-radius: 100px; font-size: 11px; font-weight: 700; }
  </style>
</head>
<body>
  <div class="card">
    <div id="formSection">
      <div class="badge-bar">
        <span class="badge"><span class="badge-dot"></span>Official Guestlist</span>
      </div>
      <h1>Afterparty Access</h1>
      <p class="subtitle">Complete your details below. Registrations are individually reviewed and approved by the host.</p>
      
      <div class="policy-box">
        <span>🔒 <b>Single Request Policy:</b> Duplicate entries using the same Mobile Number or Gmail ID are strictly blocked.</span>
      </div>

      <div id="alertBox" class="alert"></div>

      <form id="regForm">
        <div class="form-group">
          <label>Name <span class="label-hint">(As on your Official ID)</span></label>
          <input type="text" id="name" placeholder="e.g. Kushagra Mishra" required>
        </div>
        <div class="form-group">
          <label>Mobile Number <span class="label-hint">(1 request per number)</span></label>
          <input type="tel" id="phone" placeholder="e.g. 9876543210" required>
        </div>
        <div class="form-group">
          <label>Gmail ID <span class="label-hint">(Confirmation sent here)</span></label>
          <input type="email" id="email" placeholder="e.g. name@gmail.com" required>
        </div>
        <button type="submit" class="btn-submit" id="submitBtn">Register for Afterparty</button>
      </form>
    </div>

    <div id="successSection" style="display:none; text-align:center;">
      <h2 style="font-size:22px; margin-bottom:8px; color:#fff;">Request Submitted</h2>
      <p style="color:#94a3b8; font-size:13.5px; margin-bottom:20px;">Your details have been logged in the database and routed to the host for approval.</p>
      
      <div class="result-card">
        <div class="result-row"><span style="color:#94a3b8;">Status</span><span class="tag-pending">Pending Approval</span></div>
        <div class="result-row"><span style="color:#94a3b8;">Name (ID)</span><span style="font-weight:700;" id="resName">-</span></div>
        <div class="result-row"><span style="color:#94a3b8;">Mobile</span><span style="font-weight:700;" id="resPhone">-</span></div>
        <div class="result-row"><span style="color:#94a3b8;">Gmail ID</span><span style="font-weight:700;" id="resEmail">-</span></div>
      </div>
      <p style="color:#64748b; font-size:12px;">You cannot submit again. When approved, an entry pass will be emailed to your Gmail.</p>
    </div>
  </div>

  <script>
    const form = document.getElementById('regForm');
    const alertBox = document.getElementById('alertBox');
    const submitBtn = document.getElementById('submitBtn');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      alertBox.style.display = 'none';

      const name = document.getElementById('name').value.trim();
      const phone = document.getElementById('phone').value.trim();
      const email = document.getElementById('email').value.trim();

      submitBtn.disabled = true;
      submitBtn.textContent = 'Verifying Record...';

      try {
        const res = await fetch('/api/register', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name, phone, email })
        });
        const data = await res.json();

        if (data.success) {
          document.getElementById('formSection').style.display = 'none';
          document.getElementById('resName').textContent = name;
          document.getElementById('resPhone').textContent = phone;
          document.getElementById('resEmail').textContent = email;
          document.getElementById('successSection').style.display = 'block';
        } else {
          alertBox.className = 'alert alert-error';
          alertBox.textContent = data.message || 'Error submitting registration.';
          alertBox.style.display = 'block';
        }
      } catch (err) {
        alertBox.className = 'alert alert-error';
        alertBox.textContent = 'Network error. Please try again.';
        alertBox.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Register for Afterparty';
      }
    });
  </script>
</body>
</html>
"""

ADMIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Host Approval Backend</title>
  <style>
    :root {
      --bg: #070d1e;
      --panel: #0d172e;
      --border: rgba(99, 137, 214, 0.22);
      --white: #ffffff;
      --muted: #94a3b8;
      --royal: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--white); font-family: var(--font); min-height: 100vh; }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 18px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand h1 { font-size: 18px; font-weight: 700; color: #fff; }
    .brand p { font-size: 12px; color: var(--muted); }
    main { padding: 32px; max-width: 1200px; margin: 0 auto; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
    .kpi-card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 22px; }
    .kpi-card.total { border-left: 4px solid #3b82f6; }
    .kpi-card.approved { border-left: 4px solid var(--success); }
    .kpi-card.pending { border-left: 4px solid var(--warning); }
    .kpi-card.rejected { border-left: 4px solid var(--danger); }
    .kpi-title { font-size: 12px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; font-weight: 700; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #fff; margin-top: 6px; }
    .controls { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
    .filter-btn { background: var(--panel); border: 1px solid var(--border); color: var(--muted); padding: 8px 16px; border-radius: 8px; cursor: pointer; text-decoration: none; font-size: 13px; font-weight: 600; }
    .filter-btn.active { background: #1d4ed8; color: #fff; border-color: #3b82f6; }
    table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
    th { background: rgba(15,23,42,0.95); padding: 14px 18px; font-size: 12px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); text-align: left; }
    td { padding: 16px 18px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13.5px; }
    tr:hover td { background: rgba(59, 130, 246, 0.03); }
    .badge-status { padding: 3px 10px; border-radius: 100px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge-status.Pending { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    .badge-status.Approved { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .badge-status.Rejected { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    .btn-act { padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; text-decoration: none; display: inline-block; margin-right: 6px; }
    .btn-app { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .btn-app:hover { background: var(--success); color: #fff; }
    .btn-rej { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .btn-rej:hover { background: var(--danger); color: #fff; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>🔒 Host Operations Backend</h1>
      <p>Direct Database Review & Approvals (Zero Spreadsheets)</p>
    </div>
    <div>
      <a href="/admin/logout" class="filter-btn">Log Out</a>
    </div>
  </header>

  <main>
    <div class="kpi-grid">
      <div class="kpi-card total">
        <div class="kpi-title">Total Registered</div>
        <div class="kpi-val">{{ counts.total }}</div>
      </div>
      <div class="kpi-card approved">
        <div class="kpi-title">Approved Guests</div>
        <div class="kpi-val">{{ counts.approved }}</div>
      </div>
      <div class="kpi-card pending">
        <div class="kpi-title">Pending Review</div>
        <div class="kpi-val">{{ counts.pending }}</div>
      </div>
      <div class="kpi-card rejected">
        <div class="kpi-title">Rejected</div>
        <div class="kpi-val">{{ counts.rejected }}</div>
      </div>
    </div>

    <div class="controls">
      <div>
        <a href="/admin?status=All" class="filter-btn {% if current_status == 'All' %}active{% endif %}">All ({{ counts.total }})</a>
        <a href="/admin?status=Pending" class="filter-btn {% if current_status == 'Pending' %}active{% endif %}">Pending ({{ counts.pending }})</a>
        <a href="/admin?status=Approved" class="filter-btn {% if current_status == 'Approved' %}active{% endif %}">Approved ({{ counts.approved }})</a>
        <a href="/admin?status=Rejected" class="filter-btn {% if current_status == 'Rejected' %}active{% endif %}">Rejected ({{ counts.rejected }})</a>
      </div>
      <div>
        <a href="/admin/export/json" class="filter-btn" download>Export Database JSON</a>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Name (As on ID)</th>
          <th>Mobile Number</th>
          <th>Gmail ID</th>
          <th>Registered At</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {% for guest in guests %}
        <tr>
          <td style="color:#64748b; font-weight:700;">#{{ guest.id }}</td>
          <td style="font-weight:700; color:#fff;">{{ guest.name }}</td>
          <td>{{ guest.phone }}</td>
          <td>{{ guest.email }}</td>
          <td style="color:#94a3b8; font-size:12px;">{{ guest.registered_at }}</td>
          <td><span class="badge-status {{ guest.status }}">{{ guest.status }}</span></td>
          <td>
            {% if guest.status != 'Approved' %}
              <a href="/admin/action/{{ guest.id }}/Approved" class="btn-act btn-app">Approve</a>
            {% endif %}
            {% if guest.status != 'Rejected' %}
              <a href="/admin/action/{{ guest.id }}/Rejected" class="btn-act btn-rej">Reject</a>
            {% endif %}
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="7" style="text-align:center; padding:40px; color:#94a3b8;">No records found.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </main>
</body>
</html>
"""

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Host Login</title>
  <style>
    body { background:#070d1e; color:#fff; font-family:-apple-system, sans-serif; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
    .box { background:#0d172e; border:1px solid rgba(99,137,214,0.3); border-radius:16px; padding:40px 32px; width:100%; max-width:380px; text-align:center; }
    input { width:100%; box-sizing:border-box; background:#091124; border:1px solid #1e293b; border-radius:10px; padding:12px 14px; color:#fff; margin:16px 0; outline:none; }
    button { width:100%; background:linear-gradient(135deg, #1d4ed8, #3b82f6); border:none; padding:12px; border-radius:10px; color:#fff; font-weight:700; cursor:pointer; }
    .err { color:#ef4444; font-size:13px; margin-bottom:12px; }
  </style>
</head>
<body>
  <div class="box">
    <h2>Host Login</h2>
    <p style="color:#94a3b8; font-size:13px; margin-top:6px;">Enter your admin password to access approvals.</p>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST" action="/admin/login">
      <input type="password" name="password" placeholder="Admin Password" required autofocus>
      <button type="submit">Access Dashboard</button>
    </form>
  </div>
</body>
</html>
"""

# ==============================================================================
# 5. ROUTES
# ==============================================================================

# Health check endpoint for Railway
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

# Public Guest Form
@app.route("/")
def index():
    return render_template_string(GUEST_PAGE_HTML)

# Registration API
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    phone = re.sub(r"\D", "", str(data.get("phone", "")))
    email = str(data.get("email", "")).strip().lower()

    if len(name) < 2:
        return jsonify({"success": False, "message": "Please enter your full name as shown on your ID."}), 400
    if len(phone) < 10 or len(phone) > 15:
        return jsonify({"success": False, "message": "Please enter a valid 10-15 digit mobile number."}), 400
    if not email.endswith("@gmail.com") or len(email) < 11:
        return jsonify({"success": False, "message": "Please provide a valid Gmail address (@gmail.com)."}), 400

    conn = get_db()
    cursor = conn.cursor()

    # SQL duplicate check
    cursor.execute("SELECT id FROM guests WHERE phone = ? OR email = ?", (phone, email))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return jsonify({
            "success": False,
            "error": "duplicate",
            "message": "🚫 A request with this Mobile Number or Gmail ID has already been recorded. Multiple submissions are prohibited."
        }), 409

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO guests (name, phone, email, status, registered_at) VALUES (?, ?, ?, 'Pending', ?)",
        (name, phone, email, now)
    )
    conn.commit()
    conn.close()

    notify_host_new_guest(name, phone, email)
    return jsonify({"success": True, "message": "Registration submitted successfully."})

# Separate Host Backend
@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    status_filter = request.args.get("status", "All")
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM guests")
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Approved'")
    approved_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Pending'")
    pending_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guests WHERE status = 'Rejected'")
    rejected_count = cursor.fetchone()[0]

    counts = {
        "total": total_count,
        "approved": approved_count,
        "pending": pending_count,
        "rejected": rejected_count
    }

    if status_filter in ["Pending", "Approved", "Rejected"]:
        cursor.execute("SELECT * FROM guests WHERE status = ? ORDER BY id DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM guests ORDER BY id DESC")
    guests = cursor.fetchall()
    conn.close()

    return render_template_string(
        ADMIN_PAGE_HTML,
        guests=guests,
        counts=counts,
        current_status=status_filter
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        else:
            error = "Invalid admin password."
    return render_template_string(LOGIN_PAGE_HTML, error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/action/<int:guest_id>/<string:new_status>")
def admin_action(guest_id, new_status):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    if new_status in ["Approved", "Rejected"]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM guests WHERE id = ?", (guest_id,))
        guest = cursor.fetchone()

        if guest:
            cursor.execute("UPDATE guests SET status = ? WHERE id = ?", (new_status, guest_id))
            conn.commit()
            if new_status == "Approved":
                notify_guest_approved(guest["name"], guest["email"])
        conn.close()

    return redirect(url_for("admin"))

@app.route("/admin/export/json")
def export_json():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guests ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(rows)

# ==============================================================================
# 6. RAILWAY PRODUCTION ENTRYPOINT (Dynamic Port Binding)
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Afterparty Backend on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
