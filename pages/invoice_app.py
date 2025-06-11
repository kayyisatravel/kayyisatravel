import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
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

st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
st.title("🧾 Buat Invoice")

# Tombol Refresh
#if st.button("🔄 Refresh Data"):
    #st.cache_data.clear()

# === Ambil data dan olah ===
@st.cache_data  # Refresh 
def load_data():
    ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
    df = pd.DataFrame(ws.get_all_records())
    st.write("📌 Kolom ditemukan:")

    if "Tgl Pemesanan" in df.columns:
        # Ubah menjadi hanya tanggal
        df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce").dt.date
    else:
        st.error("❌ Kolom 'Tgl Pemesanan' tidak ditemukan.")
        st.stop()
    return df
# Tombol Refresh
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    df = load_data()
#else:
    #df = load_data()
# === Fungsi PDF ===
import math # Untuk pembulatan jika diperlukan

def buat_invoice_pdf(data, nama_pemesan, tanggal_invoice, output_path="invoice_output.pdf"):
    """
    Membuat file PDF invoice dengan lebar kolom dan font yang menyesuaikan ukuran kertas A4 landscape.

    Args:
        data (list of dict): Data yang akan ditampilkan dalam tabel invoice.
                             Setiap dict merepresentasikan baris data.
        nama_pemesan (str): Nama pemesan untuk invoice.
        tanggal_invoice (date): Tanggal pembuatan invoice.
        output_path (str): Path untuk menyimpan file PDF.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # --- Header Invoice ---
    pdf.set_font("Arial", "B", 18) # Judul lebih besar
    pdf.cell(0, 10, "INVOICE PEMESANAN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    pdf.cell(0, 7, f"Nama Pemesan: {nama_pemesan}", ln=True) # Gunakan nama_pemesan dari parameter
    pdf.cell(0, 7, f"Tanggal Invoice: {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True) # Gunakan tanggal_invoice dari parameter
    pdf.ln(10) # Spasi sebelum tabel

    # --- Persiapan Kolom ---
    # Definisikan kolom yang akan ditampilkan dan urutannya
    # Sesuaikan urutan ini jika Anda ingin tampilan berbeda
    kolom_prioritas = [
        "Tgl Pemesanan",
        "Tgl Berangkat",
        "Kode Booking",
        "No Penerbangan / Nama Hotel / Kereta",
        "Durasi",
        "Nama Customer",
        "Rute/Kota",
        "Harga Jual",
        "Laba",
        "BF/NBF",
        "No Invoice",
        "Keterangan",
        "Pemesan" # 'Admin' dan '% Laba' sudah diabaikan di kolom_abaikan
    ]

    kolom_abaikan = ["Pilih", "Harga Beli", "Admin", "% Laba", "Nama Pemesan"] # Nama Pemesan juga bisa diabaikan jika sudah ada di header invoice
    
    # Filter kolom_prioritas berdasarkan kolom yang ada di data
    # (data[0] untuk mengambil keys dari entry pertama sebagai referensi)
    kolom_ditampilkan = [col for col in kolom_prioritas if col in data[0].keys() and col not in kolom_abaikan]

    # --- Perhitungan Lebar Kolom ---
    halaman_lebar_efektif = pdf.w - 2 * pdf.l_margin # Lebar area konten tanpa margin kiri-kanan
    
    # Definisikan lebar untuk kolom tertentu, sisanya akan dibagi rata
    lebar_spesifik = {
        "No": 10, # Kolom nomor urut
        "Tgl Pemesanan": 25,
        "Tgl Berangkat": 25,
        "Kode Booking": 20,
        "Durasi": 15,
        "Harga Jual": 25,
        "Laba": 20,
        "BF/NBF": 15,
        "No Invoice": 20,
        "Pemesan": 25,
        "Nama Customer": 40, # Perkiraan nama cukup panjang
        "Rute/Kota": 35, # Rute/Kota bisa panjang
        "Keterangan": 40 # Keterangan bisa sangat panjang
    }

    lebar_kolom_final = {}
    total_lebar_spesifik = 0
    kolom_sisa = []

    # Hitung total lebar spesifik dan identifikasi kolom yang belum punya lebar spesifik
    for col in ["No"] + kolom_ditampilkan: # 'No' adalah kolom tambahan
        if col in lebar_spesifik:
            lebar_kolom_final[col] = lebar_spesifik[col]
            total_lebar_spesifik += lebar_spesifik[col]
        else:
            kolom_sisa.append(col)
            
    # Distribusikan lebar sisa ke kolom yang belum punya lebar spesifik
    if kolom_sisa:
        lebar_rata_rata_sisa = (halaman_lebar_efektif - total_lebar_spesifik) / len(kolom_sisa)
        for col in kolom_sisa:
            lebar_kolom_final[col] = lebar_rata_rata_sisa
            
    # Pastikan total lebar tidak melebihi lebar efektif halaman (untuk jaga-jaga pembulatan)
    if sum(lebar_kolom_final.values()) > halaman_lebar_efektif:
         # Jika ada kelebihan, kurangi dari kolom yang paling fleksibel (misal, Keterangan)
         # Atau bagi rata ke semua kolom. Untuk simplicity, kita bisa kurangi dari salah satu.
         lebar_kolom_final['Keterangan'] = lebar_kolom_final.get('Keterangan', lebar_rata_rata_sisa) - (sum(lebar_kolom_final.values()) - halaman_lebar_efektif)


    # --- Header Tabel ---
    pdf.set_font("Arial", "B", 8) # Font header tabel lebih kecil agar pas
    pdf.set_fill_color(200, 220, 255) # Warna latar header
    
    pdf.cell(lebar_kolom_final["No"], 8, "No", 1, 0, 'C', 1)
    for col in kolom_ditampilkan:
        pdf.cell(lebar_kolom_final[col], 8, col, 1, 0, 'C', 1) # 'C' untuk center
    pdf.ln()

    # --- Isi Tabel ---
    pdf.set_font("Arial", "", 8) # Font isi tabel lebih kecil
    row_height = 7 # Tinggi baris default

    for idx, row in enumerate(data, 1):
        # Tambahkan page break jika baris berikutnya tidak muat
        if pdf.get_y() + row_height > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font("Arial", "B", 8) # Ulangi header pada halaman baru
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(lebar_kolom_final["No"], 8, "No", 1, 0, 'C', 1)
            for col in kolom_ditampilkan:
                pdf.cell(lebar_kolom_final[col], 8, col, 1, 0, 'C', 1)
            pdf.ln()
            pdf.set_font("Arial", "", 8) # Kembali ke font isi tabel

        start_x = pdf.get_x() # Simpan posisi X awal untuk baris ini
        start_y = pdf.get_y() # Simpan posisi Y awal untuk baris ini
        
        # Kolom "No"
        pdf.cell(lebar_kolom_final["No"], row_height, str(idx), 1, 0, 'C')

        # Isi kolom lainnya
        for col in kolom_ditampilkan:
            current_x = pdf.get_x() # Posisi X sebelum mengisi cell
            current_y = pdf.get_y() # Posisi Y sebelum mengisi cell
            
            value = str(row.get(col, ""))
            
            # Khusus untuk kolom yang berpotensi panjang, gunakan multi_cell
            if col in ["No Penerbangan / Nama Hotel / Kereta", "Keterangan", "Nama Customer", "Rute/Kota"]:
                pdf.multi_cell(lebar_kolom_final[col], row_height / 2, value, border=0, align='L', ln=0)
                # Kembali ke posisi setelah multi_cell untuk kolom berikutnya
                pdf.set_xy(current_x + lebar_kolom_final[col], current_y)
            else:
                # Untuk kolom lain, gunakan cell biasa dan potong jika terlalu panjang
                pdf.cell(lebar_kolom_final[col], row_height, value, 1, 0, 'L') # 'L' untuk Left align
        
        pdf.ln() # Pindah ke baris berikutnya setelah semua kolom diisi

    pdf.output(output_path)
    return output_path

# --- Contoh Penggunaan ---
if __name__ == "__main__":
    # Contoh data dummy yang mirip dengan struktur Anda
    dummy_data = [
        {
            "Tgl Pemesanan": date(2025, 6, 10),
            "Tgl Berangkat": date(2025, 10, 15),
            "Kode Booking": "ABC12345",
            "No Penerbangan / Nama Hotel / Kereta": "Garuda Indonesia GA200 Jakarta",
            "Durasi": "2 jam",
            "Nama Customer": "Budi Pratama Wijaya Santoso",
            "Rute/Kota": "CGK - SUB",
            "Harga Beli": 700000,
            "Harga Jual": 850000,
            "Laba": 150000,
            "BF/NBF": "BF",
            "No Invoice": "INV001",
            "Keterangan": "Penerbangan domestik dengan bagasi 20kg",
            "Pemesan": "Agen A",
            "Admin": "Admin Y",
            "% Laba": "21.43%"
        },
        {
            "Tgl Pemesanan": date(2025, 6, 11),
            "Tgl Berangkat": date(2025, 11, 20),
            "Kode Booking": "HOTEL987",
            "No Penerbangan / Nama Hotel / Kereta": "Puri Indah Hotel & Convention",
            "Durasi": "3 mlm",
            "Nama Customer": "Ayu Lestari Dewi",
            "Rute/Kota": "Lombok Barat",
            "Harga Beli": 335000,
            "Harga Jual": 400000,
            "Laba": 65000,
            "BF/NBF": "NBF",
            "No Invoice": "INV002",
            "Keterangan": "Kamar Standard Room Only, view kolam renang",
            "Pemesan": "Agen B",
            "Admin": "Admin Z",
            "% Laba": "19.4%"
        },
         {
            "Tgl Pemesanan": date(2025, 6, 12),
            "Tgl Berangkat": date(2025, 12, 1),
            "Kode Booking": "KAI12345",
            "No Penerbangan / Nama Hotel / Kereta": "KA Argo Wilis (EKO 7/8A)",
            "Durasi": "8 jam",
            "Nama Customer": "Siti Aminah Purnomo",
            "Rute/Kota": "Bandung - Yogyakarta",
            "Harga Beli": 150000,
            "Harga Jual": 180000,
            "Laba": 30000,
            "BF/NBF": "-",
            "No Invoice": "INV003",
            "Keterangan": "Kursi dekat jendela, gerbong 5",
            "Pemesan": "Agen C",
            "Admin": "Admin X",
            "% Laba": "20.0%"
        },
        {
            "Tgl Pemesanan": date(2025, 6, 12),
            "Tgl Berangkat": date(2025, 12, 1),
            "Kode Booking": "KAI12345",
            "No Penerbangan / Nama Hotel / Kereta": "KA Argo Wilis (EKO 7/8A)",
            "Durasi": "8 jam",
            "Nama Customer": "Siti Aminah Purnomo Kedua Dengan Nama Yang Lebih Panjang Untuk Tes Multi Cell",
            "Rute/Kota": "Bandung - Yogyakarta",
            "Harga Beli": 150000,
            "Harga Jual": 180000,
            "Laba": 30000,
            "BF/NBF": "-",
            "No Invoice": "INV003",
            "Keterangan": "Kursi dekat jendela, gerbong 5, sangat panjang untuk tes multi cell di keterangan juga",
            "Pemesan": "Agen C",
            "Admin": "Admin X",
            "% Laba": "20.0%"
        }
    ]

    # Coba buat PDF
    output_pdf_path = buat_invoice_pdf(dummy_data, "PT Travel Gemilang", date.today(), "invoice_contoh.pdf")
    print(f"Invoice berhasil dibuat: {output_pdf_path}")

# === UI Streamlit ===
#st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
#st.title("🧾 Buat Invoice")

df = load_data()
#st.write("Data contoh Tgl Pemesanan (5 pertama):", df["Tgl Pemesanan"].head())
#st.write("Tipe data kolom Tgl Pemesanan:", df["Tgl Pemesanan"].apply(type).unique())
#st.write("Tanggal filter:", tanggal_range)

# === Filter UI ===
st.sidebar.header("Filter Data")

# Default range: hari ini saja
tanggal_range = st.sidebar.date_input("Rentang Tanggal", [date.today(), date.today()])

# Pastikan tanggal_range adalah list/tuple dua tanggal
if isinstance(tanggal_range, date):
    tanggal_range = [tanggal_range, tanggal_range]
elif len(tanggal_range) == 1:
    tanggal_range = [tanggal_range[0], tanggal_range[0]]

# Pastikan semua elemen tanggal_range adalah datetime.date (bukan datetime.datetime)
tanggal_range = [d if isinstance(d, date) else d.date() for d in tanggal_range]
nama_filter = st.sidebar.text_input("Cari Nama Pemesan")

# Filter data
filtered_df = df[
    (df["Tgl Pemesanan"] >= tanggal_range[0]) &
    (df["Tgl Pemesanan"] <= tanggal_range[1])
]
#st.write("Data setelah filter tanggal:", filtered_df)
if nama_filter:
    filtered_df = filtered_df[filtered_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
# Debug output opsional
#st.write("🛠 Debug: Rentang tanggal", tanggal_range)
#st.write("🛠 Debug: Jumlah data hasil filter", len(filtered_df))
#st.write("🛠 Debug: Data hasil filter", filtered_df.head())
    
if filtered_df.empty:
    st.warning("❌ Tidak ada data yang cocok.")
    st.stop()
# === Editor dengan checkbox dan pilih semua ===
st.subheader("✅ Pilih Data untuk Invoice")

editable_df = filtered_df.copy()
editable_df.insert(0, 'Pilih', False)

#if "editable_df" not in st.session_state:
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
