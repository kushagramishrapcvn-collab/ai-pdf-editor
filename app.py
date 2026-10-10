import streamlit as st
import sqlite3
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd

# ==========================================
# 1. CONFIGURATION
# ==========================================
HOST_EMAIL = "kushagramishra.pcvn@gmail.com"
ADMIN_PASSWORD = "afterpartyadmin"  # Change this to your preferred admin password

# Optional SMTP Settings for automated emails (Gmail App Password)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = HOST_EMAIL
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "")  # Set in secrets or paste 16-char App Password

DB_PATH = "afterparty.db"

# ==========================================
# 2. DATABASE & DUPLICATE CHECKS
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()

def check_duplicate(phone, email):
    clean_phone = re.sub(r"\D", "", phone)
    clean_email = email.strip().lower()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT phone, email FROM registrations")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        existing_phone = re.sub(r"\D", "", row["phone"])
        existing_email = row["email"].strip().lower()

        if existing_email == clean_email:
            return True, f"This Gmail ID ({clean_email}) is already registered."
        if existing_phone == clean_phone and clean_phone != "":
            return True, f"This Mobile Number ({clean_phone}) is already registered."

    return False, ""

def add_registration(name, phone, email):
    conn = get_db()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO registrations (timestamp, name, phone, email, status)
        VALUES (?, ?, ?, ?, 'Pending')
    """, (name.strip(), phone.strip(), email.strip().lower(), timestamp))
    conn.commit()
    conn.close()

def update_status(reg_id, new_status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE registrations SET status = ? WHERE id = ?", (new_status, reg_id))
    conn.commit()
    conn.close()

def get_all_records():
    conn = get_db()
    df = pd.read_sql_query("SELECT id, timestamp, name, phone, email, status FROM registrations ORDER BY id DESC", conn)
    conn.close()
    return df

# ==========================================
# 3. EMAIL NOTIFICATIONS
# ==========================================
def send_email(to_email, subject, html_body):
    if not SENDER_PASSWORD:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return False

def notify_host(name, phone, email):
    subject = f"🎉 New Registration: {name}"
    html = f"""
    <h3>New Afterparty Registration</h3>
    <ul>
        <li><b>Name:</b> {name}</li>
        <li><b>Mobile:</b> {phone}</li>
        <li><b>Gmail ID:</b> {email}</li>
        <li><b>Status:</b> Pending Approval</li>
    </ul>
    <p>Log in to your Admin Dashboard to review and approve.</p>
    """
    send_email(HOST_EMAIL, subject, html)

def notify_guest_approval(name, guest_email):
    subject = "🎉 You're on the Afterparty Guestlist!"
    html = f"""
    <h2>Entry Approved!</h2>
    <p>Hi <b>{name}</b>,</p>
    <p>Your registration for the afterparty has been officially <b>Approved</b>.</p>
    <p>Please carry a valid ID matching: <b>{name}</b></p>
    <p>See you at the party!</p>
    """
    send_email(guest_email, subject, html)

# ==========================================
# 4. USER INTERFACE
# ==========================================
st.set_page_config(page_title="Afterparty Registration & Admin", page_icon="🎉", layout="wide")

page = st.sidebar.radio("View", ["Guest Registration", "Host Admin Dashboard"])

# --- GUEST REGISTRATION VIEW ---
if page == "Guest Registration":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎉 Afterparty Registration")
        st.caption("Official guestlist portal. Strictly 1 registration allowed per person.")

        with st.form("guest_form", clear_on_submit=True):
            name = st.text_input("Name (As per your ID) *", placeholder="e.g. Alex Johnson")
            phone = st.text_input("Mobile Number *", placeholder="e.g. 9876543210")
            email = st.text_input("Gmail ID *", placeholder="e.g. alex@gmail.com")

            submitted = st.form_submit_button("Register", use_container_width=True)

            if submitted:
                clean_phone = re.sub(r"\D", "", phone)
                clean_email = email.strip().lower()

                if len(name.strip()) < 2:
                    st.error("Please enter a valid legal name as shown on your ID.")
                elif len(clean_phone) < 10 or len(clean_phone) > 15:
                    st.error("Please enter a valid 10-15 digit mobile number.")
                elif not clean_email.endswith("@gmail.com"):
                    st.error("Please enter a valid Gmail ID ending in @gmail.com.")
                else:
                    # Strict duplicate check
                    is_dup, reason = check_duplicate(clean_phone, clean_email)
                    if is_dup:
                        st.error(f"🚫 **Request Blocked:** {reason} You cannot submit more than once.")
                    else:
                        add_registration(name, phone, clean_email)
                        notify_host(name, phone, clean_email)
                        st.success("✅ **Registration Submitted!**")
                        st.info("The host has been notified. Your pass will be emailed to your Gmail once approved.")

# --- HOST ADMIN DASHBOARD ---
elif page == "Host Admin Dashboard":
    st.title("🔒 Host Approval Dashboard")

    pwd = st.sidebar.text_input("Admin Password", type="password")

    if pwd != ADMIN_PASSWORD:
        st.warning("Enter the host admin password in the sidebar to view records.")
    else:
        df = get_all_records()

        # Scorecards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Registered", len(df))
        c2.metric("Approved", len(df[df["status"] == "Approved"]))
        c3.metric("Pending Review", len(df[df["status"] == "Pending"]))
        c4.metric("Rejected", len(df[df["status"] == "Rejected"]))

        st.divider()

        # Approval cards
        st.subheader("Manage Pending Requests")
        pending_records = df[df["status"] == "Pending"]

        if pending_records.empty:
            st.info("No pending requests to review.")
        else:
            for _, row in pending_records.iterrows():
                with st.expander(f"📌 {row['name']} — {row['phone']} | {row['email']}"):
                    col_info, col_app, col_rej = st.columns([2, 1, 1])
                    with col_info:
                        st.write(f"**Submitted:** {row['timestamp']}")
                        st.write(f"**Name (ID):** {row['name']}")
                        st.write(f"**Mobile:** {row['phone']}")
                        st.write(f"**Gmail:** {row['email']}")
                    with col_app:
                        if st.button("✅ Approve", key=f"app_{row['id']}", use_container_width=True):
                            update_status(row["id"], "Approved")
                            notify_guest_approval(row["name"], row["email"])
                            st.success(f"Approved {row['name']}!")
                            st.rerun()
                    with col_rej:
                        if st.button("❌ Reject", key=f"rej_{row['id']}", use_container_width=True):
                            update_status(row["id"], "Rejected")
                            st.warning(f"Rejected {row['name']}.")
                            st.rerun()

        st.divider()
        st.subheader("Complete Database")
        st.dataframe(df, use_container_width=True)

        # Download Database
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Database as CSV",
            data=csv_data,
            file_name=f"afterparty_records_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
