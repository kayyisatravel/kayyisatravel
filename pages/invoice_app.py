import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io

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
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "INVOICE PEMESANAN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    pdf.cell(0, 10, f"Nama: {nama}", ln=True)
    pdf.cell(0, 10, f"Tanggal: {tanggal.strftime('%d-%m-%Y')}", ln=True)
    pdf.ln(5)

    kolom_abaikan = ["Pilih", "Harga Beli", "Admin", "%Laba", "Nama Pemesan"]
    kolom_ditampilkan = [col for col in data[0].keys() if col not in kolom_abaikan]

    halaman_lebar = 277  # A4 landscape
    jumlah_kolom = len(kolom_ditampilkan) + 1  # +1 untuk No
    lebar_kolom = halaman_lebar / jumlah_kolom

    pdf.set_font("Arial", "B", 10)
    pdf.cell(lebar_kolom, 8, "No", 1)
    for col in kolom_ditampilkan:
        pdf.cell(lebar_kolom, 8, col[:30], 1)
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    for idx, row in enumerate(data, 1):
        pdf.cell(lebar_kolom, 8, str(idx), 1)
        for col in kolom_ditampilkan:
            value = str(row.get(col, ""))[:40]
            pdf.cell(lebar_kolom, 8, value, 1)
        pdf.ln()

    pdf.output(output_path)
    return output_path

# === UI Streamlit ===
st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice")

df = load_data()

# === Filter UI ===
st.sidebar.header("Filter Data")
tanggal_range = st.sidebar.date_input("Rentang Tanggal", [datetime.today(), datetime.today()])
nama_filter = st.sidebar.text_input("Cari Nama Pemesan")

filtered_df = df[
    (df["Tgl Pemesanan"].dt.date >= tanggal_range[0]) &
    (df["Tgl Pemesanan"].dt.date <= tanggal_range[1])
]

if nama_filter:
    filtered_df = filtered_df[filtered_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]

if filtered_df.empty:
    st.warning("❌ Tidak ada data yang cocok.")
    st.stop()

# === Editor dengan checkbox dan pilih semua ===
st.subheader("✅ Pilih Data untuk Invoice")

editable_df = filtered_df.copy()
editable_df.insert(0, 'Pilih', False)

if "editable_df" not in st.session_state:
    st.session_state.editable_df = editable_df

select_all = st.checkbox("Pilih Semua", value=False)
st.session_state.editable_df["Pilih"] = select_all

selected_df = st.data_editor(
    st.session_state.editable_df,
    use_container_width=True,
    num_rows="fixed",
    disabled=[col for col in st.session_state.editable_df.columns if col != "Pilih"],
    column_config={
        "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang untuk buat invoice")
    }
)

st.session_state.editable_df = selected_df
selected_data = selected_df[selected_df['Pilih'] == True]

# === Total Harga ===
def parse_harga(harga_str):
    if pd.isna(harga_str):
        return 0
    s = str(harga_str).replace('Rp', '').replace('.', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0

total_harga = selected_data['Harga Jual'].apply(parse_harga).sum()
st.markdown(f"**Total Harga Jual dari data yang dicentang: Rp {total_harga:,.0f}**")

# === Buat PDF ===
if not selected_data.empty:
    records = selected_data.to_dict(orient="records")
    nama = selected_data["Nama Pemesan"].iloc[0]
    tanggal = selected_data["Tgl Pemesanan"].iloc[0]

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(records, nama, tanggal)
        with open(pdf_path, "rb") as f:
            st.download_button("💾 Unduh Invoice", f, file_name="invoice.pdf", mime="application/pdf")

# === Buat Excel ===
excel_data = selected_data.drop(columns=["Pilih", "Harga Beli", "Admin", "%Laba", "Nama Pemesan"], errors="ignore")
excel_buffer = io.BytesIO()
excel_data.to_excel(excel_buffer, index=False, engine="openpyxl")
excel_buffer.seek(0)

st.download_button(
    "📥 Unduh Excel",
    data=excel_buffer,
    file_name="invoice.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# === Kirim Email ===
email = st.text_input("Email (opsional) untuk kirim invoice")
if st.button("📧 Kirim Email"):
    try:
        import yagmail
        yag = yagmail.SMTP(user="tiketkay98@gmail.com", oauth2_file="oauth2_creds.json")
        yag.send(
            to=email,
            subject="Invoice Pemesanan",
            contents="Berikut invoice pemesanan Anda",
            attachments=pdf_path
        )
        st.success("✅ Email berhasil dikirim.")
    except Exception as e:
        st.error(f"❌ Gagal kirim email: {e}")
