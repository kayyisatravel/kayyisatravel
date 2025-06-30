import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import math # Untuk pembulatan jika diperlukan

# === Konfigurasi ===
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
WORKSHEET_NAME = "Data"
LOGO_PATH = "logo.png" # Ganti dengan path ke file logo Anda, misal "images/logo.png"

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
st.title("🧾 Dashboard Invoice")

# === Ambil data dan olah ===
@st.cache_data # Refresh 
def load_data():
    ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
    df = pd.DataFrame(ws.get_all_records())
    st.write("📌 Kolom ditemukan:")

    if "Tgl Pemesanan" in df.columns:
        df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce").dt.date
        st.write("🔍 Data awal:")
        st.write(df.head())
        
    else:
        st.error("❌ Kolom 'Tgl Pemesanan' tidak ditemukan.")
        st.stop()
    return df

# Tombol Refresh
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    df = load_data()
else:
    df = load_data()

## Fungsi `buat_invoice_pdf` (Direvisi)

# === Fungsi PDF ===
def buat_invoice_pdf(data, nama_pemesan, tanggal_invoice, unique_invoice_no, output_pdf_filename, logo_path=None):
    """
    Membuat file PDF invoice dengan lebar kolom dan font yang menyesuaikan ukuran kertas A4 landscape.
    Semua teks dalam tabel diratakan tengah.
    Kolom "No Invoice", "Laba", "% Laba", dan "Pemesan" tidak ditampilkan dalam tabel.
    No Invoice unik otomatis dibuat dan dicetak di bagian detail.
    Kolom "Service Fee" (Rp 20.000) ditambahkan.
    Kolom "Total Harga" berisi harga jual dari GSheets.
    Kolom "Harga" adalah "Total Harga" dikurangi "Service Fee".
    Baris penjumlahan total di bagian bawah dihapus.
    Lebar kolom disesuaikan otomatis agar teks tidak wrap.

    Args:
        data (list of dict): Data yang akan ditampilkan dalam tabel invoice.
                             Setiap dict merepresentasikan baris data.
        nama_pemesan (str): Nama pemesan untuk invoice (akan diabaikan karena sudah di-hardcode).
        tanggal_invoice (date): Tanggal pembuatan invoice.
        unique_invoice_no (str): Nomor invoice unik yang sudah digenerate di luar fungsi.
        output_pdf_filename (str): Nama file PDF lengkap untuk disimpan.
        logo_path (str, optional): Path ke file logo. Jika None, logo tidak ditampilkan.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # --- Header Invoice ---
    # Tambahkan logo jika path disediakan dan file ada
    if logo_path and st.file_manager.exists(logo_path): # Menggunakan st.file_manager.exists untuk deployment
        try:
            pdf.image(logo_path, x=10, y=10, w=30) # Sesuaikan x, y, w sesuai kebutuhan
        except Exception as e:
            st.warning(f"Tidak dapat memuat logo: {e}")
            pass # Lanjutkan tanpa logo jika ada error

    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "Lampiran Invoice", ln=True, align="C") # Judul baru "Lampiran Invoice"
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    pdf.cell(0, 7, "Nama Pemesan: PT ENDO Indonesia", ln=True) 
    pdf.cell(0, 7, f"Tanggal Invoice: {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(0, 7, f"No. Invoice: {unique_invoice_no}", ln=True)
    pdf.ln(10)

    # --- Persiapan Kolom ---
    kolom_ditampilkan_final = [
        "No",
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
    kolom_ditampilkan_pdf = [col for col in kolom_ditampilkan_final if col == "No" or (data and col in data[0].keys()) or col in ["Tax & Service", "Total Harga"]]
    if "No" in kolom_ditampilkan_pdf:
        kolom_ditampilkan_pdf.remove("No") # 'No' akan ditambahkan manual

    header_mapping = {
        "Harga Jual": "Harga",
        "Tax & Service": "Service Fee"
    }

    # --- Perhitungan Lebar Kolom Otomatis (Tanpa Wrap Text) ---
    pdf.set_font("Arial", "B", 8) # Gunakan font header untuk mengukur lebar header
    col_widths = {"No": 8} # Lebar tetap untuk kolom 'No'

    # Tentukan lebar minimum untuk kolom wajib
    min_widths = {
        "Tgl Pemesanan": 22,
        "Tgl Berangkat": 22,
        "Durasi": 12,
        "Harga Jual": 22, # Cukup untuk angka Rp x.xxx.xxx
        "Tax & Service": 22,
        "Total Harga": 22,
        "BF/NBF": 12,
        "Kode Booking": 25, # Beri lebar min agar tidak terlalu sempit
        "Nama Customer": 40,
        "Rute/Kota": 30,
        "No Penerbangan / Nama Hotel / Kereta": 50,
        "Keterangan": 40,
    }

    # Hitung lebar maksimum berdasarkan header dan data
    for col in kolom_ditampilkan_pdf:
        header_text = header_mapping.get(col, col)
        max_content_width = pdf.get_string_width(header_text) + 2 # +2 untuk padding
        
        # Hitung lebar berdasarkan data
        pdf.set_font("Arial", "", 8) # Gunakan font data untuk mengukur data
        for row in data:
            value = str(row.get(col, ""))
            # Khusus untuk kolom harga, format dulu sebelum diukur
            if col in ["Harga Jual", "Tax & Service", "Total Harga"]:
                try:
                    value = f"{float(value):,.0f}".replace(",", ".")
                except ValueError:
                    value = "0"
            max_content_width = max(max_content_width, pdf.get_string_width(value) + 2)
        
        # Pastikan tidak kurang dari lebar minimum yang ditentukan
        col_widths[col] = max(min_widths.get(col, 0), max_content_width)
    
    # Normalisasi lebar agar totalnya pas dengan halaman efektif
    total_lebar_kolom = sum(col_widths.values())
    halaman_lebar_efektif = pdf.w - 2 * pdf.l_margin
    
    # Jika total lebar kolom lebih dari halaman efektif, skalakan
    if total_lebar_kolom > halaman_lebar_efektif:
        skala_faktor = halaman_lebar_efektif / total_lebar_kolom
        for col in col_widths:
            col_widths[col] *= skala_faktor
    
    # Jika kurang, distribusikan sisanya ke kolom yang tidak punya min_width tinggi
    elif total_lebar_kolom < halaman_lebar_efektif:
        sisa_lebar = halaman_lebar_efektif - total_lebar_kolom
        
        # Tentukan kolom yang bisa diperlebar (misal, yang tidak memiliki min_width terlalu tinggi atau yang fleksibel)
        kolom_yang_bisa_diperlebar = [col for col in col_widths if col not in ["No", "Tgl Pemesanan", "Tgl Berangkat", "Durasi", "BF/NBF", "Harga Jual", "Tax & Service", "Total Harga"]]
        
        if kolom_yang_bisa_diperlebar:
            lebar_per_kolom_tambahan = sisa_lebar / len(kolom_yang_bisa_diperlebar)
            for col in kolom_yang_bisa_diperlebar:
                col_widths[col] += lebar_per_kolom_tambahan
        else: # Jika tidak ada kolom fleksibel, distribusikan secara proporsional
            proporsional_faktor = halaman_lebar_efektif / total_lebar_kolom
            for col in col_widths:
                col_widths[col] *= proporsional_faktor


    # --- Header Tabel ---
    pdf.set_font("Arial", "B", 8) 
    pdf.set_fill_color(200, 220, 255) 
    
    pdf.cell(col_widths["No"], 8, "No", 1, 0, 'C', 1) 
    for col in kolom_ditampilkan_pdf:
        header_text = header_mapping.get(col, col)
        pdf.cell(col_widths[col], 8, header_text, 1, 0, 'C', 1) 
    pdf.ln()

    # --- Isi Tabel ---
    pdf.set_font("Arial", "", 8) 
    row_height = 7 

    for idx, row in enumerate(data, 1):
        # Perhitungan harga seperti sebelumnya
        total_harga_raw_from_gsheets = row.get("Harga Jual", "0") 
        total_harga_calc = 0.0

        if isinstance(total_harga_raw_from_gsheets, (int, float)):
            total_harga_calc = float(total_harga_raw_from_gsheets)
        elif isinstance(total_harga_raw_from_gsheets, str):
            total_harga_cleaned = total_harga_raw_from_gsheets.replace("Rp", "").replace(".", "").replace(",", "").strip()
            try:
                total_harga_calc = float(total_harga_cleaned)
            except ValueError:
                total_harga_calc = 0.0
        else:
            total_harga_calc = 0.0

        service_fee_row = 20000.0 
        harga_row_calc = total_harga_calc - service_fee_row 

        row["Total Harga"] = total_harga_calc
        row["Tax & Service"] = service_fee_row
        row["Harga Jual"] = harga_row_calc

        # Cek apakah perlu halaman baru
        if pdf.get_y() + row_height + 2 > pdf.page_break_trigger:
            pdf.add_page()
            # Ulangi header tabel di halaman baru
            pdf.set_font("Arial", "B", 8)
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(col_widths["No"], 8, "No", 1, 0, 'C', 1)
            for col in kolom_ditampilkan_pdf:
                header_text = header_mapping.get(col, col)
                pdf.cell(col_widths[col], 8, header_text, 1, 0, 'C', 1)
            pdf.ln()
            pdf.set_font("Arial", "", 8)

        # Simpan posisi Y awal untuk baris ini
        initial_y_for_row = pdf.get_y()
        current_x_for_row_start = pdf.get_x() 

        # Cetak kolom "No" (rata tengah)
        pdf.cell(col_widths["No"], row_height, str(idx), 1, 0, 'C')

        # Cetak kolom lainnya
        for col in kolom_ditampilkan_pdf:
            col_width = col_widths[col]
            value_to_print = row.get(col, "") 
            
            if col in ["Harga Jual", "Tax & Service", "Total Harga"]: 
                try:
                    value_to_print = f"{float(value_to_print):,.0f}".replace(",", ".") 
                except ValueError:
                    value_to_print = "0"
            else:
                value_to_print = str(value_to_print)
            
            # Karena kita sudah memastikan lebar kolom cukup, kita bisa gunakan cell biasa.
            # Multi_cell tidak diperlukan lagi karena wrap text sudah dihindari.
            pdf.cell(col_width, row_height, value_to_print, 1, 0, 'C') # Semua rata tengah

        pdf.ln() # Pindah ke baris berikutnya

    # --- PENTING: PANGGIL pdf.output() DI SINI, DI BAGIAN PALING AKHIR FUNGSI ---
    pdf.output(output_pdf_filename) 

    return output_pdf_filename
# === UI Streamlit ===
#st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
#st.title("🧾 Buat Invoice")

df = load_data()
#st.write("Data contoh Tgl Pemesanan (5 pertama):", df["Tgl Pemesanan"].head())
#st.write("Tipe data kolom Tgl Pemesanan:", df["Tgl Pemesanan"].apply(type).unique())
#st.write("Tanggal filter:", tanggal_range)

# ... (kode UI Streamlit di bagian atas) ...

# === Filter UI ===
st.sidebar.header("Filter Data")

tanggal_range = st.sidebar.date_input("Rentang Tanggal", [date.today(), date.today()])
st.write("Tanggal filter:", tanggal_range)
st.write(df["Tgl Pemesanan"].unique())


if isinstance(tanggal_range, date):
    tanggal_range = [tanggal_range, tanggal_range]
elif len(tanggal_range) == 1:
    tanggal_range = [tanggal_range[0], tanggal_range[0]]

tanggal_range = [d if isinstance(d, date) else d.date() for d in tanggal_range]
nama_filter = st.sidebar.text_input("Cari Nama Pemesan")

filtered_df = df[
    (df["Tgl Pemesanan"] >= tanggal_range[0]) &
    (df["Tgl Pemesanan"] <= tanggal_range[1])
]
st.write("📊 Data setelah filter tanggal:", len(filtered_df))
st.write(filtered_df.head())
if nama_filter:
    filtered_df = filtered_df[filtered_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
    
if filtered_df.empty:
    st.warning("❌ Tidak ada data yang cocok.")
    st.write("🔍 Cek hasil filter akhir:")
    st.write(filtered_df)
else: 
    # === Editor dengan checkbox dan pilih semua ===
    st.subheader("✅ Pilih Data untuk Invoice")
    st.write("Nama filter:", nama_filter)
    st.write("Nama unik di data:", df["Nama Pemesan"].unique())
    st.write("Jumlah data awal:", len(df))
    st.write("Jumlah data setelah filter tanggal:", len(filtered_df))
    if nama_filter:
        st.write("Jumlah data setelah filter nama:", len(filtered_df))

    editable_df = filtered_df.copy()
    editable_df.insert(0, 'Pilih', False)

    if "editable_df" not in st.session_state:
        st.session_state.editable_df = editable_df
    
    # Perbarui editable_df di session_state jika filtered_df berubah
    # (misal setelah filter baru diterapkan)
    if not st.session_state.editable_df.equals(editable_df):
        st.session_state.editable_df = editable_df.copy()
        # Reset 'Pilih' status saat data filter berubah
        st.session_state.editable_df['Pilih'] = False 


    select_all = st.checkbox("Pilih Semua", value=False, key="select_all_checkbox")
    if select_all:
        st.session_state.editable_df["Pilih"] = True
    else:
        # Hanya reset jika sebelumnya semua terpilih dan checkbox di-uncheck
        if st.session_state.editable_df["Pilih"].all() and st.session_state.get("last_select_all_state", False):
            st.session_state.editable_df["Pilih"] = False
    st.session_state.last_select_all_state = select_all # Simpan state checkbox

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

    total_harga_jual = selected_data['Harga Jual'].apply(parse_harga).sum()
    total_laba = selected_data['Laba'].apply(parse_harga).sum()
    st.markdown(f"**Total Harga Jual yang dipilih: Rp {total_harga_jual:,.0f}**")
    st.markdown(f"**Total Laba yang dipilih: Rp {total_laba:,.0f}**")

    # === Tombol Aksi ===
    col_pdf, col_excel, col_email = st.columns(3)

    # Inisialisasi nomor invoice unik di session state jika belum ada
    if 'current_unique_invoice_no' not in st.session_state:
        st.session_state.current_unique_invoice_no = datetime.now().strftime("%d%m%y%H%M%S")

    # Generate nama file untuk PDF dan Excel
    current_pdf_filename = f"INV_{st.session_state.current_unique_invoice_no}.pdf"
    current_excel_filename = f"INV_{st.session_state.current_unique_invoice_no}.xlsx"

    # Simpan nama file terakhir yang dibuat di session state untuk pengiriman email
    if 'last_generated_pdf_path' not in st.session_state:
        st.session_state.last_generated_pdf_path = None


    with col_pdf:
        if st.button("📄 Buat Invoice PDF"):
            if not selected_data.empty:
                records = selected_data.to_dict(orient="records")
                nama = selected_data["Nama Pemesan"].iloc[0] if not selected_data["Nama Pemesan"].empty else "Pelanggan"
                tanggal = selected_data["Tgl Pemesanan"].iloc[0]

                # Update nomor invoice unik setiap kali tombol PDF diklik
                st.session_state.current_unique_invoice_no = datetime.now().strftime("%d%m%y%H%M%S")
                current_pdf_filename = f"INV_{st.session_state.current_unique_invoice_no}.pdf"
                current_excel_filename = f"INV_{st.session_state.current_unique_invoice_no}.xlsx"

                pdf_path_generated = buat_invoice_pdf(records, nama, tanggal, st.session_state.current_unique_invoice_no, current_pdf_filename) 
                
                with open(pdf_path_generated, "rb") as f:
                    st.download_button(
                        "💾 Unduh Invoice PDF", 
                        f, 
                        file_name=current_pdf_filename, 
                        mime="application/pdf"
                    )
                st.success(f"✅ Invoice PDF berhasil dibuat: {current_pdf_filename}")
                st.session_state.last_generated_pdf_path = pdf_path_generated # Simpan path untuk email
            else:
                st.warning("Tidak ada data yang dipilih untuk dibuat invoice PDF.")

    with col_excel:
        # === Buat Excel ===
        if st.button("📥 Unduh Excel"):
            if not selected_data.empty:
                excel_data = selected_data.drop(columns=["Pilih", "Harga Beli", "Admin", "%Laba", "Nama Pemesan"], errors="ignore")
                excel_buffer = io.BytesIO()
                excel_data.to_excel(excel_buffer, index=False, engine="openpyxl")
                excel_buffer.seek(0)

                st.download_button(
                    "📥 Unduh Excel",
                    data=excel_buffer,
                    file_name=current_excel_filename, # Gunakan nama file Excel yang dinamis
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success(f"✅ File Excel berhasil dibuat: {current_excel_filename}")
            else:
                st.warning("Tidak ada data yang dipilih untuk dibuat file Excel.")

    with col_email:
        # === Kirim Email ===
        email = st.text_input("Email (opsional) untuk kirim invoice", key="email_input")
        if st.button("📧 Kirim Email"):
            if not email:
                st.warning("Mohon masukkan alamat email untuk mengirim invoice.")
            elif not selected_data.empty:
                if st.session_state.last_generated_pdf_path: # Pastikan PDF sudah dibuat sebelumnya
                    try:
                        import yagmail
                        # Penting: Konfigurasi yagmail untuk deployment di Streamlit Cloud
                        # OAuth2 credentials harus diatur di Streamlit Secrets
                        # Misalnya, di .streamlit/secrets.toml
                        # [yagmail_creds]
                        # user = "your_email@gmail.com"
                        # oauth2_file = "path/to/your/oauth2_creds.json" # atau string JSON langsung
                        
                        # Contoh penggunaan dari secrets:
                        # yag = yagmail.SMTP(user=st.secrets["yagmail_creds"]["user"], 
                        #                    oauth2_file=st.secrets["yagmail_creds"]["oauth2_file"])
                        
                        # Untuk tujuan demo, saya akan menonaktifkan pengiriman email sebenarnya
                        # dan hanya menampilkan pesan.
                        
                        st.info("Simulasi pengiriman email: Fitur email membutuhkan konfigurasi Yagmail di Streamlit Secrets.")
                        # yag.send(
                        #     to=email,
                        #     subject="Invoice Pemesanan Anda",
                        #     contents="Terlampir adalah invoice pemesanan Anda.",
                        #     attachments=st.session_state.last_generated_pdf_path
                        # )
                        # st.success("✅ Email berhasil dikirim.")
                    except ImportError:
                        st.error("Modul `yagmail` tidak ditemukan. Silakan instal dengan `pip install yagmail`.")
                    except Exception as e:
                        st.error(f"❌ Gagal kirim email: {e}. Pastikan kredensial Yagmail sudah diatur di Streamlit Secrets.")
                else:
                    st.warning("Mohon buat Invoice PDF terlebih dahulu sebelum mengirim email.")
            else:
                st.warning("Tidak ada data yang dipilih untuk dibuat invoice.")
