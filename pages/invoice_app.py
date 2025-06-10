import streamlit as st
import gspread
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --- Konstanta ---
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"

# --- Koneksi Google Sheets ---
@st.cache_resource
def connect_to_gsheet(sheet_id: str, worksheet_name: str = "Data"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name)
    return worksheet

# --- Ambil data dari worksheet dan konversi ke DataFrame ---
@st.cache_data
def load_data():
    ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df['Tanggal Pemesanan'] = pd.to_datetime(df['Tgl Pemesanan'], errors='coerce')
    return df

# --- Fungsi buat invoice PDF ---
def buat_invoice_pdf(data, output_path="invoice_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "INVOICE PEMESANAN TIKET", ln=True, align="C")
    pdf.ln(10)

    nama = data[0]['Nama Pemesan']
    tanggal = data[0]['Tanggal Pemesanan']
    tanggal_str = tanggal.strftime('%d-%m-%Y') if not pd.isna(tanggal) else "-"

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Nama Pemesan: {nama}", ln=True)
    pdf.cell(0, 10, f"Tanggal Pemesanan: {tanggal_str}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Item", border=1)
    pdf.cell(40, 10, "Harga (Rp)", border=1, align="R")
    pdf.ln()

    total = 0
    pdf.set_font("Arial", size=12)
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

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "TOTAL", border=1)
    pdf.cell(40, 10, f"{total:,.2f}", border=1, align="R")
    pdf.ln(20)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 10, "Terima kasih atas pemesanannya.", ln=True, align="C")
    pdf.output(output_path)
    return output_path

# --- UI Streamlit ---
st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice")

df = load_data()

# --- Filter UI ---
st.sidebar.header("Filter")
tanggal_filter = st.sidebar.date_input("Tanggal Pemesanan", value=datetime.today())
nama_filter = st.sidebar.text_input("Nama Pemesan")

filtered_df = df[
    (df['Tgl Pemesanan'].dt.date == tanggal_filter) &
    (df['Pemesan'].str.contains(nama_filter, case=False, na=False))
]

if filtered_df.empty:
    st.warning("Tidak ada data yang cocok.")
    st.stop()

st.subheader("📋 Data yang Ditemukan")
st.dataframe(filtered_df)

selected_rows = st.multiselect(
    "Pilih baris untuk invoice:",
    filtered_df.index.tolist(),
    format_func=lambda i: f"{filtered_df.loc[i, 'Item']} - Rp{filtered_df.loc[i, 'Harga']}"
)

if selected_rows:
    data_selected = filtered_df.loc[selected_rows].to_dict(orient='records')

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(data_selected)
        with open(pdf_path, "rb") as f:
            st.download_button(
                "💾 Unduh Invoice",
                data=f,
                file_name="invoice.pdf",
                mime="application/pdf"
            )
