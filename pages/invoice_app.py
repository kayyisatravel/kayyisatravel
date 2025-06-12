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
    Semua teks dalam tabel diratakan tengah.
    Kolom "No Invoice", "Laba", "% Laba", dan "Pemesan" tidak ditampilkan dalam tabel.
    No Invoice unik otomatis dibuat dan dicetak di bagian detail.
    Kolom "Service Fee" (Rp 20.000) ditambahkan.
    Kolom "Total Harga" berisi harga jual dari GSheets.
    Kolom "Harga" adalah "Total Harga" dikurangi "Service Fee".
    Baris penjumlahan total di bagian bawah dihapus.

    Args:
        data (list of dict): Data yang akan ditampilkan dalam tabel invoice.
                             Setiap dict merepresentasikan baris data.
        nama_pemesan (str): Nama pemesan untuk invoice (akan diabaikan karena sudah di-hardcode).
        tanggal_invoice (date): Tanggal pembuatan invoice.
        output_path (str): Path untuk menyimpan file PDF.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Generate No Invoice unik 12 digit: ddmmyyhhmmss (tanggal bulan tahun jam menit detik)
    # Gunakan waktu saat ini di Indonesia (WIB)
    unique_invoice_no = datetime.now().strftime("%d%m%y%H%M%S")
    pdf_filename = f"INV_{unique_invoice_no}.pdf"
    pdf.output(pdf_filename) # Menggunakan nama file yang baru dibuat
    print(f"Invoice berhasil dibuat: {pdf_filename}")

    # --- Header Invoice ---
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "INVOICE PEMESANAN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    # Nama Pemesan di-hardcode menjadi PT ENDO Indonesia
    pdf.cell(0, 7, "Nama Pemesan: PT ENDO Indonesia", ln=True) 
    pdf.cell(0, 7, f"Tanggal Invoice: {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(0, 7, f"No. Invoice: {unique_invoice_no}", ln=True)
    pdf.ln(10)

    # --- Persiapan Kolom ---
    kolom_prioritas = [
        "Tgl Pemesanan",
        "Tgl Berangkat",
        "Kode Booking",
        "No Penerbangan / Nama Hotel / Kereta",
        "Durasi",
        "Nama Customer",
        "Rute/Kota",
        "Harga Jual", # Ini sekarang akan menjadi "Harga" setelah perhitungan
        "Tax & Service", # Akan di-mapping ke "Service Fee"
        "Total Harga",   # Ini akan menjadi "Total Harga" dari GSheets
        "BF/NBF",
        "Keterangan" 
    ]

    kolom_abaikan = [
        "Pilih", "Harga Beli", "Admin", 
        "Nama Pemesan", "No Invoice", "Laba", 
        "% Laba", "Pemesan"
    ] 
    
    # Perhatikan urutan di kolom_ditampilkan sesuai urutan yang Anda inginkan
    kolom_ditampilkan_final = [
        "No", # Akan ditambahkan secara manual
        "Tgl Pemesanan",
        "Tgl Berangkat",
        "Kode Booking",
        "No Penerbangan / Nama Hotel / Kereta",
        "Durasi",
        "Nama Customer",
        "Rute/Kota",
        "Harga Jual", # Ini yang akan direname jadi "Harga"
        "Tax & Service", # Ini yang akan direname jadi "Service Fee"
        "Total Harga", # Ini yang akan menjadi Total Harga dari GSheets
        "BF/NBF",
        "Keterangan" 
    ]
    # Filter kolom_ditampilkan_final agar hanya menyertakan kolom yang ada di data atau yang baru
    kolom_ditampilkan = [col for col in kolom_ditampilkan_final if col == "No" or col in data[0].keys() or col in ["Tax & Service", "Total Harga"]]
    # Hapus "No" dari kolom_ditampilkan karena akan ditambahkan secara manual di cell pertama
    if "No" in kolom_ditampilkan:
        kolom_ditampilkan.remove("No")


    header_mapping = {
        "Harga Jual": "Harga",    # Header "Harga Jual" di data menjadi "Harga" di PDF
        "Tax & Service": "Service Fee" # Header "Tax & Service" di data menjadi "Service Fee" di PDF
    }

    # --- Perhitungan Lebar Kolom yang Lebih Robust ---
    halaman_lebar_efektif = pdf.w - 2 * pdf.l_margin 
    
    min_lebar_wajib = {
        "No": 8, 
        "Tgl Pemesanan": 22,
        "Tgl Berangkat": 22,
        #"Kode Booking": 18 + 4 + 5,
        "Durasi": 12 + 4 + 2 + 3, # Total penambahan 9 spasi
        "Harga Jual": 22, # Lebar untuk kolom "Harga" (Hasil perhitungan)
        "Tax & Service": 22, # Lebar untuk kolom "Service Fee" (Nilai tetap 20.000)
        "Total Harga": 22, # Lebar untuk kolom "Total Harga" (Harga Jual dari GSheets)
        "BF/NBF": 12,
    }

    kolom_fleksibel = [
        "Nama Customer",
        "Kode Booking",
        "Rute/Kota",
        "No Penerbangan / Nama Hotel / Kereta",
        "Keterangan"
    ]
    
    min_lebar_wajib["Nama Customer"] = max(1, min_lebar_wajib.get("Nama Customer", 40))
    
    lebar_kolom_final = {}
    total_lebar_wajib = 0
    
    for col in ["No"] + kolom_ditampilkan: 
        if col in min_lebar_wajib:
            lebar_kolom_final[col] = min_lebar_wajib[col]
            total_lebar_wajib += min_lebar_wajib[col]
        elif col in kolom_fleksibel:
            lebar_kolom_final[col] = 0
    
    fleksibel_yang_ada = [col for col in kolom_fleksibel if col in kolom_ditampilkan]
    sisa_lebar_untuk_fleksibel = halaman_lebar_efektif - total_lebar_wajib
    
    if fleksibel_yang_ada:
        if sisa_lebar_untuk_fleksibel > 0:
            lebar_per_fleksibel = sisa_lebar_untuk_fleksibel / len(fleksibel_yang_ada)
            for col in fleksibel_yang_ada:
                lebar_kolom_final[col] = lebar_per_fleksibel
        else:
            min_flex_width = 1 
            for col in fleksibel_yang_ada:
                lebar_kolom_final[col] = min_flex_width

    # --- Header Tabel ---
    pdf.set_font("Arial", "B", 8) 
    pdf.set_fill_color(200, 220, 255) 
    
    pdf.cell(max(0.1, lebar_kolom_final["No"]), 8, "No", 1, 0, 'C', 1) 
    for col in kolom_ditampilkan:
        header_text = header_mapping.get(col, col)
        pdf.cell(max(0.1, lebar_kolom_final.get(col, 10)), 8, header_text, 1, 0, 'C', 1) 
    pdf.ln()

    # --- Isi Tabel ---
    pdf.set_font("Arial", "", 8) 
    row_height = 7 
    multi_cell_line_height = row_height / 2.5 

    for idx, row in enumerate(data, 1):
        # --- LOGIKA PERHITUNGAN BARU ---
        # 1. Ambil "Total Harga" dari GSheets (yang ada di kolom "Harga Jual" di data asli)
        total_harga_raw_from_gsheets = row.get("Harga Jual", "0") 
        total_harga_calc = 0.0

        if isinstance(total_harga_raw_from_gsheets, str):
            total_harga_cleaned = total_harga_raw_from_gsheets.replace("Rp", "").replace(".", "").replace(",", "").strip()
            try:
                total_harga_calc = float(total_harga_cleaned)
            except ValueError:
                print(f"Peringatan: Gagal mengonversi 'Total Harga' '{total_harga_raw_from_gsheets}' ke angka. Menggunakan 0.0.")
                total_harga_calc = 0.0
        else:
            total_harga_calc = float(total_harga_raw_from_gsheets)

        # 2. Service Fee tetap 20.000
        service_fee_row = 20000.0 
        
        # 3. Hitung "Harga" baru (Total Harga - Service Fee)
        harga_row_calc = total_harga_calc - service_fee_row 

        # 4. Simpan nilai-nilai yang sudah dihitung ke dalam dictionary 'row'
        #    Pastikan kolom yang sesuai diperbarui.
        row["Total Harga"] = total_harga_calc # Ini adalah harga jual dari GSheets
        row["Tax & Service"] = service_fee_row # Ini adalah Service Fee
        row["Harga Jual"] = harga_row_calc # Ini adalah "Harga" setelah perhitungan

        max_row_height_this_row = row_height
        for col_name in kolom_fleksibel: 
            if col_name in kolom_ditampilkan and col_name in lebar_kolom_final:
                value_for_height_check = str(row.get(col_name, ""))
                col_width = lebar_kolom_final[col_name]
                if col_width > 0: 
                    text_width = pdf.get_string_width(value_for_height_check)
                    num_lines = math.ceil(text_width / col_width) if text_width > 0 else 1
                    if num_lines > 1:
                        required_height_for_multi_cell = num_lines * multi_cell_line_height
                        max_row_height_this_row = max(max_row_height_this_row, required_height_for_multi_cell)

        if pdf.get_y() + max_row_height_this_row + 2 > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font("Arial", "B", 8)
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(max(0.1, lebar_kolom_final["No"]), 8, "No", 1, 0, 'C', 1)
            for col in kolom_ditampilkan:
                header_text = header_mapping.get(col, col)
                pdf.cell(max(0.1, lebar_kolom_final.get(col, 10)), 8, header_text, 1, 0, 'C', 1)
            pdf.ln()
            pdf.set_font("Arial", "", 8)

        # Simpan posisi Y awal untuk baris ini
        initial_y_for_row = pdf.get_y()
        current_x_for_row_start = pdf.get_x() 

        # Cetak kolom "No" (rata tengah)
        pdf.cell(max(0.1, lebar_kolom_final["No"]), max_row_height_this_row, str(idx), 1, 0, 'C')

        # Cetak kolom lainnya
        for col in kolom_ditampilkan:
            col_width = max(0.1, lebar_kolom_final.get(col, 10))
            value_to_print = row.get(col, "") 
            
            # Format harga dan angka
            if col in ["Harga Jual", "Tax & Service", "Total Harga"]: 
                try:
                    value_to_print = f"{float(value_to_print):,.0f}".replace(",", ".")
                except ValueError:
                    value_to_print = "0"
            else:
                value_to_print = str(value_to_print)
            
            # Khusus untuk kolom yang berpotensi panjang (kolom fleksibel), gunakan multi_cell
            if col in kolom_fleksibel:
                num_lines_needed = math.ceil(pdf.get_string_width(value_to_print) / col_width) if col_width > 0 else 1
                effective_text_height = num_lines_needed * multi_cell_line_height
                
                y_offset_for_center = (max_row_height_this_row - effective_text_height) / 2
                
                pdf.set_xy(pdf.get_x(), initial_y_for_row + y_offset_for_center)
                pdf.multi_cell(col_width, multi_cell_line_height, value_to_print, border=0, align='C') 
                
                x_next_col = current_x_for_row_start + lebar_kolom_final["No"] + sum(lebar_kolom_final.get(c,0) for c in kolom_ditampilkan[:kolom_ditampilkan.index(col)+1])
                pdf.set_xy(x_next_col, initial_y_for_row)

            else:
                pdf.set_xy(pdf.get_x(), initial_y_for_row) 
                pdf.cell(col_width, max_row_height_this_row, value_to_print, 1, 0, 'C')
        
        # Gambar border untuk setiap sel di baris ini secara manual setelah semua teks dicetak
        pdf.set_xy(current_x_for_row_start, initial_y_for_row)
        for col_name_for_border in ["No"] + kolom_ditampilkan:
            cell_width_for_border = max(0.1, lebar_kolom_final.get(col_name_for_border, 10))
            pdf.cell(cell_width_for_border, max_row_height_this_row, "", 1, 0, 'C') 
        pdf.ln() 
    
    pdf.output(output_path)
    return output_path
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
