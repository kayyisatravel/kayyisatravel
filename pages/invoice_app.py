import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Konfigurasi ===
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"

# === Koneksi GSheet via secrets ===
def connect_to_gsheet(SHEET_ID, worksheet_name="Data"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(worksheet_name)
    return worksheet

# === Ambil data dan olah ===
@st.cache_data
def load_data():
    ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
    df = pd.DataFrame(ws.get_all_records())
    st.write("📌 Kolom ditemukan:")

    if "Tgl Pemesanan" in df.columns:
        df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce")
    else:
        st.error("❌ Kolom 'Tgl Pemesanan' tidak ditemukan.")
        st.stop()
    return df

# === Fungsi PDF ===
def buat_invoice_pdf(data, nama, tanggal, output_path="invoice_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "INVOICE PEMESANAN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
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
        pdf.cell(80, 10, str(row['Tgl Pemesanan']), 1)
        harga_str = str(row['Harga Jual'])
        harga_clean = harga_str.replace('Rp', '').replace('.', '').replace(',', '').strip()
        try:
            harga = float(harga_clean)
        except ValueError:
            harga = 0
        total += harga
        pdf.cell(40, 10, f"Rp {harga:,.0f}", 1)
        pdf.ln()

    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 10, "Total", 1)
    pdf.cell(40, 10, f"Rp {total:,.0f}", 1)
    pdf.output(output_path)
    return output_path

# === UI Streamlit ===
st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice dari Google Sheets")

df = load_data()

# === Filter UI ===
st.sidebar.header("Filter Data")
tanggal_range = st.sidebar.date_input("Rentang Tanggal", [datetime.today(), datetime.today()])
nama_filter = st.sidebar.text_input("Cari Nama Pemesan")

# === Filter data ===
filtered_df = df[
    (df["Tgl Pemesanan"].dt.date >= tanggal_range[0]) &
    (df["Tgl Pemesanan"].dt.date <= tanggal_range[1])
]

if nama_filter:
    filtered_df = filtered_df[filtered_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]

if filtered_df.empty:
    st.warning("❌ Tidak ada data yang cocok.")
    st.stop()

# === Editor dengan checkbox ===
st.subheader("✅ Pilih Data untuk Invoice")
editable_df = filtered_df.copy()
editable_df["Pilih"] = False

selected_df = st.data_editor(
    editable_df,
    use_container_width=True,
    num_rows="fixed",
    disabled=[col for col in editable_df.columns if col != "Pilih"],
    column_config={
        "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang untuk buat invoice")
    }
)

selected_data = selected_df[selected_df["Pilih"] == True]

# === Buat PDF ===
if not selected_data.empty:
    records = selected_data.to_dict(orient="records")
    nama = selected_data["Nama Pemesan"].iloc[0]
    tanggal = selected_data["Tgl Pemesanan"].iloc[0]

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(records, nama, tanggal)
        with open(pdf_path, "rb") as f:
            st.download_button("💾 Unduh Invoice", f, file_name="invoice.pdf", mime="application/pdf")

    email = st.text_input("Email (opsional) untuk kirim invoice")
    if st.button("📧 Kirim Email"):
        try:
            import yagmail
            yag = yagmail.SMTP(user="emailanda@gmail.com", oauth2_file="oauth2_creds.json")
            yag.send(
                to=email,
                subject="Invoice Pemesanan",
                contents="Berikut invoice pemesanan Anda",
                attachments=pdf_path
            )
            st.success("✅ Email berhasil dikirim.")
        except Exception as e:
            st.error(f"❌ Gagal kirim email: {e}")
