import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials

# === Konfigurasi ===
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"
REQUIRED_COLUMNS = ["Tgl Pemesanan", "Nama Pemesan", "Item", "Harga"]

# === Fungsi koneksi GSheet ===
def connect_to_gsheet(sheet_id: str, worksheet_name: str):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    return worksheet

# === Load data dari Google Sheets dengan validasi dan caching ===
@st.cache_data(ttl=3600)
def load_data():
    start_time = time.time()
    ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
    raw_data = ws.get_all_records()
    df = pd.DataFrame(raw_data)
    
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        st.error(f"❌ Kolom hilang: {', '.join(missing_cols)}")
        st.stop()

    df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce")
    df["Harga"] = pd.to_numeric(df["Harga"], errors="coerce")
    df.dropna(subset=["Tgl Pemesanan", "Nama Pemesan", "Item", "Harga"], inplace=True)

    st.caption(f"📥 Data dimuat dalam {time.time() - start_time:.2f} detik.")
    return df

# === Fungsi PDF ===
def buat_invoice_pdf(data, nama, tanggal, output_path="invoice_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "INVOICE PEMESANAN", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Nama: {nama}", ln=True)
    pdf.cell(0, 10, f"Tanggal: {tanggal.strftime('%d-%m-%Y')}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 10, "Item", 1)
    pdf.cell(40, 10, "Harga", 1)
    pdf.ln()

    total = 0
    pdf.set_font("Arial", "", 12)
    for row in data:
        pdf.cell(80, 10, str(row["Item"]), 1)
        harga = float(row["Harga"])
        total += harga
        pdf.cell(40, 10, f"Rp {harga:,.0f}", 1)
        pdf.ln()

    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 10, "Total", 1)
    pdf.cell(40, 10, f"Rp {total:,.0f}", 1)
    pdf.output(output_path)
    return output_path

# === UI Streamlit ===
st.set_page_config(page_title="Buat Invoice", layout="centered")
st.title("🧾 Buat Invoice dari Google Sheets")

df = load_data()

# === Filter UI ===
st.sidebar.header("Filter Data")
tanggal_range = st.sidebar.date_input("Rentang Tanggal", [datetime.today(), datetime.today()])
nama_filter = st.sidebar.text_input("Cari Nama Pemesan")

# === Filter Data ===
mask = (df["Tgl Pemesanan"].dt.date >= tanggal_range[0]) & (df["Tgl Pemesanan"].dt.date <= tanggal_range[1])
if nama_filter:
    mask &= df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)

filtered_df = df[mask]

if filtered_df.empty:
    st.warning("❌ Tidak ada data yang cocok.")
    st.stop()

st.subheader("📋 Data Ditemukan")
st.dataframe(filtered_df)

# === Pilih baris untuk invoice ===
selected_rows = st.multiselect(
    "Pilih baris untuk invoice:",
    options=filtered_df.index.tolist(),
    format_func=lambda x: f"{filtered_df.loc[x, 'Nama Pemesan']} | {filtered_df.loc[x, 'Item']}"
)

# === Buat PDF Invoice ===
if selected_rows:
    selected_data = filtered_df.loc[selected_rows]
    nama = selected_data["Nama Pemesan"].iloc[0]
    tanggal = selected_data["Tgl Pemesanan"].iloc[0]
    records = selected_data.to_dict(orient="records")

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(records, nama, tanggal)
        with open(pdf_path, "rb") as f:
            st.download_button("💾 Unduh Invoice", f, file_name="invoice.pdf", mime="application/pdf")

    email = st.text_input("Email (opsional) untuk kirim invoice")
    if st.button("📧 Kirim Email"):
        try:
            import yagmail
            yag = yagmail.SMTP(user="emailanda@gmail.com", oauth2_file="oauth2_creds.json")
            yag.send(to=email, subject="Invoice Pemesanan", contents="Berikut invoice Anda", attachments=pdf_path)
            st.success("✅ Email berhasil dikirim.")
        except Exception as e:
            st.error(f"❌ Gagal kirim email: {e}")
