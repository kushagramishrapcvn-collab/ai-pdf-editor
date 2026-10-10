import os
import sqlite3
import re
import smtplib
import json
import urllib.request
import urllib.parse
import urllib.error
import threading
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
HOST_EMAIL = os.environ.get("HOST_EMAIL", "kushagramishra.pcvn@gmail.com").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "afterpartyadmin")

# Resend API Configuration (HTTPS Port 443 - Recommended for Railway)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_QoCn2b2W_AD3oRb3TswSQChHnX98CVDWH").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()

# Gmail SMTP Configuration (Fallback)
SMTP_SERVER = "smtp.gmail.com"
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", HOST_EMAIL).strip()
RAW_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
SENDER_PASSWORD = re.sub(r"\s+", "", RAW_PASSWORD).strip()

# ==============================================================================
# 2. TEMPLATE FILTERS & HELPERS
# ==============================================================================
@app.template_filter('whatsapp_phone')
def whatsapp_phone_filter(phone):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return "91" + digits
    return digits

@app.template_filter('urlencode')
def urlencode_filter(s):
    return urllib.parse.quote_plus(str(s or ""))

# ==============================================================================
# 3. SQL DATABASE INITIALIZATION
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
# 4. DIRECT & ASYNCHRONOUS EMAIL SENDER (RESEND API + SMTP FALLBACK)
# ==============================================================================
def send_via_resend(to_email, subject, html_content):
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY is not configured in Railway Variables."
    
    url = "https://api.resend.com/emails"
    from_header = RESEND_FROM_EMAIL
    if "@" not in from_header:
        from_header = "onboarding@resend.dev"
    if "<" not in from_header:
        from_header = f"Afterparty VIP <{from_header}>"
        
    payload = {
        "from": from_header,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "AfterpartyApp/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_body = response.read().decode("utf-8")
            return True, f"Resend API OK: {res_body}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return False, f"Resend HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, f"Resend Network Error: {str(e)}"

def send_email_direct(to_email, subject, html_content):
    # 1. Primary: Resend API (HTTPS Port 443 - zero firewall blocks on Railway)
    if RESEND_API_KEY:
        ok, res = send_via_resend(to_email, subject, html_content)
        if ok:
            return True, f"Delivered via Resend API: {res}"
        print(f"[WARN] Resend attempt failed: {res}. Trying SMTP fallback...")

    # 2. Secondary Fallback: Gmail SMTP (SSL 465 / TLS 587)
    if SENDER_PASSWORD:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Afterparty Host <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=8) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
            return True, "Delivered via Gmail SMTP (SSL 465)"
        except Exception as e_ssl:
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=8) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
                return True, "Delivered via Gmail SMTP (STARTTLS 587)"
            except Exception as e_tls:
                if RESEND_API_KEY:
                    return False, f"Resend: {res} | SMTP: {e_tls}"
                return False, f"SMTP Error (Railway port filter): {e_tls}"

    if not RESEND_API_KEY and not SENDER_PASSWORD:
        return False, "Neither RESEND_API_KEY nor SENDER_PASSWORD configured in Railway Variables."

    return False, f"Email delivery failed: {res}"

def async_send_email(to_email, subject, html_content):
    def worker():
        ok, msg = send_email_direct(to_email, subject, html_content)
        print(f"[{'SUCCESS' if ok else 'FAILURE'}] Sending email to {to_email}: {msg}")
    threading.Thread(target=worker, daemon=True).start()

def notify_host_new_guest(name, phone, email):
    subject = f"🎉 New Registration: {name}"
    html = f"""
    <div style="font-family: sans-serif; background-color: #0b132b; color: #ffffff; padding: 25px; border-radius: 12px;">
      <h3 style="color: #f59e0b;">New Afterparty Registration</h3>
      <p>A new guest has applied:</p>
      <ul>
          <li><b>Name:</b> {name}</li>
          <li><b>WhatsApp:</b> {phone}</li>
          <li><b>Gmail:</b> {email}</li>
          <li><b>Status:</b> Pending Approval</li>
      </ul>
      <p>Log in to <code>/admin</code> to review and approve.</p>
    </div>
    """
    async_send_email(HOST_EMAIL, subject, html)

def notify_guest_approved(name, guest_email, verify_url, pass_url, ticket_code):
    subject = f"🎟️ Official Afterparty VIP Ticket & QR Code [{ticket_code}]"
    qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={urllib.parse.quote_plus(verify_url)}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 30px 10px; background-color: #060b18; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 480px; background-color: #0f1c3f; border: 1px solid rgba(212, 175, 55, 0.4); border-radius: 20px; overflow: hidden;">
        <tr>
          <td align="center" style="background: linear-gradient(135deg, #0b1536 0%, #1e3a8a 100%); padding: 32px 24px; border-bottom: 2px solid #d4af37;">
            <div style="display: inline-block; background-color: rgba(212, 175, 55, 0.15); border: 1px solid #d4af37; padding: 5px 14px; border-radius: 100px; font-size: 11px; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; color: #fde68a; margin-bottom: 10px;">
              ★ OFFICIAL VIP PASS ★
            </div>
            <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff;">EXCLUSIVE AFTERPARTY</h1>
            <p style="margin: 6px 0 0 0; font-size: 13px; color: #cbd5e1;">Pass Code: <b style="color: #fde68a;">{ticket_code}</b></p>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding: 32px 24px 20px 24px;">
            <div style="background-color: #ffffff; padding: 14px; border-radius: 16px; display: inline-block;">
              <img src="{qr_img_url}" width="200" height="200" alt="VIP Entry QR Code" style="display: block; border: 0; border-radius: 8px;">
            </div>
            <p style="margin: 14px 0 0 0; color: #f59e0b; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;">
              SCAN QR CODE AT VENUE ENTRANCE
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding: 0 24px 24px 24px;">
            <table width="100%" cellpadding="10" cellspacing="0" style="background-color: #081026; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; color: #ffffff; font-size: 13.5px;">
              <tr>
                <td style="color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.06);">Status</td>
                <td align="right" style="border-bottom: 1px solid rgba(255,255,255,0.06); font-weight: 800; color: #34d399;">VERIFIED GUEST ✓</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.06);">Guest Name (ID)</td>
                <td align="right" style="border-bottom: 1px solid rgba(255,255,255,0.06); font-weight: 700; color: #ffffff;">{name}</td>
              </tr>
              <tr>
                <td style="color: #94a3b8;">Registered Gmail</td>
                <td align="right" style="font-weight: 600; color: #ffffff;">{guest_email}</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding: 0 24px 30px 24px; text-align: center;">
            <p style="margin: 0 0 20px 0; color: #cbd5e1; font-size: 12.5px; line-height: 1.5;">
              ⚠️ <b>Door Policy:</b> Carry your physical government ID matching <b>"{name}"</b> for entry verification.
            </p>
            <a href="{pass_url}" style="display: inline-block; background: linear-gradient(135deg, #d4af37, #f59e0b); color: #060b18; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: 800; font-size: 13.5px;">
              Open Digital Web Pass
            </a>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    async_send_email(guest_email, subject, html)

# ==============================================================================
# 5. TEMPLATES (LUXURY GOLD & MIDNIGHT NAVY - ORIGINAL PENDING CARD DESIGN)
# ==============================================================================

GUEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Afterparty VIP Registration</title>
  <style>
    :root {
      --bg-base: #060b18;
      --card-bg: #0f1c3f;
      --card-border: rgba(212, 175, 55, 0.35);
      --gold-primary: #d4af37;
      --gold-light: #fef08a;
      --gold-gradient: linear-gradient(135deg, #d4af37 0%, #f59e0b 50%, #fbbf24 100%);
      --text-white: #ffffff;
      --text-ivory: #f8fafc;
      --text-muted: #94a3b8;
      --input-bg: #081026;
      --input-border: #1e293b;
      --danger: #ef4444;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: var(--bg-base);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(30, 58, 138, 0.45) 0%, transparent 60%),
        radial-gradient(circle at 85% 90%, rgba(212, 175, 55, 0.12) 0%, transparent 45%);
      color: var(--text-white);
      font-family: var(--font);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
    }
    .card {
      width: 100%;
      max-width: 480px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 22px;
      padding: 42px 32px;
      box-shadow: 0 25px 50px rgba(0,0,0,0.8), 0 0 30px rgba(212, 175, 55, 0.15);
      position: relative;
    }
    .card::before {
      content: "";
      position: absolute;
      top: 0;
      left: 15%;
      right: 15%;
      height: 2px;
      background: linear-gradient(90deg, transparent, #d4af37, transparent);
    }
    .badge-bar { text-align: center; margin-bottom: 14px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 16px;
      background: rgba(212, 175, 55, 0.12);
      border: 1px solid rgba(212, 175, 55, 0.4);
      border-radius: 100px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--gold-light);
    }
    .badge-dot { width: 6px; height: 6px; background: var(--gold-primary); border-radius: 50%; box-shadow: 0 0 8px var(--gold-primary); }
    h1 {
      font-size: 27px;
      font-weight: 800;
      text-align: center;
      color: var(--text-white);
      margin-bottom: 8px;
      letter-spacing: -0.01em;
    }
    .subtitle {
      text-align: center;
      color: var(--text-muted);
      font-size: 13.5px;
      line-height: 1.5;
      margin-bottom: 24px;
    }
    .policy-box {
      background: rgba(8, 16, 38, 0.8);
      border: 1px solid rgba(212, 175, 55, 0.25);
      border-radius: 10px;
      padding: 11px 14px;
      margin-bottom: 22px;
      font-size: 12px;
      color: #fde68a;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .form-group { margin-bottom: 18px; }
    label { display: block; font-size: 13px; font-weight: 600; color: var(--text-ivory); margin-bottom: 7px; }
    .label-hint { font-weight: 400; color: var(--text-muted); font-size: 11.5px; }
    input {
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 11px;
      padding: 13px 16px;
      color: var(--text-white);
      font-size: 14.5px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus {
      border-color: var(--gold-primary);
      box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.2);
    }
    .btn-submit {
      width: 100%;
      padding: 15px;
      background: var(--gold-gradient);
      border: none;
      border-radius: 12px;
      color: #060b18;
      font-size: 15.5px;
      font-weight: 800;
      letter-spacing: 0.04em;
      cursor: pointer;
      margin-top: 10px;
      transition: transform 0.15s, filter 0.15s;
      box-shadow: 0 10px 25px rgba(212, 175, 55, 0.3);
    }
    .btn-submit:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .btn-submit:active { transform: translateY(0); }
    .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
    .alert { padding: 12px 14px; border-radius: 10px; font-size: 13px; margin-bottom: 18px; display: none; line-height: 1.5; }
    .alert-error { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #fca5a5; }
    .result-card {
      background: #081026;
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
      margin: 20px 0;
      text-align: left;
      font-size: 13.5px;
    }
    .result-row { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .result-row:last-child { border-bottom: none; }
    .tag-pending { background: rgba(245, 158, 11, 0.2); color: #fbbf24; padding: 3px 12px; border-radius: 100px; font-size: 11.5px; font-weight: 800; border: 1px solid rgba(245, 158, 11, 0.4); }
    footer {
      margin-top: 24px;
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
    }
    footer a { color: var(--gold-primary); text-decoration: none; font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <div id="formSection">
      <div class="badge-bar">
        <span class="badge"><span class="badge-dot"></span>VIP Guestlist Registration</span>
      </div>
      <h1>Afterparty Registration</h1>
      <p class="subtitle">Enter your official credentials. Submissions are individually verified and approved by the host.</p>
      
      <div class="policy-box">
        <span>🔒 <b>Strict Notice:</b> Limit 1 request per person. Duplicate Mobile Numbers or Gmail IDs are automatically rejected.</span>
      </div>

      <div id="alertBox" class="alert"></div>

      <form id="regForm">
        <div class="form-group">
          <label>Name <span class="label-hint">(As on your Official ID)</span></label>
          <input type="text" id="name" placeholder="e.g. Kushagra Mishra" required autocomplete="name">
        </div>
        <div class="form-group">
          <label>WhatsApp Number <span class="label-hint">(VIP Pass with QR Code will be sent here)</span></label>
          <input type="tel" id="phone" placeholder="e.g. 9876543210" required autocomplete="tel">
        </div>
        <div class="form-group">
          <label>Gmail ID <span class="label-hint">(Registration record)</span></label>
          <input type="email" id="email" placeholder="e.g. yourname@gmail.com" required autocomplete="email">
        </div>
        <button type="submit" class="btn-submit" id="submitBtn">Request VIP Access</button>
      </form>

      <footer>
        Host backstage portal &bull; <a href="/admin">Host Login</a>
      </footer>
    </div>

    <!-- SUCCESS / PENDING STATUS SCREEN (AS REQUESTED) -->
    <div id="successSection" style="display:none; text-align:center;">
      <div style="width: 58px; height: 58px; margin: 0 auto 16px auto; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 26px;">
        ⏳
      </div>
      <h2 style="font-size:23px; font-weight:800; margin-bottom:8px; color:#fff;">Request Submitted!</h2>
      <p style="color:#94a3b8; font-size:13.5px; margin-bottom:18px;">Your application has been locked in the guestlist and submitted to the host for review.</p>
      
      <div class="result-card">
        <div class="result-row">
          <span style="color:#94a3b8;">Status</span>
          <span class="tag-pending">Pending Approval</span>
        </div>
        <div class="result-row">
          <span style="color:#94a3b8;">Pass Code</span>
          <span style="font-weight:700; color:#fde68a;" id="resTicket">-</span>
        </div>
        <div class="result-row">
          <span style="color:#94a3b8;">Name (As on ID)</span>
          <span style="font-weight:700; color:#fff;" id="resName">-</span>
        </div>
        <div class="result-row">
          <span style="color:#94a3b8;">WhatsApp Number</span>
          <span style="font-weight:700; color:#fff;" id="resPhone">-</span>
        </div>
        <div class="result-row">
          <span style="color:#94a3b8;">Gmail ID</span>
          <span style="font-weight:600; color:#cbd5e1;" id="resEmail">-</span>
        </div>
      </div>

      <div style="background: rgba(37, 211, 102, 0.1); border: 1px solid rgba(37, 211, 102, 0.35); border-radius: 12px; padding: 13px 15px; margin-top: 18px; text-align: left;">
        <p style="color: #6ee7b7; font-size: 13px; margin: 0; line-height: 1.5;">
          📲 <b>WhatsApp Pass Delivery:</b> Once the host approves your entry, your official VIP ticket with scannable QR Code will be dispatched directly to your WhatsApp.
        </p>
      </div>

      <p style="font-size: 12px; color: #64748b; margin-top: 18px;">
        ⚠️ Door Rule: Limit 1 request per person. Please carry physical government ID at the venue entrance.
      </p>
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
      submitBtn.textContent = 'Submitting...';

      try {
        const res = await fetch('/', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name, phone, email })
        });
        const data = await res.json();

        if (data.status === 'success' || data.success) {
          document.getElementById('formSection').style.display = 'none';
          document.getElementById('resTicket').textContent = data.ticket_code || 'AP-PENDING';
          document.getElementById('resName').textContent = name;
          document.getElementById('resPhone').textContent = phone;
          document.getElementById('resEmail').textContent = email;
          document.getElementById('successSection').style.display = 'block';
        } else {
          alertBox.className = 'alert alert-error';
          alertBox.innerHTML = '<b>⚠️ Notice:</b> ' + (data.message || 'Error submitting registration.');
          alertBox.style.display = 'block';
        }
      } catch (err) {
        alertBox.className = 'alert alert-error';
        alertBox.textContent = 'Network error. Please try again.';
        alertBox.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Request VIP Access';
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
  <title>VIP Pass - {{ guest.name }}</title>
  <style>
    :root {
      --bg: #060b18;
      --card-bg: #0f1c3f;
      --gold: #d4af37;
      --gold-light: #fef08a;
      --text-white: #ffffff;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 16px;
      color: #fff;
    }
    .ticket {
      width: 100%;
      max-width: 440px;
      background: var(--card-bg);
      border: 1px solid rgba(212, 175, 55, 0.4);
      border-radius: 22px;
      overflow: hidden;
      box-shadow: 0 30px 60px rgba(0,0,0,0.85), 0 0 35px rgba(212, 175, 55, 0.2);
    }
    .ticket-header {
      background: linear-gradient(135deg, #0b1536 0%, #1e3a8a 100%);
      padding: 30px 24px;
      text-align: center;
      border-bottom: 2px solid var(--gold);
    }
    .vip-tag {
      background: rgba(212, 175, 55, 0.2);
      border: 1px solid var(--gold);
      color: var(--gold-light);
      padding: 4px 14px;
      border-radius: 100px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      display: inline-block;
      margin-bottom: 10px;
    }
    h1 { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
    .ticket-body { padding: 32px 24px; text-align: center; }
    .qr-box {
      background: #fff;
      padding: 16px;
      border-radius: 18px;
      display: inline-block;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .qr-box img { display: block; border-radius: 8px; }
    .meta-table {
      width: 100%;
      margin-top: 24px;
      background: #081026;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.08);
      font-size: 13.5px;
    }
    .meta-table td { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .meta-table tr:last-child td { border-bottom: none; }
    .label { color: var(--text-muted); text-align: left; }
    .val { text-align: right; font-weight: 700; color: #fff; }
    .notice {
      margin-top: 20px;
      font-size: 12px;
      color: #cbd5e1;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <div class="ticket">
    <div class="ticket-header">
      <div class="vip-tag">★ OFFICIAL VIP PASS ★</div>
      <h1>EXCLUSIVE AFTERPARTY</h1>
      <p style="color: #cbd5e1; font-size: 13px;">Pass Code: <b style="color: #fde68a;">{{ guest.ticket_code or ('#AP-' ~ guest.id) }}</b></p>
    </div>
    <div class="ticket-body">
      <div class="qr-box">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={{ verify_url_encoded }}" width="220" height="220" alt="VIP Pass QR">
      </div>
      <p style="color: var(--gold); font-size: 12px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 14px;">
        Scan at venue entry
      </p>

      <table class="meta-table">
        <tr>
          <td class="label">Pass Status</td>
          <td class="val" style="color: #34d399;">VERIFIED GUEST ✓</td>
        </tr>
        <tr>
          <td class="label">Guest Name (ID)</td>
          <td class="val">{{ guest.name }}</td>
        </tr>
        <tr>
          <td class="label">WhatsApp Number</td>
          <td class="val">{{ guest.phone }}</td>
        </tr>
        <tr>
          <td class="label">Registered Email</td>
          <td class="val" style="font-size: 12.5px;">{{ guest.email }}</td>
        </tr>
      </table>

      <p class="notice">
        ⚠️ <b>Door Rule:</b> Show this QR Code and carry your physical ID matching "<b>{{ guest.name }}</b>" for entry.
      </p>
    </div>
  </div>
</body>
</html>
"""

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Host Login</title>
  <style>
    body {
      background: #060b18;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }
    .box {
      width: 100%;
      max-width: 380px;
      background: #0f1c3f;
      border: 1px solid rgba(212, 175, 55, 0.4);
      border-radius: 18px;
      padding: 36px 28px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.8);
      text-align: center;
    }
    h2 { margin-bottom: 20px; font-size: 20px; font-weight: 800; color: #fff; }
    input {
      width: 100%;
      box-sizing: border-box;
      background: #081026;
      border: 1px solid #1e293b;
      border-radius: 10px;
      padding: 12px 14px;
      color: #fff;
      font-size: 14px;
      margin-bottom: 16px;
      outline: none;
    }
    input:focus { border-color: #d4af37; }
    button {
      width: 100%;
      background: linear-gradient(135deg, #d4af37, #f59e0b);
      border: none;
      padding: 13px;
      border-radius: 10px;
      font-weight: 800;
      color: #060b18;
      cursor: pointer;
      font-size: 14.5px;
    }
    .err { color: #f87171; font-size: 13px; margin-bottom: 14px; }
  </style>
</head>
<body>
  <div class="box">
    <h2>🔒 Host Operations Login</h2>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST">
      <input type="password" name="password" placeholder="Enter Host Password" required autofocus>
      <button type="submit">Access Control Center</button>
    </form>
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
      --bg: #060b18;
      --panel: #0d172e;
      --border: rgba(212, 175, 55, 0.3);
      --gold: #d4af37;
      --white: #ffffff;
      --muted: #94a3b8;
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
    .kpi-card { background: var(--panel); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 22px; }
    .kpi-card.total { border-left: 4px solid var(--gold); }
    .kpi-card.approved { border-left: 4px solid var(--success); }
    .kpi-card.pending { border-left: 4px solid var(--warning); }
    .kpi-card.rejected { border-left: 4px solid var(--danger); }
    .kpi-title { font-size: 12px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; font-weight: 700; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #fff; margin-top: 6px; }
    .controls { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
    .filter-btn { background: var(--panel); border: 1px solid rgba(255,255,255,0.1); color: var(--muted); padding: 8px 16px; border-radius: 8px; cursor: pointer; text-decoration: none; font-size: 13px; font-weight: 600; }
    .filter-btn.active { background: #d4af37; color: #060b18; font-weight: 800; }
    .alert-banner { padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; font-size: 13.5px; }
    .alert-banner.success { background: rgba(16, 185, 129, 0.2); border: 1px solid var(--success); color: #6ee7b7; }
    .alert-banner.warning { background: rgba(245, 158, 11, 0.2); border: 1px solid var(--warning); color: #fde68a; }
    table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; overflow: hidden; }
    th { background: rgba(8,16,38,0.95); padding: 14px 18px; font-size: 12px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid rgba(255,255,255,0.08); text-align: left; }
    td { padding: 16px 18px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13.5px; }
    tr:hover td { background: rgba(212, 175, 55, 0.03); }
    .badge-status { padding: 3px 10px; border-radius: 100px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge-status.Pending { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    .badge-status.Approved { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .badge-status.Rejected { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    .btn-act { padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; text-decoration: none; display: inline-block; margin-right: 6px; }
    .btn-app { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .btn-app:hover { background: var(--success); color: #fff; }
    .btn-rej { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .btn-rej:hover { background: var(--danger); color: #fff; }
    .btn-view { background: rgba(212, 175, 55, 0.15); color: #fde68a; border: 1px solid var(--gold); }
    .btn-view:hover { background: var(--gold); color: #060b18; }
    .btn-whatsapp { background: #25d366; color: #060b18; border: 1px solid #25d366; font-weight: 800; box-shadow: 0 2px 8px rgba(37,211,102,0.3); }
    .btn-whatsapp:hover { background: #20ba59; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>🔒 Host Operations Backend</h1>
      <p>Direct Database Review, Approvals & WhatsApp / QR Pass Distribution</p>
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
          <th>WhatsApp Number</th>
          <th>Gmail ID</th>
          <th>Registered At</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for guest in guests %}
        <tr>
          <td style="color:#fde68a; font-weight:700;">{{ guest.ticket_code or ('#AP-' ~ guest.id) }}</td>
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
            {% if guest.status == 'Approved' %}
              <a href="/pass/{{ guest.id }}" target="_blank" class="btn-act btn-view">View QR</a>
              <a href="https://api.whatsapp.com/send?phone={{ guest.phone | whatsapp_phone }}&text=Hey%20{{ guest.name | urlencode }}!%20%F0%9F%8E%89%20Your%20VIP%20Pass%20for%20the%20Exclusive%20Afterparty%20is%20APPROVED.%0A%0A%F0%9F%8E%9F%20Pass%20Code:%20{{ guest.ticket_code }}%0A%F0%9F%93%B2%20View%20%26%20Scan%20Your%20QR%20Pass:%20{{ request.host_url.rstrip('/') }}/pass/{{ guest.id }}%0A%0A%E2%9A%A0%EF%B8%8F%20Door%20Policy:%20Carry%20your%20physical%20government%20ID%20matching%20{{ guest.name | urlencode }}%20at%20entry." target="_blank" class="btn-act btn-whatsapp">📱 Send WhatsApp Pass</a>
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

# ==============================================================================
# 6. CONTROLLER ROUTES
# ==============================================================================

@app.route("/", methods=["GET", "POST"])
@app.route("/api/register", methods=["POST"])
def index():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip().lower()

        if not name or not phone or not email:
            return jsonify({"status": "error", "success": False, "message": "All fields (Name, WhatsApp Number, Gmail ID) are strictly mandatory."}), 400

        # Duplicate checking
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM guests WHERE phone = ? OR email = ?", (phone, email))
        existing = cursor.fetchone()

        if existing:
            conn.close()
            status = existing["status"]
            return jsonify({
                "status": "error",
                "success": False,
                "message": f"This WhatsApp number or Gmail ID is already registered (Current status: {status}). Repeated submissions are not allowed."
            }), 409

        # Generate unique ticket pass identifier
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO guests (name, phone, email, status, registered_at) VALUES (?, ?, ?, 'Pending', ?)",
            (name, phone, email, now_str)
        )
        new_id = cursor.lastrowid
        ticket_code = f"AP-{new_id:04d}"
        cursor.execute("UPDATE guests SET ticket_code = ? WHERE id = ?", (ticket_code, new_id))
        conn.commit()
        conn.close()

        # Host Notification
        notify_host_new_guest(name, phone, email)

        return jsonify({
            "status": "success",
            "success": True,
            "ticket_code": ticket_code,
            "name": name,
            "phone": phone,
            "email": email,
            "message": f"Your VIP access application has been recorded (Pass #{ticket_code}). Once approved, your official QR ticket pass will be delivered to your WhatsApp ({phone})."
        })

    return render_template_string(GUEST_PAGE_HTML)

@app.route("/pass/<int:guest_id>")
def view_pass(guest_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
    guest = cursor.fetchone()
    conn.close()

    if not guest:
        return "Pass Not Found", 404

    base_url = request.host_url.rstrip("/")
    verify_url = f"{base_url}/verify/{guest_id}"
    verify_url_encoded = urllib.parse.quote_plus(verify_url)

    return render_template_string(
        PASS_PAGE_HTML, 
        guest=guest, 
        verify_url=verify_url, 
        verify_url_encoded=verify_url_encoded
    )

@app.route("/verify/<int:guest_id>")
def verify_ticket(guest_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
    guest = cursor.fetchone()
    conn.close()

    if not guest:
        return """
        <div style='background:#060b18; color:#ef4444; padding:50px; font-family:sans-serif; text-align:center;'>
          <h1>❌ INVALID PASS</h1>
          <p>This QR code does not match any registered guest record.</p>
        </div>
        """, 404

    if guest["status"] != "Approved":
        return f"""
        <div style='background:#060b18; color:#f59e0b; padding:50px; font-family:sans-serif; text-align:center;'>
          <h1>⚠️ ENTRY NOT CLEARED</h1>
          <p>Pass status for <b>{guest['name']}</b> is: <b>{guest['status']}</b>.</p>
        </div>
        """, 403

    return f"""
    <div style='background:#060b18; color:#10b981; padding:50px; font-family:sans-serif; text-align:center;'>
      <div style='border:2px solid #10b981; border-radius:18px; padding:30px; display:inline-block; background:#0d172e;'>
        <h1 style='color:#34d399; margin:0;'>✅ ACCESS GRANTED</h1>
        <h2 style='color:#ffffff; margin:10px 0;'>{guest['name']}</h2>
        <p style='color:#cbd5e1;'>Pass Code: <b>{guest['ticket_code']}</b></p>
        <p style='color:#94a3b8; font-size:13px;'>Carry physical ID matching "{guest['name']}".</p>
      </div>
    </div>
    """

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

# Direct Diagnostics Route (Check in browser tab)
@app.route("/test-mail")
def test_mail_diagnose():
    target = request.args.get("to", HOST_EMAIL)
    subject = "🧪 Test VIP Pass Delivery"
    html = """
    <div style='background: #0f1c3f; color: #ffffff; padding: 25px; border-radius: 14px; font-family: sans-serif; border: 1px solid #d4af37;'>
      <h2 style='color: #d4af37; margin-top: 0;'>✅ Email Service Working!</h2>
      <p style='color: #e2e8f0;'>Your Afterparty backend on Railway is now successfully delivering emails via HTTPS.</p>
    </div>
    """
    ok, message = send_email_direct(target, subject, html)
    return jsonify({
        "status": "SUCCESS" if ok else "FAILED",
        "service_used": "Resend API" if RESEND_API_KEY else ("Gmail SMTP" if SENDER_PASSWORD else "None"),
        "has_resend_api_key": bool(RESEND_API_KEY),
        "resend_key_preview": (RESEND_API_KEY[:6] + "...") if RESEND_API_KEY else None,
        "recipient": target,
        "detail": message
    })

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
        cursor.execute("SELECT name, email, phone, ticket_code FROM guests WHERE id = ?", (guest_id,))
        guest = cursor.fetchone()

        if guest:
            cursor.execute("UPDATE guests SET status = ? WHERE id = ?", (new_status, guest_id))
            conn.commit()
            
            if new_status == "Approved":
                base_url = request.host_url.rstrip("/")
                verify_url = f"{base_url}/verify/{guest_id}"
                pass_url = f"{base_url}/pass/{guest_id}"
                notify_guest_approved(
                    guest["name"], 
                    guest["email"], 
                    verify_url, 
                    pass_url, 
                    guest["ticket_code"]
                )
                flash(f"✅ Approved {guest['name']}! Click '📱 Send WhatsApp Pass' to forward their ticket on WhatsApp.", "success")
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
# 7. RAILWAY PRODUCTION ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting Afterparty Backend on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
