import streamlit as st
import pygsheets
import pandas as pd
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

# --- Konfigurasi GSheet ---
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"

# --- Fungsi ambil data dari GSheet ---
@st.cache_resource
def load_data_from_gsheet():
    gc = pygsheets.authorize(service_file='credentials.json')
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet_by_title(WORKSHEET_NAME)
    df = ws.get_as_df()
    df['Tanggal Pemesanan'] = pd.to_datetime(df['Tanggal Pemesanan'], errors='coerce')
    return df

# --- Fungsi buat invoice PDF ---
def buat_invoice_pdf(data, output_path="invoice_output.pdf"):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template("invoice_template.html")
    nama = data[0]['Nama Pemesan']
    tanggal = data[0]['Tanggal Pemesanan']
    total = sum(float(item['Harga']) for item in data)
    html_out = template.render(nama=nama, tanggal=tanggal.strftime("%d-%m-%Y"), items=data, total=total)
    HTML(string=html_out).write_pdf(output_path)
    return output_path

# --- Mulai UI Streamlit ---
st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice dari Data Google Sheets")

df = load_data_from_gsheet()

# --- Filter UI ---
st.sidebar.header("Filter")
tanggal_filter = st.sidebar.date_input("Tanggal Pemesanan", datetime.today())
nama_filter = st.sidebar.text_input("Nama Pemesan")

filtered_df = df[
    (df['Tanggal Pemesanan'].dt.date == tanggal_filter) &
    (df['Nama Pemesan'].str.contains(nama_filter, case=False, na=False))
]

if filtered_df.empty:
    st.warning("Tidak ada data yang cocok.")
    st.stop()

st.subheader("📋 Data yang Ditemukan")
st.dataframe(filtered_df)

selected_rows = st.multiselect(
    "Pilih baris yang akan dibuatkan invoice:",
    filtered_df.index.tolist(),
    format_func=lambda x: f"{filtered_df.loc[x, 'Nama Pemesan']} | {filtered_df.loc[x, 'Item']}"
)

if selected_rows:
    data_selected = filtered_df.loc[selected_rows].to_dict(orient='records')

    if st.button("📄 Buat Invoice PDF"):
        pdf_path = buat_invoice_pdf(data_selected)
        with open(pdf_path, "rb") as f:
            st.download_button("💾 Unduh Invoice", f, file_name="invoice.pdf", mime="application/pdf")

        # Optional kirim email
        email_pemesan = st.text_input("Masukkan email untuk kirim invoice (opsional)")
        if st.button("📧 Kirim Invoice via Email"):
            import yagmail
            try:
                yag = yagmail.SMTP("emailanda@gmail.com", oauth2_file="oauth2_creds.json")
                yag.send(to=email_pemesan, subject="Invoice Pemesanan", contents="Berikut kami lampirkan invoice Anda.", attachments=pdf_path)
                st.success("✅ Invoice berhasil dikirim!")
            except Exception as e:
                st.error(f"❌ Gagal mengirim email: {e}")
print("Invoice app loaded")
