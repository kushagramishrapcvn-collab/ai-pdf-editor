import os
import sqlite3
import re
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, flash

# ==============================================================================
# 1. APP & CONFIGURATION
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "afterparty_luxury_secret_key_999")

DB_FILE = os.environ.get("DB_PATH", "afterparty_database.db")
HOST_EMAIL = os.environ.get("HOST_EMAIL", "kushagramishra.pcvn@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "afterpartyadmin")

# Gmail SMTP Configuration for Automated Ticket Emails
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", HOST_EMAIL)
# 16-character Google App Password (set in Railway Variables -> SENDER_PASSWORD)
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "").strip()

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
            registered_at TEXT NOT NULL,
            ticket_code TEXT
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
# 3. EMAIL DISPATCH HELPERS WITH DIRECT IN-EMAIL QR CODE
# ==============================================================================
def send_email(to_email, subject, html_content):
    if not SENDER_PASSWORD:
        print("⚠️ Warning: SENDER_PASSWORD is not set in Railway. Email could not be sent.")
        return False, "SENDER_PASSWORD not set in Railway environment variables."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Afterparty Guestlist <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"✅ Email successfully sent to {to_email}")
        return True, "Email sent successfully."
    except Exception as e:
        err_msg = str(e)
        print(f"❌ Error sending email to {to_email}: {err_msg}")
        return False, err_msg

def notify_host_new_guest(name, phone, email):
    subject = f"🎉 New Registration Pending Approval: {name}"
    html = f"""
    <div style="font-family: sans-serif; background-color: #070d1e; color: #ffffff; padding: 25px; border-radius: 12px;">
      <h3 style="color: #60a5fa;">New Afterparty Registration Request</h3>
      <p>A new guest has applied to attend:</p>
      <ul>
          <li><b>Name (As per ID):</b> {name}</li>
          <li><b>Mobile Number:</b> {phone}</li>
          <li><b>Gmail ID:</b> {email}</li>
          <li><b>Status:</b> Pending Approval</li>
      </ul>
      <p>Log in to your private host backend (<code>/admin</code>) to review and approve.</p>
    </div>
    """
    send_email(HOST_EMAIL, subject, html)

def notify_guest_approved(name, guest_email, verify_url, pass_url, ticket_code):
    subject = f"🎟️ Your Official Afterparty VIP Ticket & QR Code [{ticket_code}]"
    qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={urllib.parse.quote_plus(verify_url)}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Afterparty VIP Ticket</title>
    </head>
    <body style="margin: 0; padding: 30px 10px; background-color: #070d1e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 480px; background-color: #0d172e; border: 1px solid rgba(99, 137, 214, 0.4); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 50px rgba(0,0,0,0.8);">
        <!-- TICKET HEADER -->
        <tr>
          <td align="center" style="background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #3b82f6 100%); padding: 32px 24px; color: #ffffff;">
            <div style="display: inline-block; background-color: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.35); padding: 5px 14px; border-radius: 100px; font-size: 11px; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; color: #fef08a; margin-bottom: 8px;">
              ★ OFFICIAL VIP ENTRY PASS ★
            </div>
            <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.01em;">EXCLUSIVE AFTERPARTY</h1>
            <p style="margin: 6px 0 0 0; font-size: 13px; color: #bfdbfe;">Pass Code: <b style="color: #ffffff;">{ticket_code}</b></p>
          </td>
        </tr>

        <!-- QR CODE SECTION -->
        <tr>
          <td align="center" style="padding: 32px 24px 20px 24px;">
            <div style="background-color: #ffffff; padding: 14px; border-radius: 16px; display: inline-block; box-shadow: 0 8px 24px rgba(0,0,0,0.5);">
              <img src="{qr_img_url}" width="200" height="200" alt="VIP Entry QR Code" style="display: block; border: 0; border-radius: 8px;">
            </div>
            <p style="margin: 14px 0 0 0; color: #60a5fa; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">
              SCAN QR CODE AT VENUE ENTRANCE
            </p>
          </td>
        </tr>

        <!-- GUEST DETAILS BOX -->
        <tr>
          <td style="padding: 0 24px 24px 24px;">
            <table width="100%" cellpadding="10" cellspacing="0" style="background-color: #091124; border: 1px solid rgba(99, 137, 214, 0.25); border-radius: 12px; color: #ffffff; font-size: 13.5px;">
              <tr>
                <td style="color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.06);">Status</td>
                <td align="right" style="border-bottom: 1px solid rgba(255,255,255,0.06); font-weight: 800; color: #34d399;">VERIFIED GUEST ✓</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.06);">Guest Name (ID)</td>
                <td align="right" style="border-bottom: 1px solid rgba(255,255,255,0.06); font-weight: 700; color: #ffffff;">{name}</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.06);">Mobile Number</td>
                <td align="right" style="border-bottom: 1px solid rgba(255,255,255,0.06); font-weight: 600; color: #ffffff;">(Registered)</td>
              </tr>
              <tr>
                <td style="color: #94a3b8;">Registered Gmail</td>
                <td align="right" style="font-weight: 600; color: #ffffff;">{guest_email}</td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- DOOR RULES & LINK -->
        <tr>
          <td style="padding: 0 24px 30px 24px; text-align: center;">
            <p style="margin: 0 0 20px 0; color: #cbd5e1; font-size: 12.5px; line-height: 1.5;">
              ⚠️ <b>Door Verification Policy:</b> Entry will only be granted if the name on your physical government/official ID matches <b>"{name}"</b>.
            </p>
            <a href="{pass_url}" style="display: inline-block; background: linear-gradient(135deg, #1d4ed8, #3b82f6); color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; font-size: 13.5px; box-shadow: 0 4px 15px rgba(29, 78, 216, 0.4);">
              View Digital Web Pass
            </a>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    return send_email(guest_email, subject, html)

# ==============================================================================
# 4. TEMPLATES (LUXURY DARK BLUE & WHITE)
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
          <label>Gmail ID <span class="label-hint">(Ticket with QR will be sent here)</span></label>
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
      <p style="color:#64748b; font-size:12px;">You cannot submit again. As soon as the host approves, your official VIP ticket with your scannable QR Code will be delivered directly to your Gmail.</p>
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

PASS_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VIP Entry Pass | {{ guest.name }}</title>
  <style>
    :root {
      --bg: #070d1e;
      --card-bg: rgba(13, 23, 46, 0.95);
      --card-border: rgba(99, 137, 214, 0.35);
      --royal: #2563eb;
      --gold: #f59e0b;
      --white: #ffffff;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: var(--bg);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(30, 64, 175, 0.4) 0%, transparent 60%),
        radial-gradient(circle at 50% 100%, rgba(15, 23, 42, 0.8) 0%, transparent 50%);
      color: var(--white);
      font-family: var(--font);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
    }
    .ticket-container {
      width: 100%;
      max-width: 420px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 25px 60px rgba(0,0,0,0.8), 0 0 35px rgba(37, 99, 235, 0.25);
    }
    .ticket-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #3b82f6 100%);
      padding: 28px 24px;
      text-align: center;
    }
    .vip-badge {
      display: inline-block;
      background: rgba(0,0,0,0.3);
      border: 1px solid rgba(255,255,255,0.3);
      padding: 4px 14px;
      border-radius: 100px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: #fef08a;
      margin-bottom: 8px;
    }
    .ticket-header h1 { font-size: 22px; font-weight: 800; margin-bottom: 4px; }
    .ticket-header p { font-size: 12px; color: #bfdbfe; }
    .ticket-body { padding: 32px 24px; text-align: center; }
    .qr-frame {
      width: 200px;
      height: 200px;
      margin: 0 auto 20px;
      background: #ffffff;
      border-radius: 16px;
      padding: 12px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .qr-frame img { width: 100%; height: 100%; display: block; border-radius: 8px; }
    .ticket-info {
      background: rgba(9, 17, 36, 0.8);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 16px 20px;
      text-align: left;
      font-size: 13.5px;
      margin-bottom: 20px;
    }
    .info-row { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #94a3b8; }
    .info-val { font-weight: 700; color: #fff; }
    .status-pill {
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
      padding: 2px 10px;
      border-radius: 100px;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .notice { font-size: 12px; color: #94a3b8; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="ticket-container">
    <div class="ticket-header">
      <span class="vip-badge">★ VIP ENTRY PASS ★</span>
      <h1>Official Afterparty Access</h1>
      <p>Pass Code: <b>{{ guest.ticket_code }}</b></p>
    </div>

    <div class="ticket-body">
      {% if guest.status == 'Approved' %}
        <div class="qr-frame">
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={{ verify_url | urlencode }}" alt="Scan for Door Verification">
        </div>
        <div style="font-size:12px; color:#60a5fa; font-weight:700; margin-bottom:18px;">
          SCAN QR CODE AT VENUE ENTRANCE
        </div>

        <div class="ticket-info">
          <div class="info-row"><span class="info-label">Status</span><span class="status-pill">VERIFIED GUEST</span></div>
          <div class="info-row"><span class="info-label">Guest Name (ID)</span><span class="info-val">{{ guest.name }}</span></div>
          <div class="info-row"><span class="info-label">Mobile Number</span><span class="info-val">{{ guest.phone }}</span></div>
          <div class="info-row"><span class="info-label">Gmail ID</span><span class="info-val">{{ guest.email }}</span></div>
        </div>
        <p class="notice">
          ⚠️ <b>ID Check:</b> Entry will strictly be checked against your official ID matching <b>"{{ guest.name }}"</b>.
        </p>
      {% elif guest.status == 'Pending' %}
        <div style="padding: 40px 10px;">
          <h2 style="color:#fbbf24; margin-bottom:10px;">Review In Progress</h2>
          <p class="notice">Your registration is currently pending host approval. Your scannable VIP QR pass will unlock here once approved.</p>
        </div>
      {% else %}
        <div style="padding: 40px 10px;">
          <h2 style="color:#ef4444; margin-bottom:10px;">Registration Declined</h2>
          <p class="notice">Unfortunately, your access request was not approved.</p>
        </div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

VERIFY_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Door Verification</title>
  <style>
    body { background:#070d1e; color:#fff; font-family:-apple-system, sans-serif; display:flex; align-items:center; justify-content:center; min-height:100vh; padding:20px; margin:0; }
    .box { background:#0d172e; border:1px solid rgba(99,137,214,0.3); border-radius:20px; padding:36px; max-width:440px; width:100%; text-align:center; }
    .icon { width:70px; height:70px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px; font-size:32px; }
    .valid { background:rgba(16,185,129,0.2); border:2px solid #10b981; color:#10b981; }
    .invalid { background:rgba(239,68,68,0.2); border:2px solid #ef4444; color:#ef4444; }
    .details { background:#091124; border-radius:12px; padding:16px; text-align:left; margin:20px 0; font-size:14px; border:1px solid #1e293b; }
    .row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.06); }
    .row:last-child { border-bottom:none; }
  </style>
</head>
<body>
  <div class="box">
    {% if guest and guest.status == 'Approved' %}
      <div class="icon valid">✓</div>
      <h2 style="color:#34d399; margin-bottom:6px;">ENTRY AUTHORIZED</h2>
      <p style="color:#94a3b8; font-size:13px;">Official Approved VIP Guest</p>
      
      <div class="details">
        <div class="row"><span style="color:#94a3b8;">Ticket Code</span><b style="color:#fbbf24;">{{ guest.ticket_code }}</b></div>
        <div class="row"><span style="color:#94a3b8;">Match With ID</span><b>{{ guest.name }}</b></div>
        <div class="row"><span style="color:#94a3b8;">Mobile Number</span><b>{{ guest.phone }}</b></div>
        <div class="row"><span style="color:#94a3b8;">Gmail ID</span><b>{{ guest.email }}</b></div>
        <div class="row"><span style="color:#94a3b8;">Status</span><b style="color:#34d399;">APPROVED</b></div>
      </div>
      <p style="color:#cbd5e1; font-size:12px;">Verify that the visitor's physical ID matches <b>"{{ guest.name }}"</b> before admitting.</p>
    {% else %}
      <div class="icon invalid">✕</div>
      <h2 style="color:#f87171; margin-bottom:6px;">ENTRY DENIED</h2>
      <p style="color:#94a3b8; font-size:13px;">This QR Code is invalid or has not been approved by the host.</p>
    {% endif %}
  </div>
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
    main { padding: 32px; max-width: 1280px; margin: 0 auto; }
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
    .alert-banner { padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; font-size: 13.5px; }
    .alert-banner.success { background: rgba(16, 185, 129, 0.2); border: 1px solid var(--success); color: #6ee7b7; }
    .alert-banner.warning { background: rgba(245, 158, 11, 0.2); border: 1px solid var(--warning); color: #fde68a; }
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
    .btn-view { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
    .btn-view:hover { background: #2563eb; color: #fff; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>🔒 Host Operations Backend</h1>
      <p>Direct Database Review, Approvals & Automated QR Email Dispatch</p>
    </div>
    <div>
      <a href="/admin/logout" class="filter-btn">Log Out</a>
    </div>
  </header>

  <main>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert-banner {{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if not smtp_configured %}
      <div class="alert-banner warning">
        ⚠️ <b>Gmail SMTP is not configured yet!</b> Set the <code>SENDER_PASSWORD</code> environment variable in Railway to enable automatic email dispatch. (Approvals will still work and unlock web QR passes).
      </div>
    {% endif %}

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
          <th>Pass Code</th>
          <th>Name (As on ID)</th>
          <th>Mobile Number</th>
          <th>Gmail ID</th>
          <th>Registered At</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for guest in guests %}
        <tr>
          <td style="color:#fbbf24; font-weight:700;">{{ guest.ticket_code or ('#AP-' ~ guest.id) }}</td>
          <td style="font-weight:700; color:#fff;">{{ guest.name }}</td>
          <td>{{ guest.phone }}</td>
          <td>{{ guest.email }}</td>
          <td style="color:#94a3b8; font-size:12px;">{{ guest.registered_at }}</td>
          <td><span class="badge-status {{ guest.status }}">{{ guest.status }}</span></td>
          <td>
            {% if guest.status != 'Approved' %}
              <a href="/admin/action/{{ guest.id }}/Approved" class="btn-act btn-app">Approve & Email QR</a>
            {% endif %}
            {% if guest.status != 'Rejected' %}
              <a href="/admin/action/{{ guest.id }}/Rejected" class="btn-act btn-rej">Reject</a>
            {% endif %}
            {% if guest.status == 'Approved' %}
              <a href="/pass/{{ guest.id }}" target="_blank" class="btn-act btn-view">View QR Ticket</a>
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
    new_id = cursor.lastrowid
    ticket_code = f"VIP-{new_id:04d}"
    cursor.execute("UPDATE guests SET ticket_code = ? WHERE id = ?", (ticket_code, new_id))
    conn.commit()
    conn.close()

    notify_host_new_guest(name, phone, email)

    return jsonify({"success": True, "message": "Registration submitted successfully."})

# Digital VIP Pass with Scannable QR Code
@app.route("/pass/<int:guest_id>")
def view_pass(guest_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
    guest = cursor.fetchone()
    conn.close()

    if not guest:
        return "Pass not found", 404

    base_url = request.host_url.rstrip("/")
    verify_url = f"{base_url}/verify/{guest_id}"

    return render_template_string(PASS_PAGE_HTML, guest=guest, verify_url=verify_url)

# Door Verification Endpoint (Triggered when bouncer scans the QR code)
@app.route("/verify/<int:guest_id>")
def verify_door(guest_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
    guest = cursor.fetchone()
    conn.close()

    return render_template_string(VERIFY_PAGE_HTML, guest=guest)

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
        current_status=status_filter,
        smtp_configured=bool(SENDER_PASSWORD)
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

# Host Approval Action: Sends Email with QR Code immediately
@app.route("/admin/action/<int:guest_id>/<string:new_status>")
def admin_action(guest_id, new_status):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    if new_status in ["Approved", "Rejected"]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, email, ticket_code FROM guests WHERE id = ?", (guest_id,))
        guest = cursor.fetchone()

        if guest:
            cursor.execute("UPDATE guests SET status = ? WHERE id = ?", (new_status, guest_id))
            conn.commit()
            
            if new_status == "Approved":
                base_url = request.host_url.rstrip("/")
                verify_url = f"{base_url}/verify/{guest_id}"
                pass_url = f"{base_url}/pass/{guest_id}"
                success, msg = notify_guest_approved(
                    guest["name"], 
                    guest["email"], 
                    verify_url, 
                    pass_url, 
                    guest["ticket_code"]
                )
                if success:
                    flash(f"✅ Approved {guest['name']}! VIP ticket with QR Code was emailed to {guest['email']}.", "success")
                else:
                    flash(f"⚠️ Approved {guest['name']}, but email failed ({msg}). Check Railway SENDER_PASSWORD variable.", "warning")
            else:
                flash(f"Status for {guest['name']} updated to Rejected.", "warning")
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
# 6. RAILWAY PRODUCTION ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Afterparty Backend on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
