import streamlit as st
import pygsheets
import pandas as pd
from datetime import datetime
from fpdf import FPDF

# --- Konfigurasi Google Sheets ---
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"

# --- Fungsi ambil data dari Google Sheets ---
@st.cache_resource
def load_data_from_gsheet():
    gc = pygsheets.authorize(service_file='credentials.json')  # Pastikan file credentials.json sudah ada
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet_by_title(WORKSHEET_NAME)
    df = ws.get_as_df()
    df['Tanggal Pemesanan'] = pd.to_datetime(df['Tanggal Pemesanan'], errors='coerce')
    return df

# --- Fungsi buat invoice PDF dengan fpdf2 ---
def buat_invoice_pdf(data, output_path="invoice_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Invoice Pemesanan Tiket", ln=True, align="C")
    pdf.ln(10)

    # Info pemesan
    nama = data[0]['Nama Pemesan']
    tanggal = data[0]['Tanggal Pemesanan']
    if pd.isna(tanggal):
        tanggal_str = "-"
    else:
        tanggal_str = tanggal.strftime("%d-%m-%Y")

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Nama Pemesan: {nama}", ln=True)
    pdf.cell(0, 10, f"Tanggal Pemesanan: {tanggal_str}", ln=True)
    pdf.ln(5)

    # Header tabel
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Item", border=1)
    pdf.cell(40, 10, "Harga (Rp)", border=1, align="R")
    pdf.ln()

    # Isi tabel
    pdf.set_font("Arial", size=12)
    total = 0
    for item in data:
        nama_item = item.get('Item', '-')
        harga_str = item.get('Harga', '0')
        try:
            harga = float(harga_str)
        except:
            harga = 0
        total += harga

        pdf.cell(100, 10, nama_item, border=1)
        pdf.cell(40, 10, f"{harga:,.2f}", border=1, align="R")
        pdf.ln()

    # Total
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Total", border=1)
    pdf.cell(40, 10, f"{total:,.2f}", border=1, align="R")
    pdf.ln(20)

    pdf.cell(0, 10, "Terima kasih telah melakukan pemesanan.", ln=True, align="C")

    pdf.output(output_path)
    return output_path

# --- Mulai UI Streamlit ---
st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice dari Data Google Sheets")

# Load data
df = load_data_from_gsheet()

# Filter UI di sidebar
st.sidebar.header("Filter Data")
tanggal_filter = st.sidebar.date_input("Tanggal Pemesanan", value=datetime.today())
nama_filter = st.sidebar.text_input("Nama Pemesan")

# Filter dataframe
filtered_df = df[
    (df['Tanggal Pemesanan'].dt.date == tanggal_filter) &
    (df['Nama Pemesan'].str.contains(nama_filter, case=False, na=False))
]

if filtered_df.empty:
    st.warning("Tidak ada data yang cocok dengan filter.")
    st.stop()

st.subheader("📋 Data yang Ditemukan")
st.dataframe(filtered_df)

# Pilih baris yang akan dibuat invoice
selected_rows = st.multiselect(
    "Pilih baris untuk buat invoice:",
    filtered_df.index.tolist(),
    format_func=lambda x: f"{filtered_df.loc[x, 'Nama Pemesan']} | {filtered_df.loc[x, 'Item']}"
)

if selected_rows:
    data_selected = filtered_df.loc[selected_rows].to_dict(orient='records')

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(data_selected)
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="💾 Unduh Invoice PDF",
                data=f,
                file_name="invoice.pdf",
                mime="application/pdf"
            )

    # Opsi kirim email (opsional)
    email_pemesan = st.text_input("Masukkan email untuk kirim invoice (opsional)")
    if email_pemesan and st.button("📧 Kirim Invoice via Email"):
        import yagmail
        try:
            yag = yagmail.SMTP("emailanda@gmail.com", oauth2_file="oauth2_creds.json")
            yag.send(
                to=email_pemesan,
                subject="Invoice Pemesanan Tiket",
                contents="Berikut kami lampirkan invoice pemesanan Anda.",
                attachments=pdf_path
            )
            st.success("✅ Invoice berhasil dikirim!")
        except Exception as e:
            st.error(f"❌ Gagal mengirim email: {e}")
