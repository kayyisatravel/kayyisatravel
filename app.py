import os
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"
import streamlit as st
from PIL import Image
import easyocr
import numpy as np
import pandas as pd
import PyPDF2
from pdf2image import convert_from_bytes
from process_ocr import process_ocr_unified
from sheets_utils import connect_to_gsheet, append_dataframe_to_sheet
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import math # Untuk pembulatan jika diperlukan
from typing import List, Dict
from gspread.utils import rowcol_to_a1
from datetime import datetime
from zoneinfo import ZoneInfo  # Built-in mulai Python 3.9
import time
from generator import parse_input_dynamic, generate_eticket, parse_evoucher_text, generate_evoucher_html, generate_pdf417_barcode, generate_eticket_pdf
from typing import List
from tqdm import tqdm  # hanya dipakai untuk progress (bisa dihapus kalau tidak ingin)

now = datetime.now(ZoneInfo("Asia/Jakarta"))

#refresh
# --- PAGE CONFIG ---
st.set_page_config(page_title="OCR & Dashboard Tiket", layout="centered")

# --- CACHE RESOURCES ---
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['en', 'id'], gpu=False)
def parse_harga(harga):
    try:
        if isinstance(harga, (int, float)):
            return float(harga)
        return float(str(harga).replace("Rp", "").replace(".", "").replace(",", "").strip())
    except:
        return 0.0
@st.cache_data

def prepare_batch_update(
    df_all: pd.DataFrame,
    selected_norm: pd.DataFrame,
    update_config: Dict[str, str],
    worksheet_cols: List[str]
) -> List[Dict[str, object]]:
    """
    Siapkan list update dalam format yang kompatibel dengan gspread's batch_update().
    
    Returns:
        List of {"range": "A2:D2", "values": [["val1", "val2", "val3", "val4"]]}
    """
    updates = []

    for _, row in selected_norm.iterrows():
        mask = (
            (df_all["Nama Pemesan_str"] == row["Nama Pemesan_str"]) &
            (df_all["Kode Booking_str"] == row["Kode Booking_str"]) &
            (df_all["Tgl Berangkat_str"] == row["Tgl Berangkat_str"])
        )

        if mask.any():
            matching_index = df_all[mask].index[0]
            row_number = matching_index + 2  # baris header +1

            col_indices = []
            values = []

            for col_name, new_value in update_config.items():
                if col_name in worksheet_cols:
                    col_idx = worksheet_cols.index(col_name) + 1
                    col_indices.append(col_idx)
                    values.append(new_value)

            if col_indices:
                min_col = min(col_indices)
                max_col = max(col_indices)
                start_a1 = rowcol_to_a1(row_number, min_col)
                end_a1 = rowcol_to_a1(row_number, max_col)
                range_a1 = f"{start_a1}:{end_a1}"

                # Susun list nilai (baris tunggal, bisa multiple kolom)
                updates.append({
                    "range": range_a1,
                    "values": [values]
                })

    return updates
 # === Fungsi PDF ===
import os
from fpdf import FPDF
import streamlit as st

import os
from fpdf import FPDF
import streamlit as st

from fpdf import FPDF
import streamlit as st

from fpdf import FPDF
import pandas as pd
from datetime import datetime

def buat_invoice_pdf(data, tanggal_invoice, unique_invoice_no, output_pdf_filename, logo_path, ttd_path=None, status_lunas="BELUM LUNAS"):
    # =============================
    # Inisialisasi PDF
    # =============================
    pdf = FPDF(orientation="P", unit="mm", format="A4")  # Portrait
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # =============================
    # HEADER (ALAMAT + LOGO)
    # =============================
    pdf.set_font("Arial", "B", 8)
    pdf.set_y(20)  # jarak dari atas halaman
    alamat_perusahaan = (
        "KAYYISA TOUR & TRAVEL\n"
        "The Taman Dhika Cluster Wilis Blok F2 No. 2 Buduran, Sidoarjo - Jawa Timur\n"
        "Mobile: 081217026522  Email: kayyisatour@gmail.com"
    )
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, alamat_perusahaan, align="L")
    
    # LOGO di kanan
    if logo_path:
        try:
            logo_width = 40
            # posisi X = lebar halaman - margin kanan - lebar logo
            logo_x = pdf.w - pdf.r_margin - logo_width
            pdf.image(logo_path, x=logo_x, y=10, w=logo_width)
        except Exception as e:
            print("Gagal load logo:", e)
    #pdf.set_draw_color(0, 0, 0)  # warna garis hitam
    #pdf.set_line_width(0.3)  # ketebalan garis tipis
    #pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())  # garis horisontal penuh
    #pdf.set_y(pdf.get_y() + 2)
    pdf.ln(5)  # beri jarak setelah header
    pdf.set_draw_color(0, 0, 0)  # warna garis hitam
    pdf.set_line_width(0.3)  # ketebalan garis tipis
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())  # garis horisontal penuh
    pdf.set_y(pdf.get_y() + 2)  # beri jarak 2 mm setelah garis

    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "INVOICE", ln=True, align="C")
    pdf.ln(5)

    # Nama Customer pertama
    try:
        nama_customer_pertama = data[0].get("Nama Customer", "Pelanggan")
    except:
        nama_customer_pertama = "Pelanggan"

    tanggal_invoice = datetime.now()  # Tanggal cetak sebagai tanggal invoice
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 6, f"Nama Pemesan: {nama_customer_pertama}", ln=True)
    pdf.cell(0, 6, f"Tanggal Invoice: {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(0, 6, f"No. Invoice: {unique_invoice_no}", ln=True)
    pdf.ln(5)

    # =============================
    # KOLOM TABEL
    # =============================
    kolom_final = [
        "No",
        "Tgl Pemesanan",
        "Tgl Berangkat",
        "Kode Booking",
        "No Penerbangan / Hotel / Kereta",
        "Durasi",
        "Nama Customer",
        "Rute",
        "Harga Jual"
    ]

    # Kolom yang ada di data
    kolom_pdf = [c for c in kolom_final if c != "No" and c in data[0].keys()]

    # Mapping Header
    header_mapping = {
        "Harga Jual": "Harga"
    }

    # =============================
    # Hitung lebar kolom
    # =============================
    pdf.set_font("Arial", "B", 8)
    col_widths = {"No": 8}
    min_widths = {
        "Tgl Pemesanan": 22,
        "Tgl Berangkat": 22,
        "Durasi": 15,
        "Harga Jual": 22,
        "Kode Booking": 25,
        "Nama Customer": 40,
        "Rute": 30,
        "No Penerbangan / Hotel / Kereta": 50,
    }

    for col in kolom_pdf:
        header = header_mapping.get(col, col)
        max_w = pdf.get_string_width(header) + 2
        pdf.set_font("Arial", "", 9)
        for row in data:
            val = str(row.get(col, ""))
            max_w = max(max_w, pdf.get_string_width(val) + 2)
        col_widths[col] = max(min_widths.get(col, 0), max_w)

    # Sesuaikan total lebar kolom agar tidak melebihi halaman
    max_total_width = pdf.w - 2 * pdf.l_margin
    total_width = sum(col_widths.values())
    if total_width > max_total_width:
        scale = max_total_width / total_width
        for k in col_widths:
            col_widths[k] *= scale

    # =============================
    # CETAK HEADER TABEL
    # =============================
    pdf.set_font("Arial", "B", 7)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(col_widths["No"], 7, "No", 1, 0, 'C', 1)
    for col in kolom_pdf:
        pdf.cell(col_widths[col], 7, header_mapping.get(col, col), 1, 0, 'C', 1)
    pdf.ln()

    # =============================
    # ISI TABEL
    # =============================
    pdf.set_font("Arial", "", 7)
    row_h = 6
    for i, row in enumerate(data, 1):
        pdf.cell(col_widths["No"], row_h, str(i), 1, 0, 'C')
        for col in kolom_pdf:
            val = row.get(col, "")
            # Format tanggal
            if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                try:
                    val = pd.to_datetime(val).strftime("%d-%m-%Y")
                except:
                    val = str(val)
            pdf.cell(col_widths[col], row_h, str(val), 1, 0, 'C')
        pdf.ln()
    pdf.ln(5)

    # =============================
    # BAGIAN BAWAH (REKENING & TTD)
    # =============================
    def to_number(val):
        if isinstance(val, (int, float)):
            return val
    
        if isinstance(val, str):
            # Ambil semua angka dari string
            digits = re.findall(r"\d+", val)
            if digits:
                return float("".join(digits))
        
        return 0
    def terbilang(n):
        angka = ["Nol", "Satu", "Dua", "Tiga", "Empat", "Lima", 
                 "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]
    
        n = int(n)
    
        if n == 0:
            return "Nol"
    
        elif n < 12:
            return angka[n]
        elif n < 20:
            return terbilang(n - 10) + " Belas"
        elif n < 100:
            sisa = n % 10
            return terbilang(n // 10) + " Puluh" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 200:
            return "Seratus" + ("" if n == 100 else " " + terbilang(n - 100))
        elif n < 1000:
            sisa = n % 100
            return terbilang(n // 100) + " Ratus" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 2000:
            return "Seribu" + ("" if n == 1000 else " " + terbilang(n - 1000))
        elif n < 1_000_000:
            sisa = n % 1000
            return terbilang(n // 1000) + " Ribu" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 1_000_000_000:
            sisa = n % 1_000_000
            return terbilang(n // 1_000_000) + " Juta" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 1_000_000_000_000:
            sisa = n % 1_000_000_000
            return terbilang(n // 1_000_000_000) + " Milyar" + ("" if sisa == 0 else " " + terbilang(sisa))
        else:
            sisa = n % 1_000_000_000_000
            return terbilang(n // 1_000_000_000_000) + " Triliun" + ("" if sisa == 0 else " " + terbilang(sisa))



    if status_lunas.upper() == "LUNAS":
        total_harga = 0
    else:
        total_harga = sum(to_number(row.get("Harga Jual", 0)) for row in data)

    
    left_x = pdf.l_margin
    right_x = pdf.w - 90
    
    # --- KIRI (DAFTAR BANK) ---
   # --- TOTAL + TERBILANG ---
    pdf.set_x(left_x)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(0, 0, 0)
    
    # Total nominal
    pdf.cell(0, 8, f"TOTAL TAGIHAN: Rp {total_harga:,.0f}", ln=True)
    
    # Terbilang
    if total_harga == 0:
        terbilang_text = "Nol rupiah"
    else:
        terbilang_text = terbilang(total_harga).strip().capitalize() + " rupiah"

    pdf.set_font("Arial", "I", 8)
    pdf.multi_cell(0, 6, f"({terbilang_text})", align="L")
    pdf.ln(2)
    
    # Simpan posisi Y terakhir untuk TTD kanan
    y_setelah_terbilang = pdf.get_y()



    #num_rows = len(bank_list)  # total baris daftar bank

    # --- KANAN (TEMPAT/TANGGAL + TTD) ---
    pdf.set_xy(right_x + 45, y_setelah_terbilang)
    pdf.set_font("Arial", "", 9)
    pdf.cell(80, 6, f"Sidoarjo, {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True)
    pdf.set_x(right_x + 50)
    pdf.cell(80, 6, "Hormat Kami,", ln=True)
    pdf.ln(2)
    
    if not ttd_path:
        pdf.set_x(right_x + 5)
        pdf.set_font("Arial", "I", 6)
        pdf.cell(80, 6, "Dicetak Otomatis, Tidak Memerlukan Tanda Tangan", ln=True)
    else:
        try:
            ttd_w = 40
            ttd_x = right_x + 5
            ttd_y = pdf.get_y()
            pdf.image(ttd_path, x=ttd_x, y=ttd_y, w=ttd_w)
            pdf.ln(22)
        except:
            pdf.ln(12)
    
    pdf.set_x(right_x + 50)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(80, 6, "Rizal D Aqsa", ln=True)

    pdf.ln(2)  # beri jarak sedikit setelah TTD/Nama
    pdf.set_x(left_x)
    pdf.set_font("Arial", "", 7)
    if status_lunas.upper() == "LUNAS":
        pdf.set_font("Arial", "B", 8)
        pdf.cell(0, 6, "Pembayaran: LUNAS", ln=True)
    else:
        pdf.set_font("Arial", "", 7)
        pdf.cell(0, 6, "Transfer Pembayaran:", ln=True)
        bank_list = [
        "Bank BCA - 0881651041",
        "Bank Mandiri - 1420022043888",
        "Bank BNI - 0197267094",
        "Bank BRI - 008601138769506",
        "Bank BSI - 2204899994",
        ]    
        for bank in bank_list:
            pdf.set_x(left_x)
            pdf.multi_cell(80, 3, f"{bank} a.n Josirma Sari Pratiwi", align="L")
    
    # =============================
    # TEKS OTOMATIS DI ATAS FOOTER
    # =============================
    pdf.set_x(left_x)
    pdf.set_y(-50)  # 2-3 baris di atas footer
    pdf.set_font("Arial", "I", 6)
    pdf.multi_cell(0, 5, "Invoice ini dicetak secara otomatis oleh komputer dan tidak memerlukan tanda tangan", align="C")

    # =============================
    # OUTPUT FILE
    # =============================
    pdf.output(output_pdf_filename)
    return output_pdf_filename






# === UI Streamlit ===
#st.set_page_config(page_title="Buat Invoice Tiket", layout="centered")
#st.title("🧾 Buat Invoice")

#df = load_data()
#st.write("Data contoh Tgl Pemesanan (5 pertama):", df["Tgl Pemesanan"].head())
#st.write("Tipe data kolom Tgl Pemesanan:", df["Tgl Pemesanan"].apply(type).unique())
#st.write("Tanggal filter:", tanggal_range)

# ... (kode UI Streamlit di bagian atas) ...

def normalize_df(df):
    df = df.copy()

    # Pastikan tanggal di-parse dengan dayfirst=True
    df["Tgl Berangkat"] = pd.to_datetime(df["Tgl Berangkat"], dayfirst=True, errors="coerce")
    df["Tgl Berangkat_str"] = df["Tgl Berangkat"].dt.strftime("%d-%m-%Y").fillna("")

    # Konversi kode booking ke string
    df["Kode Booking_str"] = df["Kode Booking"].astype(str).str.strip().str.upper()

    # Nama Pemesan ke string uppercase
    if "Nama Pemesan" in df.columns:
        df["Nama Pemesan_str"] = df["Nama Pemesan"].astype(str).str.strip().str.upper()
    else:
        df["Nama Pemesan_str"] = ""

    if "Nama Customer" in df.columns:
        df["Nama Customer_str"] = df["Nama Customer"].astype(str).str.strip().str.upper()
    else:
        df["Nama Customer_str"] = ""

    return df

def extract_text_from_pdf(pdf_bytes):
    reader = get_ocr_reader()
    pages = convert_from_bytes(pdf_bytes.read(), dpi=300)
    texts = []
    for page in pages[:5]:
        img = page.convert('RGB')
        img = resize_image(img, max_dim=1600)
        result = reader.readtext(np.array(img), detail=0)
        texts.append("\n".join(result))
    return "\n\n".join(texts)

try:
    resample = Image.Resampling.LANCZOS
except AttributeError:
    resample = Image.ANTIALIAS

# --- UTILITIES ---
def resize_image(img: Image.Image, max_dim=1024) -> Image.Image:
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        return img.resize((int(w * scale), int(h * scale)), resample)
    return img

# --- INITIALIZE SESSION STATE ---
for key, default in {
    'manual_input_area': '',
    'parsed_entries_manual': None,
    'parsed_entries_ocr': None,
    'bulk_input': ''
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Google Sheets ID
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

import re
import pandas as pd
import streamlit as st

def save_gsheet(df: pd.DataFrame):
    """
    Simpan DataFrame ke Google Sheets jika tidak ada duplikat
    berdasarkan kolom unik: Nama Customer, Kode Booking, Tgl Pemesanan.
    """
    if df is None or df.empty:
        st.warning("❌ Data kosong atau invalid.")
        return

    # Konversi kolom tanggal lebih awal (hindari parsing berulang)
    df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce").dt.date

    # Ambil worksheet
    ws = connect_to_gsheet(SHEET_ID, 'Data')
    
    # Ambil hanya kolom kunci dari sheet (bukan semua data)
    key_cols = ["Nama Customer", "Kode Booking", "Tgl Pemesanan"]
    existing_keys = ws.get_all_values()
    if not existing_keys or len(existing_keys) < 2:
        existing_df = pd.DataFrame(columns=key_cols)
    else:
        header = existing_keys[0]
        rows = existing_keys[1:]
        key_indices = [header.index(k) for k in key_cols]
        filtered_rows = [[r[i] for i in key_indices] for r in rows]
        existing_df = pd.DataFrame(filtered_rows, columns=key_cols)
        existing_df["Tgl Pemesanan"] = pd.to_datetime(existing_df["Tgl Pemesanan"], errors="coerce").dt.date

    # Gabung dan cek duplikat
    df["dupe_key"] = df[key_cols].astype(str).agg("__".join, axis=1)
    existing_df["dupe_key"] = existing_df[key_cols].astype(str).agg("__".join, axis=1)

    dupes = df[df["dupe_key"].isin(set(existing_df["dupe_key"]))]
    if not dupes.empty:
        st.error("❌ Ditemukan duplikat data yang sudah ada di GSheet:")
        st.dataframe(dupes[key_cols])
        st.warning("Mohon periksa data sebelum mengirim ulang.")
        return

    # Hapus kolom bantuan sebelum kirim
    df = df.drop(columns=["dupe_key"])
    
    # Kirim data
    append_dataframe_to_sheet(df, ws)
    st.success("✅ Berhasil simpan data ke Google Sheets.")



# --- TAMPILAN UTAMA ---
# CSS custom
st.markdown("""
    <style>
        html, body, [class*="css"] {
            background-color: #2c3e50;
            color: #ecf0f1;
            font-family: 'Segoe UI', sans-serif;
        }
        .main-header {
            font-size: 2.5em;
            font-weight: bold;
            color: #f39c12;
            padding-bottom: 0.2em;
        }
        .sub-header {
            font-size: 1.2em;
            color: #bdc3c7;
            margin-bottom: 1em;
        }
        .highlight {
            color: #ffffff;
            background-color: #e67e22;
            padding: 0.3em 0.6em;
            border-radius: 6px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# Layout: 2 kolom
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="main-header">Dashboard Tiket |<span class="highlight">Kayyisa Tour & Travel</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Input & Simpan Data Pesanan</div>', unsafe_allow_html=True)

with col2:
    st.image("https://www.pngmart.com/files/17/Travel-Icon-PNG-Image.png", width=150)

st.markdown("""<hr style="border-top: 1px solid #7f8c8d;">""", unsafe_allow_html=True)
#with st.sidebar:
    
# --- SECTION 1: UPLOAD & OCR ---
#st.markdown('---')
with st.expander("⬆️📷 Upload Gambar atau PDF untuk OCR"):
    file = st.file_uploader(
        "Pilih file gambar (.jpg/.png) atau PDF",
        type=['jpg','jpeg','png','pdf'],
        key='file_uploader'
    )    
    ocr_text = ''
    if file:
        if file.type == 'application/pdf':
            ocr_text = extract_text_from_pdf(file)
        else:
            img = Image.open(file).convert('RGB')
            img = resize_image(img)
            st.image(img, caption='Gambar Terupload', use_column_width=True)
            reader = get_ocr_reader()
            result = reader.readtext(np.array(img), detail=0)
            ocr_text = "\n".join(result)
    
        if ocr_text:
            st.text_area('Hasil OCR', ocr_text, height=200, key='ocr_area')
            
            # Tampilkan tombol untuk Proses Data OCR
            if st.button('➡️ Proses Data OCR'):
                try:
                    # Proses OCR text menjadi DataFrame
                    df_ocr = pd.DataFrame(process_ocr_unified(ocr_text))
                    st.session_state.parsed_entries_ocr = df_ocr
    
                    # Tampilkan editor untuk edit hasil OCR
                    st.subheader("📝 Edit Data Hasil OCR (Opsional)")
                    edited_df = st.dataframe(df_ocr, num_rows="dynamic", use_container_width=True)
    
                    # Simpan hasil edit ke session state
                    st.session_state.parsed_entries_ocr = edited_df
    
                    # Tampilkan data yang sudah diedit
                    st.markdown("#### Preview Data OCR Setelah Diedit")
                    st.dataframe(edited_df, use_container_width=True)
                except Exception as e:
                    st.error(f"OCR Processing Error: {e}")


# --- SECTION 2: MANUAL INPUT ---

#def manual_input_section():
#    st.markdown('---')
#    st.subheader('2a. Input Data Manual')
#    input_text = st.text_area(
 #       'Masukkan Teks Manual',
  #      value=st.session_state.manual_input_area,
   #     height=200,
    #    key='manual_input_area'
#    )
 #   col1, col2 = st.columns(2)
  #  with col1:
   #     if st.button('🔍 Proses Manual'):
    #        try:
     #           df_man = pd.DataFrame(process_ocr_unified(input_text))
      #          st.dataframe(df_man, use_container_width=True)
       #         st.session_state.parsed_entries_manual = df_man
        #    except Exception as e:
         #       st.error(f"Manual Processing Error: {e}")
#    with col2:
 #       if st.button('🧹 Clear Manual'):
  #          st.session_state.manual_input_area = ''
   #         st.session_state.parsed_entries_manual = None

#manual_input_section()

# --- SECTION 2: BULK MANUAL INPUT ---
#st.markdown('---')
with st.expander('⌨️ Upload Data Text'):
    if "bulk_input" not in st.session_state or not st.session_state["bulk_input"].strip():
        st.session_state["bulk_input"] = "Kode booking:\n\n\nBeli "

    raw = st.text_area(
        "Masukkan banyak entri, pisahkan setiap entri dengan '==='",
        key="bulk_input",
        height=200
    )


    if st.button("🔍 Proses Bulk"):
        entries = []
        labels = []
        for i, block in enumerate(raw.split("===")):
            block = block.strip()
            if block:
                try:
                    df_block = pd.DataFrame(process_ocr_unified(block))
                    entries.append(df_block)
                    labels.append(f"Entri {i+1}")
                except Exception as e:
                    st.error(f"Gagal parse blok ke-{i+1}: {e}")
        if entries:
            st.session_state.bulk_entries_raw = entries
            st.session_state.bulk_labels = labels
            st.session_state.bulk_parsed = pd.concat(entries, ignore_index=True)
    
    # Jika ada hasil bulk_entries_raw, tampilkan UI editing
    if "bulk_parsed" in st.session_state and not st.session_state.bulk_parsed.empty:
        df = st.session_state.bulk_parsed
    
        if "edit_mode_bulk" not in st.session_state:
            st.session_state.edit_mode_bulk = False
    
        # Checkbox untuk mengaktifkan edit mode
        # Aktifkan mode edit manual
        edit_mode = st.checkbox("✏️ Edit Data Manual", value=st.session_state.get("edit_mode_bulk", False))
        
        if edit_mode:
            st.session_state.edit_mode_bulk = True
            st.markdown("#### 📝 Edit Beberapa Baris")
        
            # Pilih beberapa baris
            selected_rows = st.multiselect("Pilih baris yang ingin diedit:", options=df.index.tolist())
        
            edited_rows = {}  # Simpan perubahan per baris
        
            for i in selected_rows:
                row_data = df.iloc[i].to_dict()
                st.markdown(f"---\n##### ✏️ Baris ke-{i}")
                with st.expander(f"📝 Edit Data Baris {i}", expanded=True):
                    updated_row = {}
                    for col, val in row_data.items():
                        if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                            try:
                                val = pd.to_datetime(val).date()
                            except:
                                val = pd.Timestamp.today().date()
                            new_val = st.date_input(f"{col} (Baris {i})", value=val, key=f"{col}_{i}")
                        elif isinstance(val, (int, float)):
                            new_val = st.text_input(f"{col} (Baris {i})", value=str(val), key=f"{col}_{i}")
                        else:
                            if col == "Keterangan":
                                default_val = "Belum Lunas" if pd.isna(val) or str(val).strip() == "" else str(val)
                            elif col == "Pemesan":
                                default_val = "ER ENDO" if pd.isna(val) or str(val).strip() == "" else str(val)
                            elif col == "Admin":
                                default_val = "PA" if pd.isna(val) or str(val).strip() == "" else str(val)
                            else:
                                default_val = str(val) if pd.notna(val) else ""
                            new_val = st.text_input(f"{col} (Baris {i})", value=default_val, key=f"{col}_{i}")
                        updated_row[col] = new_val
                    edited_rows[i] = updated_row
        
            # Simpan semua perubahan
            if st.button("💾 Simpan Semua Perubahan"):
                for i, updated_row in edited_rows.items():
                    for col, val in updated_row.items():
                        df.at[i, col] = val
            
                st.session_state.bulk_parsed = df
                st.session_state.edit_mode_bulk = False  # ⬅️ Reset ke tampilan semula
                st.success(f"✅ {len(edited_rows)} baris berhasil diperbarui.")
                st.rerun()

    
        else:
            st.session_state.edit_mode_bulk = False
            st.markdown("#### 📊 Data Gabungan Hasil Bulk")
            st.dataframe(st.session_state.bulk_parsed, use_container_width=True)


    
    # Bulk save button
    if st.session_state.get("bulk_parsed") is not None and st.button("📤 Simpan Bulk ke GSheet"):
        save_gsheet(st.session_state.bulk_parsed)
        for k in ["bulk_parsed", "bulk_input", "file_uploader"]:
            st.session_state.pop(k, None)
        st.rerun()

with st.expander("✏️ Input Manual Data"):
    tgl_pemesanan = st.date_input("Tgl Pemesanan", value=date.today(), key="tgl_pemesanan")
    tgl_berangkat = st.date_input("Tgl Berangkat", value=date.today(), key="tgl_berangkat")

    kode_booking = st.text_input("Kode Booking")
    no_penerbangan = st.text_input("No Penerbangan / Hotel / Kereta")
    durasi = st.text_input("Durasi")
    nama_customer = st.text_input("Nama Customer")
    rute = st.text_input("Rute")
    harga_beli = st.number_input("Harga Beli", min_value=0.0, step=1000.0, format="%.0f", key="harga_beli")
    harga_jual = st.number_input("Harga Jual", min_value=0.0, step=1000.0, format="%.0f", key="harga_jual")

    laba = harga_jual - harga_beli
    pct_laba = (laba / harga_beli * 100) if harga_beli > 0 else 0.0
    st.markdown(f"**Laba:** Rp {int(laba):,}".replace(",", "."))
    st.markdown(f"**% Laba:** {pct_laba:.2f}%")

    tipe = st.selectbox("Tipe", ["KERETA", "HOTEL", "PESAWAT"])
    bf_nbf = st.selectbox("BF/NBF", ["BF", "NBF", ""])
    no_invoice = st.text_input("No Invoice")
    keterangan = st.text_input("Keterangan")

    pemesan_options = ["ER ENDO", "KI ENDO", "BTN SMG", "PT MURINDA", "ASRUL", "Lainnya..."]
    nama_pemesan = st.selectbox("Nama Pemesan", pemesan_options)
    if nama_pemesan == "Lainnya...":
        nama_pemesan = st.text_input("Masukkan Nama Pemesan")

    admin = st.selectbox("Admin", ["PA", "MA"])

    if st.button("Preview"):
        new_data = {
            "Tgl Pemesanan": tgl_pemesanan,
            "Tgl Berangkat": tgl_berangkat,
            "Kode Booking": kode_booking,
            "No Penerbangan / Hotel / Kereta": no_penerbangan,
            "Durasi": durasi,
            "Nama Customer": nama_customer,
            "Rute": rute,
            "Harga Beli": harga_beli,
            "Harga Jual": harga_jual,
            "Laba": laba,
            "Tipe": tipe,
            "BF/NBF": bf_nbf,
            "No Invoice": no_invoice,
            "Keterangan": keterangan,
            "Nama Pemesan": nama_pemesan,
            "Admin": admin,
            "% Laba": pct_laba
        }
        if "bulk_parsed" not in st.session_state:
            st.session_state.bulk_parsed = pd.DataFrame()
        st.session_state.bulk_parsed = pd.concat(
            [st.session_state.bulk_parsed, pd.DataFrame([new_data])], ignore_index=True
        )
        st.success("✅ Data ditambahkan ke preview.")

# --- Preview dan edit data sebelum simpan ---
        if "bulk_parsed" in st.session_state and not st.session_state.bulk_parsed.empty:
            df = st.session_state.bulk_parsed
        
            # Bersihkan kolom dari spasi berlebih
            df.columns = df.columns.str.strip()
        
            # Tambahkan kolom jika belum ada (agar preview lengkap)
            for col in ["Laba", "% Laba"]:
                if col not in df.columns:
                    df[col] = 0.0
        
            # Hitung ulang kolom Laba dan % Laba
            df["Laba"] = df["Harga Jual"] - df["Harga Beli"]
            df["% Laba"] = df.apply(
                lambda row: (row["Laba"] / row["Harga Beli"] * 100) if row["Harga Beli"] > 0 else 0.0,
                axis=1
            )
        
            st.session_state.bulk_parsed = df  # simpan kembali yang sudah dihitung ulang
        
            # Mode edit
            if "edit_mode_bulk" not in st.session_state:
                st.session_state.edit_mode_bulk = False
        
            edit_mode = st.checkbox(
                "✏️ Edit Data Manual",
                value=st.session_state.edit_mode_bulk,
                key="edit_mode_bulk_checkbox"
            )
        
            if edit_mode:
                st.session_state.edit_mode_bulk = True
                st.markdown("#### 📝 Form Edit Manual Per Baris")
        
                row_index = st.number_input("Pilih baris ke-", min_value=0, max_value=len(df) - 1, step=1)
                row_data = df.iloc[row_index].to_dict()
                updated_row = {}
        
                for col, val in row_data.items():
                    if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                        if pd.isna(val) or val == "":
                            val = pd.Timestamp.today()
                        else:
                            try:
                                val = pd.to_datetime(val).date()
                            except:
                                val = pd.Timestamp.today().date()
                        new_val = st.date_input(f"{col}", value=val)
                    elif col in ["Harga Beli", "Harga Jual"]:
                        new_val = st.number_input(f"{col}", value=float(val) if val != "" else 0.0, step=1000.0, format="%.0f")
                    elif col in ["Laba", "% Laba"]:
                        st.markdown(f"**{col}:** {val:.2f}")  # tampilkan saja, tidak bisa diubah
                        new_val = val
                    else:
                        new_val = st.text_input(f"{col}", value=str(val) if pd.notna(val) else "")
                    updated_row[col] = new_val
        
                if st.button("💾 Simpan Perubahan"):
                    for col in updated_row:
                        if col in ["Harga Beli", "Harga Jual"]:
                            try:
                                df.at[row_index, col] = float(updated_row[col])
                            except:
                                df.at[row_index, col] = 0.0
                        elif col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                            try:
                                df.at[row_index, col] = pd.to_datetime(updated_row[col]).date()
                            except:
                                df.at[row_index, col] = pd.Timestamp.today().date()
                        elif col not in ["Laba", "% Laba"]:
                            df.at[row_index, col] = updated_row[col]
        
                    # Recalculate after update
                    df.at[row_index, "Laba"] = df.at[row_index, "Harga Jual"] - df.at[row_index, "Harga Beli"]
                    df.at[row_index, "% Laba"] = (
                        round((df.at[row_index, "Laba"] / df.at[row_index, "Harga Beli"]) * 100, 2)
                        if df.at[row_index, "Harga Beli"] > 0 else 0.0
                    )
        
                    st.session_state.bulk_parsed = df
                    st.session_state.edit_mode_bulk = False
                    st.success("✅ Perubahan disimpan.")
                    st.experimental_rerun()
        
            else:
                st.session_state.edit_mode_bulk = False
                st.markdown("#### 📊 Preview Data Manual")
                st.dataframe(df, use_container_width=True)
        
            if st.button("📤 Simpan ke GSheet"):
                try:
                    # Simpan ke GSheet
                    save_gsheet(st.session_state.get("bulk_parsed", []))
        
                    # Tandai berhasil disimpan
                    st.session_state["saved_success"] = True
        
                    # Hapus data dari session state
                    st.session_state.pop("bulk_parsed", None)
        
                    # Rerun app untuk bersihkan tampilan
                    st.rerun()
        
                except Exception as e:
                    st.error(f"❌ Gagal menyimpan: {e}")
        
            # Tampilkan notifikasi hanya setelah rerun
            if st.session_state.get("saved_success"):
                st.success("✅ Data berhasil disimpan dan preview dihapus.")
                st.session_state["saved_success"] = False


with st.expander("💾 Database Pemesan", expanded=False):
    # === Konfigurasi GSheet ===
    SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"
    WORKSHEET_NAME = "Data"

    def connect_to_gsheet(SHEET_ID, worksheet_name="Data"):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID)
        return sheet.worksheet(worksheet_name)

    @st.cache_data
    def load_data():
        ws = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
        df = pd.DataFrame(ws.get_all_records())
        if "Tgl Pemesanan" in df.columns:
            df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Tgl Pemesanan"])
        else:
            st.error("❌ Kolom 'Tgl Pemesanan' tidak ditemukan.")
            st.stop()
        return df

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        df = load_data()
    else:
        df = load_data()

    # === Filter Utama ===
    st.markdown("### 📊 Filter Data")
    df_filtered = df.copy()
    df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors='coerce')
    
    # Inisialisasi default tanggal_range supaya selalu ada
    today = date.today()
    awal_bulan = today.replace(day=1)
    tanggal_range = [pd.Timestamp(awal_bulan), pd.Timestamp(today)]
    
    filter_mode = st.radio(
        "Pilih Jenis Filter Tanggal",
        ["📆 Rentang Tanggal", "🗓️ Bulanan", "📅 Tahunan"],
        horizontal=True,
        key="filter_mode_radio"
    )
    
    if filter_mode == "📆 Rentang Tanggal":
        tgl_awal = st.date_input("Tanggal Awal", date.today().replace(day=1))
        tgl_akhir = st.date_input("Tanggal Akhir", date.today())
        if tgl_awal > tgl_akhir:
            tgl_awal, tgl_akhir = tgl_akhir, tgl_awal
        df_filtered = df[
            (df["Tgl Pemesanan"] >= pd.to_datetime(tgl_awal)) &
            (df["Tgl Pemesanan"] <= pd.to_datetime(tgl_akhir))
        ]

    elif filter_mode == "🗓️ Bulanan":
        bulan_nama = {
            "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
            "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
            "September": 9, "Oktober": 10, "November": 11, "Desember": 12
        }
        bulan_label = list(bulan_nama.keys())
        bulan_pilihan = st.selectbox("Pilih Bulan", bulan_label, index=date.today().month - 1)
        tahun_bulan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan"].dt.year.dropna().unique(), reverse=True))
        df_filtered = df[
            (df["Tgl Pemesanan"].dt.month == bulan_nama[bulan_pilihan]) &
            (df["Tgl Pemesanan"].dt.year == tahun_bulan)
        ]

    elif filter_mode == "📅 Tahunan":
        tahun_pilihan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan"].dt.year.dropna().unique(), reverse=True))
        df_filtered = df[df["Tgl Pemesanan"].dt.year == tahun_pilihan]

    # Tambahan filter untuk "Belum Lunas"
    if "Keterangan" in df.columns:
        filter_belum_lunas = st.checkbox("Tampilkan hanya yang Belum Lunas")
        if filter_belum_lunas:
            df_filtered = df_filtered[df_filtered["Keterangan"].str.contains("Belum Lunas", case=False, na=False)]


    # === Filter Tambahan ===
    st.markdown("### 🧍 Filter Tambahan")
    
    tampilkan_uninvoice_saja = st.checkbox("🔍 Tampilkan hanya yang belum ada Invoice")
    auto_select_25jt = st.checkbox("⚙️ Auto-pilih total penjualan hingga Rp 25 juta")
    
    # Tambahan input baru untuk Nama Customer
    nama_customer_filter = st.text_input("Cari Nama Customer")
    
    # Input lainnya (sudah ada sebelumnya)
    nama_filter = st.text_input("Cari Nama Pemesan")
    kode_booking_filter = st.text_input("Cari Kode Booking")
    no_invoice_filter = st.text_input("Cari No Invoice")
    
    # === Proses Filter ===
    
    # 1️⃣ Filter berdasarkan Nama Customer
    if nama_customer_filter:
        df_filtered = df_filtered[df_filtered["Nama Customer"].str.contains(nama_customer_filter, case=False, na=False)]
    
    # 2️⃣ Filter berdasarkan Nama Pemesan
    if nama_filter:
        df_filtered = df_filtered[df_filtered["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
    
    # 3️⃣ Filter berdasarkan Kode Booking
    if kode_booking_filter:
        df_filtered = df_filtered[df_filtered["Kode Booking"].astype(str).str.contains(kode_booking_filter, case=False, na=False)]
    
    # 4️⃣ Bersihkan dan Filter No Invoice
    df_filtered["No Invoice"] = df_filtered["No Invoice"].astype(str).str.strip()
    
    if no_invoice_filter:
        df_filtered = df_filtered[df_filtered["No Invoice"].str.contains(no_invoice_filter.strip(), case=False, na=False)]
    
    # 5️⃣ Filter hanya yang belum ada Invoice
    if tampilkan_uninvoice_saja:
        df_filtered = df_filtered[df_filtered["No Invoice"].isna() | (df_filtered["No Invoice"].str.strip() == "")]



    # === Tampilkan & Edit Data ===
    if df_filtered.empty:
        st.warning("❌ Tidak ada data yang cocok.")
    else:
        st.success(f"✅ Menampilkan {len(df_filtered)} data sesuai filter.")
        editable_df = df_filtered.copy()
        editable_df.insert(0, 'Pilih', False)

        def parse_harga(harga_str):
            if pd.isna(harga_str):
                return 0
            s = str(harga_str).replace('Rp', '').replace('.', '').replace(',', '').strip()
            try:
                return float(s)
            except:
                return 0

        MAX_TOTAL = 25_000_000
        if auto_select_25jt:
            total = 0
            for i in editable_df.index:
                harga = parse_harga(editable_df.loc[i, "Harga Jual"])
                if total + harga <= MAX_TOTAL:
                    editable_df.at[i, "Pilih"] = True
                    total += harga
                else:
                    break

        if "editable_df" not in st.session_state:
            st.session_state.editable_df = editable_df

        if not st.session_state.editable_df.equals(editable_df):
            st.session_state.editable_df = editable_df.copy()
            st.session_state.editable_df["Pilih"] = False

        if auto_select_25jt:
            total = 0
            for i in st.session_state.editable_df.index:
                harga = parse_harga(st.session_state.editable_df.loc[i, "Harga Jual"])
                if total + harga <= MAX_TOTAL:
                    st.session_state.editable_df.at[i, "Pilih"] = True
                    total += harga
                else:
                    break

        select_all = st.checkbox("Pilih Semua", value=False, key="select_all_checkbox")
        if select_all:
            st.session_state.editable_df["Pilih"] = True
        else:
            if st.session_state.editable_df["Pilih"].all() and st.session_state.get("last_select_all_state", False):
                st.session_state.editable_df["Pilih"] = False
        st.session_state.last_select_all_state = select_all

        selected_df = st.data_editor(
            st.session_state.editable_df,
            use_container_width=True,
            num_rows="fixed",
            disabled=[col for col in editable_df.columns if col != "Pilih"],
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang untuk buat invoice")
            }
        )
        st.session_state.editable_df = selected_df
        selected_data = selected_df[selected_df["Pilih"]]
# === Edit Form untuk 1 Baris ===
        if len(selected_data) == 1:
            with st.expander('Edit Data yang dipilih'):
                #st.markdown("### ✏️ Edit Data Terpilih")
                row_to_edit = selected_data.iloc[0]
            
                # Fungsi bantu amankan tanggal
                def safe_date(val):
                    if isinstance(val, date):
                        return val
                    if isinstance(val, str):
                        try:
                            return datetime.strptime(val, "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    if isinstance(val, pd.Timestamp):
                        return val.date()
                    return date.today()
            
                # Ambil dan validasi input
                nama_pemesan_form = st.text_input("Nama Pemesan", row_to_edit.get("Nama Pemesan", ""), key="edit_nama_pemesan")
                tgl_pemesanan_form = st.date_input("Tgl Pemesanan", safe_date(row_to_edit.get("Tgl Pemesanan")), key="edit_tgl_pemesanan")
                tgl_berangkat_form = st.date_input("Tgl Berangkat", safe_date(row_to_edit.get("Tgl Berangkat")), key="edit_tgl_berangkat")
                kode_booking_form = st.text_input("Kode Booking", row_to_edit.get("Kode Booking", ""), key="edit_kode_booking")
                no_penerbangan_form = st.text_input("No Penerbangan / Hotel / Kereta", row_to_edit.get("No Penerbangan / Hotel / Kereta", ""), key="edit_no_penerbangan")
                nama_customer_form = st.text_input("Nama Customer", row_to_edit.get("Nama Customer", ""), key="edit_nama_customer")
                rute_form = st.text_input("Rute", row_to_edit.get("Rute", ""), key="edit_rute")
                harga_beli_form = st.number_input("Harga Beli", value=parse_harga(row_to_edit.get("Harga Beli", 0)), format="%.0f", key="edit_harga_beli")
                harga_jual_form = st.number_input("Harga Jual", value=parse_harga(row_to_edit.get("Harga Jual", 0)), format="%.0f", key="edit_harga_jual")
                no_invoice_form = st.text_input("No Invoice", row_to_edit.get("No Invoice", ""), key="edit_no_invoice")
                keterangan_form = st.text_input("Keterangan", row_to_edit.get("Keterangan", ""), key="edit_keterangan")
                admin_form = st.text_input("Admin", row_to_edit.get("Admin", ""), key="edit_admin")

            
                if st.button("💾 Simpan Perubahan ke GSheet"):
                    try:
                        worksheet = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
                        all_data = worksheet.get_all_records()
                        df_all = pd.DataFrame(all_data)
                        
                        # Normalisasi kedua dataframe
                        df_all = normalize_df(df_all)
                        selected_norm = normalize_df(pd.DataFrame([row_to_edit])).reset_index(drop=True)
                        
                        mask = (
                            (df_all["Nama Pemesan_str"] == selected_norm.loc[0, "Nama Pemesan_str"]) &
                            (df_all["Nama Customer_str"] == selected_norm.loc[0, "Nama Customer_str"]) &  
                            (df_all["Kode Booking_str"] == selected_norm.loc[0, "Kode Booking_str"]) &
                            (df_all["Tgl Berangkat_str"] == selected_norm.loc[0, "Tgl Berangkat_str"])
                        )
    
            
                        if not mask.any():
                            st.warning("❌ Data asli tidak ditemukan di Google Sheets.")
                        else:
                            index = mask.idxmax()
                            colmap = {
                                "Nama Pemesan": nama_pemesan_form,
                                "Tgl Pemesanan": tgl_pemesanan_form.strftime('%Y-%m-%d'),
                                "Tgl Berangkat": tgl_berangkat_form.strftime('%Y-%m-%d'),
                                "Kode Booking": kode_booking_form,
                                "No Penerbangan / Hotel / Kereta": no_penerbangan_form,
                                "Nama Customer": nama_customer_form,
                                "Rute": rute_form,
                                "Harga Beli": harga_beli_form,
                                "Harga Jual": harga_jual_form,
                                #"Tipe": tipe_form.upper(),
                                #"BF/NBF": bf_nbf_form,
                                "No Invoice": no_invoice_form,
                                "Keterangan": keterangan_form,
                                "Admin": admin_form
                            }
            
                            for col, val in colmap.items():
                                if col in df_all.columns:
                                    worksheet.update_cell(index + 2, df_all.columns.get_loc(col) + 1, val)
                                    time.sleep(0.2)
                            st.success("✅ Data berhasil diperbarui ke Google Sheets.")
                            st.cache_data.clear()
            
                    except Exception as e:
                        st.error(f"❌ Gagal update: {e}")
                        st.text(f"📋 Type: {type(e)}")

        
        elif len(selected_data) > 1:
            with st.expander('Update Massal (Beberapa Baris)'):
                st.markdown("### 🛠️ Update Massal (Beberapa Baris)")
                st.info("Pilih beberapa baris untuk melakukan update massal pada kolom tertentu.")
            
                # Checkbox filter data yang belum dibuat invoice
                filter_uninvoice = st.checkbox("Belum dibuat INV (Tampilkan hanya data tanpa No Invoice)")
            
                # Kolom input untuk mass update
                no_invoice_mass = st.text_input("No Invoice (Mass Update)")
                kosongkan_invoice = st.checkbox("Kosongkan No Invoice")
            
                keterangan_mass = st.text_input("Keterangan (Mass Update)")
                kosongkan_keterangan = st.checkbox("Kosongkan Keterangan")
            
                nama_pemesan_mass = st.text_input("Nama Pemesan (Mass Update)")
                kosongkan_nama_pemesan = st.checkbox("Kosongkan Nama Pemesan")
            
                admin_mass = st.text_input("Admin (Mass Update)")
                kosongkan_admin = st.checkbox("Kosongkan Admin")
            
                # Ambil data lengkap dari worksheet
                worksheet = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
                all_data = worksheet.get_all_records()
                df_all = pd.DataFrame(all_data)
            
                # Normalisasi df_all dan selected_data
                df_all = normalize_df(df_all)
                selected_norm = normalize_df(selected_data)
            
                # Terapkan filter "Belum dibuat INV"
                if filter_uninvoice:
                    df_all["No Invoice"] = df_all["No Invoice"].replace("", pd.NA)
                    df_all = df_all[df_all["No Invoice"].isna()]
                df_all_unique = df_all.drop_duplicates(
                    subset=["Nama Pemesan_str", "Kode Booking_str", "Tgl Berangkat_str"]
                )
                df_to_update = pd.merge(
                    selected_norm,
                    df_all_unique,
                    on=["Nama Pemesan_str", "Kode Booking_str", "Tgl Berangkat_str"],
                    how="inner",
                    suffixes=('', '_matched')
                )
                # Tampilkan data yang difilter jika ingin (opsional)
                st.write("### Data yang akan diproses:")
                st.dataframe(df_to_update)
                
                if st.button("🔁 Terapkan Update Massal"):
                    try:
                        count = 0
                        gagal = 0
                        duplikat = 0
                        tidak_ditemukan = []
                        update_requests = []
                
                        # --- Normalisasi string agar pencocokan lebih akurat ---
                        for df in [df_all, selected_norm]:
                            for col in ["Nama Pemesan", "Kode Booking", "Tgl Berangkat", "Nama Customer"]:
                                col_str = f"{col}_str"
                                df[col_str] = df[col].astype(str).str.strip().str.lower()
                
                        progress = st.progress(0)
                        total_rows = len(selected_norm)
                        
                        for i, (idx, row) in enumerate(selected_norm.iterrows(), start=1):
                            progress.progress(min(i / total_rows, 1.0))

                
                            # Buat mask pencocokan lebih spesifik (4 kolom kunci)
                            mask = (
                                (df_all["Nama Pemesan_str"] == row["Nama Pemesan_str"]) &
                                (df_all["Kode Booking_str"] == row["Kode Booking_str"]) &
                                (df_all["Tgl Berangkat_str"] == row["Tgl Berangkat_str"]) &
                                (df_all["Nama Customer_str"] == row["Nama Customer_str"])
                            )
                
                            match_count = mask.sum()
                
                            if match_count == 0:
                                gagal += 1
                                tidak_ditemukan.append({
                                    "Nama Pemesan": row["Nama Pemesan"],
                                    "Nama Customer": row["Nama Customer"],
                                    "Kode Booking": row["Kode Booking"],
                                    "Tgl Berangkat": row["Tgl Berangkat"]
                                })
                                continue
                
                            if match_count > 1:
                                duplikat += 1
                                st.warning(f"⚠️ Duplikat ditemukan untuk {row['Nama Customer']} - {row['Kode Booking']}. Update dilewati.")
                                continue
                
                            # Ambil index tunggal dari match
                            matching_index = df_all[mask].index[0]
                            row_number = matching_index + 2  # baris di GSheets (header + 1)
                
                            # --- Buat daftar update yang akan dikirim sekaligus ---
                            if no_invoice_mass or kosongkan_invoice:
                                nilai = "" if kosongkan_invoice else no_invoice_mass
                                col_index = df_all.columns.get_loc("No Invoice") + 1
                                update_requests.append((row_number, col_index, nilai))
                            if keterangan_mass or kosongkan_keterangan:
                                nilai = "" if kosongkan_keterangan else keterangan_mass
                                col_index = df_all.columns.get_loc("Keterangan") + 1
                                update_requests.append((row_number, col_index, nilai))
                            if nama_pemesan_mass or kosongkan_nama_pemesan:
                                nilai = "" if kosongkan_nama_pemesan else nama_pemesan_mass
                                col_index = df_all.columns.get_loc("Nama Pemesan") + 1
                                update_requests.append((row_number, col_index, nilai))
                            if admin_mass or kosongkan_admin:
                                nilai = "" if kosongkan_admin else admin_mass
                                col_index = df_all.columns.get_loc("Admin") + 1
                                update_requests.append((row_number, col_index, nilai))
                
                            count += 1
                
                        # --- Eksekusi batch update agar cepat ---
                        if update_requests:
                            batch_data = [
                                {
                                    "range": gspread.utils.rowcol_to_a1(r, c),
                                    "values": [[v]]
                                }
                                for r, c, v in update_requests
                            ]

                            worksheet.batch_update(batch_data)
                            st.success(f"✅ {count} baris berhasil diperbarui di Google Sheets (batch update).")
                
                        if gagal:
                            st.warning(f"⚠️ {gagal} baris tidak ditemukan di GSheets.")
                            with st.expander("🔍 Lihat baris yang tidak ditemukan"):
                                st.json(tidak_ditemukan)
                
                        if duplikat:
                            st.warning(f"⚠️ {duplikat} baris dilewati karena duplikasi data.")
                
                        if count == 0 and gagal == 0:
                            st.info("ℹ️ Tidak ada data yang diproses.")
                
                        st.cache_data.clear()
                        progress.empty()
                
                    except Exception as e:
                        st.error(f"❌ Gagal update massal: {e}")

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
        if total_harga_jual >= MAX_TOTAL:
            st.success(f"✅ Total penjualan mencapai Rp {total_harga_jual:,.0f} (batas 25 juta tercapai)")
        elif total_harga_jual >= MAX_TOTAL * 0.95:
            st.warning(f"⚠️ Total penjualan mendekati batas: Rp {total_harga_jual:,.0f}")
        
        # === Hitung total harga jual data yang belum punya invoice ===
        uninvoice_df = df[
            (df["Tgl Pemesanan"] >= tanggal_range[0]) &
            (df["Tgl Pemesanan"] <= tanggal_range[1]) &
            (
                df["No Invoice"].isna() |
                (df["No Invoice"].astype(str).str.strip() == "")
            )
        ]
        if nama_filter:
            uninvoice_df = uninvoice_df[uninvoice_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
        
        # Fungsi bantu parsing harga jual
        def parse_harga(harga_str):
            if pd.isna(harga_str):
                return 0
            s = str(harga_str).replace('Rp', '').replace('.', '').replace(',', '').strip()
            try:
                return float(s)
            except:
                return 0
        
        total_uninvoice = uninvoice_df["Harga Jual"].apply(parse_harga).sum()
        
        # Tampilkan notifikasi di sidebar
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 💰 Belum dibuatkan Invoice")
            st.info(f"Total penjualan tanpa invoice: **Rp {total_uninvoice:,.0f}**")
            if total_uninvoice >= 25_000_000:
                st.success("✅ Sudah mencapai 25 juta")
            elif total_uninvoice >= 23_000_000:
                st.warning("⚠️ Hampir mencapai 25 juta")

# === Tombol Aksi ===
        col_pdf, col_excel, col_email = st.columns(3)
    
        # Inisialisasi nomor invoice unik di session state jika belum ada
        if 'current_unique_invoice_no' not in st.session_state:
            st.session_state.current_unique_invoice_no = now.strftime("%y%m%d%H%M%S")
    
        # Generate nama file untuk PDF dan Excel
        current_pdf_filename = f"INV_{st.session_state.current_unique_invoice_no}.pdf"
        current_excel_filename = f"INV_{st.session_state.current_unique_invoice_no}.xlsx"
    
        # Simpan nama file terakhir yang dibuat di session state untuk pengiriman email
        if 'last_generated_pdf_path' not in st.session_state:
            st.session_state.last_generated_pdf_path = None
    
        with col_pdf:
            status_lunas = st.radio("Status Pembayaran:", ("Belum Lunas", "Lunas"))    
            if st.button("📄 Buat Invoice PDF"):
                if not selected_data.empty:
        
                    records = selected_data.to_dict(orient="records")
        
                    # Tanggal invoice → ambil dari kolom Tgl Pemesanan baris pertama
                    tanggal_invoice = pd.to_datetime(selected_data["Tgl Pemesanan"].iloc[0])
        
                    # Buat nomor invoice unik
                    st.session_state.current_unique_invoice_no = now.strftime("%y%m%d%H%M%S")
                    current_pdf_filename = f"INV_{st.session_state.current_unique_invoice_no}.pdf"
        
                    # === PEMANGGILAN FUNGSI YANG BARU ===
                    pdf_path_generated = buat_invoice_pdf(
                        records,
                        tanggal_invoice,
                        st.session_state.current_unique_invoice_no,
                        current_pdf_filename,
                        logo_path="assets/Logo Perusahaan.jpeg",
                        ttd_path="ttd.png",
                        status_lunas=status_lunas
                    )

        
                    with open(pdf_path_generated, "rb") as f:
                        st.download_button(
                            "💾 Unduh Invoice PDF",
                            f,
                            file_name=current_pdf_filename,
                            mime="application/pdf"
                        )
        
                    st.success(f"✅ Invoice PDF berhasil dibuat: {current_pdf_filename}")
                    st.session_state.last_generated_pdf_path = pdf_path_generated
        
                else:
                    st.warning("Tidak ada data yang dipilih untuk dibuat invoice PDF.")

    
        with col_excel:
            # === Buat Excel ===
            if st.button("📄 Buat Excel"):
                if not selected_data.empty:
                    excel_data = selected_data.drop(columns=["Pilih", "Harga Beli", "Laba", "Admin", "% Laba", "Nama Pemesan"], errors="ignore")
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
    ## Fungsi `buat_invoice_pdf` (Direvisi)
    

# Contoh fungsi parsing untuk kereta dan hotel (sesuaikan dengan fungsi asli kamu)
def parsing_ticket(text, tipe):
    if tipe == "Kereta":
        return parse_input_dynamic(text)  # ganti dengan fungsi parsing tiket kereta kamu
    elif tipe == "Hotel":
        return parse_evoucher_text(text)  # fungsi parsing hotel yang sudah ada

def generate_ticket(data, tipe):
    if tipe == "Kereta":
        return generate_eticket(data)  # fungsi generate tiket kereta kamu
    elif tipe == "Hotel":
        return generate_evoucher_html(data)  # fungsi generate voucher hotel kamu
        
st.markdown("""<hr style="border-top: 1px solid #7f8c8d;">""", unsafe_allow_html=True)

with st.expander("🎫 Generator E-Tiket"):

    # Pilihan tipe tiket
    tipe_tiket = st.radio("Pilih tipe tiket:", ["Kereta", "Hotel"], key="tipe_tiket_radio")
    
    st.session_state['tipe_tiket'] = tipe_tiket

    # Template default berdasarkan tipe tiket
    if tipe_tiket == "Hotel":
        default_text = "Order ID:\nItinerary ID:\n\nHarga "
    else:
        default_text = "Kode booking: "

    # Inisialisasi text_area hanya sekali per tipe (hindari reset)
    input_key = f"input_text_{tipe_tiket}"
    if input_key not in st.session_state:
        st.session_state[input_key] = default_text

    # Area input teks
    input_text = st.text_area(
        f"Tempelkan teks tiket {tipe_tiket}",
        value=st.session_state[input_key],
        height=300,
        key=input_key
    )

    # Tombol generate
    if st.button("Generate Tiket"):
        if input_text.strip():
            data = parsing_ticket(input_text, tipe_tiket)
            st.session_state['last_data'] = data
            st.session_state['tipe_tiket'] = tipe_tiket
        else:
            st.warning("Silakan masukkan data tiket terlebih dahulu.")

    # Tampilkan hasil jika sudah ada
    if 'last_data' in st.session_state and st.session_state.get('tipe_tiket') == tipe_tiket:
        data = st.session_state['last_data']
        try:
            html = generate_ticket(data, tipe_tiket)
            st.components.v1.html(html, height=800, scrolling=True)
        except Exception as e:
            st.warning("⚠️ Gagal membuat tampilan tiket. Periksa apakah semua data penting sudah terisi, seperti 'Harga'.")



with st.expander("🎫 Generator E-Tiket + Simpan Data"):
    tipe_tiket = st.radio("Pilih tipe tiket:", ["Kereta", "Hotel", "Pesawat"], key="tipe_tiket_simpan")
    input_text = st.text_area(f"Tempelkan teks tiket {tipe_tiket}", height=300, key="text_tiket")

    if st.button("🖨️ Generate Tiket & Parse Data"):
        if input_text.strip():
            # 1. Generate visual tiket
            data = parsing_ticket(input_text, tipe_tiket)
            html = generate_ticket(data, tipe_tiket)
            st.session_state['last_ticket_html'] = html
            st.session_state['last_ticket_data'] = input_text  # raw text

            # 2. Jalankan proses parsing data
            parsed_result = process_ocr_unified(input_text)
            st.write("🚧 Parse output raw:", parsed_result)
            if isinstance(parsed_result, list):
                df_ocr = pd.DataFrame(parsed_result)
                st.write("🚧 DataFrame tanpa filter kolom:", df_ocr)
            elif isinstance(parsed_result, pd.DataFrame):
                df_ocr = parsed_result.copy()
            else:
                st.warning("⚠️ Parsing tidak menghasilkan data yang dikenali.")
                st.stop()

            # Normalisasi kolom sesuai format
            expected_cols = [
                "Tgl Pemesanan", "Tgl Berangkat", "Kode Booking",
                "No Penerbangan / Hotel / Kereta", "Durasi",
                "Nama Customer", "Rute", "Harga Beli", "Harga Jual", "Laba",
                "Tipe", "BF/NBF", "No Invoice", "Keterangan",
                "Nama Pemesan", "Admin", "% Laba"
            ]
            for col in expected_cols:
                if col not in df_ocr.columns:
                    df_ocr[col] = ""

            df_ocr = df_ocr[expected_cols]
            st.session_state.ocr_preview_df = df_ocr
        else:
            st.warning("Silakan masukkan data tiket terlebih dahulu.")

    # Tampilkan tiket jika sudah tersedia
    if st.session_state.get('last_ticket_html'):
        st.components.v1.html(st.session_state['last_ticket_html'], height=800, scrolling=True)

    # Tampilkan DataFrame hasil parsing
    if "ocr_preview_df" in st.session_state:
        df = st.session_state.ocr_preview_df

        st.markdown("### 🧾 Data Hasil Parsing Tiket")

        edit_mode = st.checkbox("Edit Manual", value=st.session_state.get("edit_mode_ocr", False))

        if edit_mode:
            st.session_state.edit_mode_ocr = True

            row_index = st.number_input("Pilih baris ke-", min_value=0, max_value=len(df)-1, step=1)
            row_data = df.iloc[row_index].to_dict()
            updated_row = {}

            for col, val in row_data.items():
                if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                    try:
                        val = pd.to_datetime(val).date() if val else pd.Timestamp.today().date()
                    except:
                        val = pd.Timestamp.today().date()
                    new_val = st.date_input(col, value=val)
                else:
                    new_val = st.text_input(col, value=str(val) if pd.notna(val) else "")
                updated_row[col] = new_val

            if st.button("💾 Simpan Perubahan Baris"):
                for col in updated_row:
                    df.at[row_index, col] = updated_row[col]
                st.session_state.ocr_preview_df = df
                st.session_state.edit_mode_ocr = False
                st.success("✅ Perubahan disimpan.")
                st.rerun()

        else:
            st.dataframe(df, use_container_width=True)

            if st.button("📤 Simpan ke Database / GSheet"):
                save_gsheet(df)
                st.success("✅ Data berhasil disimpan.")
                st.session_state.pop("ocr_preview_df", None)
                st.session_state.pop("last_ticket_html", None)
                st.rerun()

st.markdown("""<hr style="border-top: 1px solid #7f8c8d;">""", unsafe_allow_html=True)
#=================================================================================================================================================================
from prophet import Prophet
from prophet.plot import plot_plotly
import plotly.graph_objects as go

with st.expander("📘 Laporan Keuangan Lengkap"):
    st.markdown("### 📊 Filter Laporan")

    df["Tgl Pemesanan"] = pd.to_datetime(df["Tgl Pemesanan"], errors="coerce")

    filter_mode = st.radio(
        "Pilih Jenis Filter Tanggal", 
        ["📆 Rentang Tanggal", "🗓️ Bulanan", "📅 Tahunan"], 
        horizontal=True,
        key="filter_tanggal_mode"
    )

    df_filtered = df.copy()

    if filter_mode == "📆 Rentang Tanggal":
        tgl_awal = st.date_input("Tanggal Awal", date.today().replace(day=1), key="tgl_awal_input")
        tgl_akhir = st.date_input("Tanggal Akhir", date.today(), key="tgl_akhir_input")
        if tgl_awal > tgl_akhir:
            tgl_awal, tgl_akhir = tgl_akhir, tgl_awal
        df_filtered = df[
            (df["Tgl Pemesanan"] >= pd.to_datetime(tgl_awal)) &
            (df["Tgl Pemesanan"] <= pd.to_datetime(tgl_akhir))
        ]

    elif filter_mode == "🗓️ Bulanan":
        bulan_nama = {
            "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
            "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
            "September": 9, "Oktober": 10, "November": 11, "Desember": 12
        }
        bulan_label = list(bulan_nama.keys())
        bulan_pilihan = st.selectbox("Pilih Bulan", bulan_label, index=date.today().month - 1, key="filter_bulan_input")
        tahun_bulan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan"].dt.year.dropna().unique(), reverse=True), key="filter_tahun_bulanan")
        df_filtered = df[
            (df["Tgl Pemesanan"].dt.month == bulan_nama[bulan_pilihan]) &
            (df["Tgl Pemesanan"].dt.year == tahun_bulan)
        ]

    elif filter_mode == "📅 Tahunan":
        tahun_pilihan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan"].dt.year.dropna().unique(), reverse=True), key="filter_tahun_tahunan")
        df_filtered = df[df["Tgl Pemesanan"].dt.year == tahun_pilihan]


    # Tambahan filter Pemesan dan Admin
    st.markdown("### 🧍 Filter Tambahan")
    pemesan_list = ["(Semua)"] + sorted(df["Nama Pemesan"].dropna().unique())
    admin_list = ["(Semua)"] + sorted(df["Admin"].dropna().unique())

    selected_pemesan = st.selectbox("Nama Pemesan", pemesan_list)
    selected_admin = st.selectbox("Admin", admin_list)

    if selected_pemesan != "(Semua)":
        df_filtered = df_filtered[df_filtered["Nama Pemesan"] == selected_pemesan]
    if selected_admin != "(Semua)":
        df_filtered = df_filtered[df_filtered["Admin"] == selected_admin]

    if df_filtered.empty:
        st.warning("❌ Tidak ada data sesuai filter.")
    else:
        # Parse harga jika masih string
        def parse_harga(h):
            if pd.isna(h): return 0
            s = str(h).replace("Rp", "").replace(".", "").replace(",", "").strip()
            try: return float(s)
            except: return 0

        df_filtered["Harga Jual (Num)"] = df_filtered["Harga Jual"].apply(parse_harga)
        df_filtered["Harga Beli (Num)"] = df_filtered["Harga Beli"].apply(parse_harga)

        total_jual = df_filtered["Harga Jual (Num)"].sum()
        total_beli = df_filtered["Harga Beli (Num)"].sum()
        total_profit = total_jual - total_beli

        col1, col2 = st.columns([1, 1])
        col1.metric("💰 Total Penjualan", f"Rp {int(total_jual):,}".replace(",", "."))
        col2.metric("💸 Total Pembelian", f"Rp {int(total_beli):,}".replace(",", "."))
        with col2:
            st.metric("📈 Profit", f"Rp {int(total_profit):,}".replace(",", "."))
            
        # Grafik Tren Penjualan
        st.markdown("### 📈 Grafik Tren Penjualan")
        df_chart = df_filtered.groupby("Tgl Pemesanan")["Harga Jual (Num)"].sum().reset_index()
        st.line_chart(df_chart.rename(columns={"Tgl Pemesanan": "index"}).set_index("index"))

        # Rekap tambahan bulanan per tanggal
        if filter_mode == "🗓️ Bulanan":
            df_filtered["Tanggal"] = df_filtered["Tgl Pemesanan"].dt.day
            summary_bulanan = pd.DataFrame(index=["Total Penjualan", "Total Pembelian", "Laba"])
            for day in range(1, 32):
                day_data = df_filtered[df_filtered["Tanggal"] == day]
                jual = day_data["Harga Jual (Num)"].sum()
                beli = day_data["Harga Beli (Num)"].sum()
                laba = jual - beli
                summary_bulanan[day] = [jual, beli, laba]

            st.markdown("### 📅 Rekap Bulanan per Tanggal")
            st.dataframe(summary_bulanan.style.format("Rp {:,.0f}"), use_container_width=True)

        # Rekap tambahan tahunan per bulan
        if filter_mode == "📅 Tahunan":
            df_filtered["Bulan"] = df_filtered["Tgl Pemesanan"].dt.month
            nama_bulan = {
                1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
                7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
            }

            summary_tahunan = pd.DataFrame(index=["Total Penjualan", "Total Pembelian", "Laba"])
            for month in range(1, 13):
                month_data = df_filtered[df_filtered["Bulan"] == month]
                jual = month_data["Harga Jual (Num)"].sum()
                beli = month_data["Harga Beli (Num)"].sum()
                laba = jual - beli
                summary_tahunan[nama_bulan[month]] = [jual, beli, laba]

            st.markdown("### 📆 Rekap Tahunan per Bulan")
            st.dataframe(summary_tahunan.style.format("Rp {:,.0f}"), use_container_width=True)
            
        # Ringkasan per Admin
        st.markdown("### 🧑‍💼 Ringkasan per Admin")
        st.dataframe(
            df_filtered.groupby("Admin")["Harga Jual (Num)"].sum().reset_index(name="Total Penjualan"),
            use_container_width=True
        )

        # Ringkasan per Pemesan
        st.markdown("### 👥 Ringkasan per Pemesan")
        st.dataframe(
            df_filtered.groupby("Nama Pemesan")["Harga Jual (Num)"].sum().reset_index(name="Total Penjualan"),
            use_container_width=True
        )
        
        # Tabel detail
        with st.expander("📄 Lihat Tabel Detail"):
            st.dataframe(df_filtered, use_container_width=True)
        st.markdown("### 🤖 Analisa Keuangan Otomatis")

        avg_profit = df_filtered["Harga Jual (Num)"].sum() - df_filtered["Harga Beli (Num)"].sum()
        num_days = df_filtered["Tgl Pemesanan"].dt.date.nunique()
        avg_profit_per_day = avg_profit / num_days if num_days else 0
        
        top_admin = df_filtered.groupby("Admin")["Harga Jual (Num)"].sum().idxmax()
        top_pemesan = df_filtered.groupby("Nama Pemesan")["Harga Jual (Num)"].sum().idxmax()
        
        max_day = df_filtered.groupby("Tgl Pemesanan")["Harga Jual (Num)"].sum().idxmax()
        max_day_val = df_filtered.groupby("Tgl Pemesanan")["Harga Jual (Num)"].sum().max()
        
        st.markdown(f"""
        - 💼 **Rata-rata laba harian**: Rp {int(avg_profit_per_day):,}.  
        - 🏆 **Admin dengan penjualan tertinggi**: {top_admin}  
        - 🙋 **Pemesan paling aktif**: {top_pemesan}  
        - 📅 **Hari dengan omset tertinggi**: {max_day.date()} sebesar Rp {int(max_day_val):,}  
        """)
        
        with st.expander("🔮 Prediksi Omzet / Laba per Bulan (Dinamis)"):
            df_prophet = df_filtered.copy()
            df_prophet = df_prophet.groupby("Tgl Pemesanan")[["Harga Jual (Num)", "Harga Beli (Num)"]].sum().reset_index()
            df_prophet["ds"] = df_prophet["Tgl Pemesanan"]
            df_prophet["y"] = df_prophet["Harga Jual (Num)"] - df_prophet["Harga Beli (Num)"]
        
            # Gunakan hanya data 3 bulan terakhir untuk pelatihan (opsional)
            if len(df_prophet) >= 90:
                df_prophet = df_prophet[df_prophet["ds"] >= df_prophet["ds"].max() - pd.DateOffset(months=3)]
        
            model = Prophet()
            model.fit(df_prophet[["ds", "y"]])
        
            future = model.make_future_dataframe(periods=90)  # 3 bulan ke depan
            forecast = model.predict(future)
        
            # 🎛️ Input UI: Pilih bulan dan tahun target
            all_months = [f"{i:02d}" for i in range(1, 13)]
            month_map = {
                "01": "Januari", "02": "Februari", "03": "Maret", "04": "April", "05": "Mei", "06": "Juni",
                "07": "Juli", "08": "Agustus", "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
            }
            month_select = st.selectbox("📅 Pilih Bulan", options=all_months, format_func=lambda x: month_map[x])
            year_select = st.selectbox("🗓️ Pilih Tahun", options=sorted(forecast["ds"].dt.year.unique()))
        
            # 🧠 Filter forecast ke bulan & tahun yang dipilih
            forecast_selected = forecast[
                (forecast["ds"].dt.month == int(month_select)) &
                (forecast["ds"].dt.year == year_select)
            ]
        
            if forecast_selected.empty:
                st.warning("📭 Tidak ada prediksi tersedia untuk bulan & tahun yang dipilih.")
            else:
                total_yhat = forecast_selected["yhat"].sum()
                min_yhat = forecast_selected["yhat"].min()
                max_yhat = forecast_selected["yhat"].max()
                delta_trend = forecast_selected["trend"].iloc[-1] - forecast_selected["trend"].iloc[0]
        
                # Tampilkan grafik prediksi bulan tersebut
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=forecast_selected["ds"], y=forecast_selected["yhat"], name="Prediksi Laba"))
                fig.update_layout(title=f"📈 Prediksi Laba - {month_map[month_select]} {year_select}")
                st.plotly_chart(fig, use_container_width=True)
        
                # 🧾 Ringkasan
                st.markdown("### 📊 Ringkasan Prediksi Bulanan:")
                st.markdown(f"""
                - 🗓️ Bulan dipilih: **{month_map[month_select]} {year_select}**
                - 📈 **Total laba diprediksi**: Rp {int(total_yhat):,}
                - 🔼 **Hari terbaik (estimasi)**: Rp {int(max_yhat):,}
                - 🔽 **Hari terendah (estimasi)**: Rp {int(min_yhat):,}
                - 📊 **Tren bulan ini**: {'meningkat' if delta_trend > 0 else 'menurun' if delta_trend < 0 else 'stabil'} (Δ Rp {int(delta_trend):,})
                """)
        
                # Perbandingan dengan bulan sebelumnya
                prev_month = int(month_select) - 1 if int(month_select) > 1 else 12
                prev_year = year_select if int(month_select) > 1 else year_select - 1
                forecast_prev = forecast[
                    (forecast["ds"].dt.month == prev_month) &
                    (forecast["ds"].dt.year == prev_year)
                ]
                if not forecast_prev.empty:
                    total_prev = forecast_prev["yhat"].sum()
                    delta = total_yhat - total_prev
                    st.markdown(f"📉 **Perbandingan dengan bulan sebelumnya ({month_map[str(prev_month).zfill(2)]} {prev_year})**: Rp {int(total_prev):,} → Rp {int(total_yhat):,} (Δ Rp {int(delta):,})")


        with st.expander("📊 Perbandingan Kinerja Bulanan / YTD"):
            df_filtered["Bulan"] = df_filtered["Tgl Pemesanan"].dt.to_period("M")
            df_monthly = df_filtered.groupby("Bulan")[["Harga Jual (Num)", "Harga Beli (Num)"]].sum().reset_index()
            df_monthly["Laba"] = df_monthly["Harga Jual (Num)"] - df_monthly["Harga Beli (Num)"]
            df_monthly["Bulan"] = df_monthly["Bulan"].astype(str)
        
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_monthly["Bulan"], y=df_monthly["Harga Jual (Num)"], name="Penjualan"))
            fig.add_trace(go.Bar(x=df_monthly["Bulan"], y=df_monthly["Harga Beli (Num)"], name="Pembelian"))
            fig.add_trace(go.Scatter(x=df_monthly["Bulan"], y=df_monthly["Laba"], mode="lines+markers", name="Laba"))
        
            fig.update_layout(barmode='group', title="Kinerja Bulanan", xaxis_title="Bulan", yaxis_title="Rp")
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("🚨 Deteksi Anomali Penjualan"):
            df_anomali = df_filtered.groupby("Tgl Pemesanan")["Harga Jual (Num)"].sum().reset_index()
            q1 = df_anomali["Harga Jual (Num)"].quantile(0.25)
            q3 = df_anomali["Harga Jual (Num)"].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
        
            anomalies = df_anomali[
                (df_anomali["Harga Jual (Num)"] < lower_bound) |
                (df_anomali["Harga Jual (Num)"] > upper_bound)
            ]
        
            st.dataframe(anomalies, use_container_width=True)
            st.markdown(f"🔍 Ditemukan **{len(anomalies)}** hari dengan penjualan di luar batas normal (IQR).")

        with st.expander("💼 Segmentasi Produk berdasarkan Profitabilitas"):
            if "Tipe" in df_filtered.columns:
                df_segment = df_filtered.copy()
                df_segment["Profit"] = df_segment["Harga Jual (Num)"] - df_segment["Harga Beli (Num)"]
                segment = df_segment.groupby("Tipe")[["Harga Jual (Num)", "Harga Beli (Num)", "Profit"]].sum().reset_index()
                segment["Profit Margin (%)"] = 100 * segment["Profit"] / segment["Harga Jual (Num)"]
        
                st.dataframe(segment.sort_values("Profit", ascending=False), use_container_width=True)
        
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=segment["Tipe"],
                    y=segment["Profit Margin (%)"],
                    name="Margin (%)"
                ))
                fig.update_layout(title="Segmentasi Produk: Profit Margin", xaxis_title="Produk", yaxis_title="Margin %")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Kolom 'Tipe' tidak tersedia.")


#=================================================================================================================================================================
import streamlit as st
import pandas as pd
import holidays
import matplotlib.pyplot as plt

with st.expander("📊 Analisa Laporan Keuangan"):

    # Pastikan kolom datetime sudah benar
    df_filtered["Tgl Pemesanan"] = pd.to_datetime(df_filtered["Tgl Pemesanan"], errors="coerce")
    
    if "Harga Jual" in df_filtered.columns:
        df_filtered["Harga Jual (Num)"] = (
            df_filtered["Harga Jual"]
            .astype(str)
            .replace("[Rp.,\s]", "", regex=True)
            .astype(float)
        )
    else:
        st.error("❌ Kolom 'Harga Jual' tidak ditemukan. Tidak bisa melanjutkan analisa.")

    years = df_filtered["Tgl Pemesanan"].dt.year.dropna().unique()
    id_holidays = holidays.Indonesia(years=years)

    # ----- HARiAN -----
    df_daily = (
        df_filtered.groupby("Tgl Pemesanan")["Harga Jual (Num)"]
        .sum()
        .reset_index()
        .sort_values("Tgl Pemesanan")
    )
    df_daily["Pct_Change"] = df_daily["Harga Jual (Num)"].pct_change() * 100
    df_daily["Is_Holiday"] = df_daily["Tgl Pemesanan"].isin(id_holidays)
    df_daily["Is_Weekend"] = df_daily["Tgl Pemesanan"].dt.dayofweek >= 5  # Sabtu=5, Minggu=6
    df_daily["Near_Holiday"] = df_daily["Is_Holiday"] | df_daily["Is_Weekend"]

    threshold_drop_daily = -20
    penurunan_signifikan_harian = df_daily[df_daily["Pct_Change"] <= threshold_drop_daily]

    # ----- BULANAN -----
    df_filtered["YearMonth"] = df_filtered["Tgl Pemesanan"].dt.to_period("M")
    df_monthly = (
        df_filtered.groupby("YearMonth")["Harga Jual (Num)"]
        .sum()
        .reset_index()
        .sort_values("YearMonth")
    )
    df_monthly["Pct_Change"] = df_monthly["Harga Jual (Num)"].pct_change() * 100
    df_monthly["MonthStart"] = df_monthly["YearMonth"].dt.to_timestamp()
    
    def check_month_holiday(ts):
        return any([(ts + pd.Timedelta(days=i)) in id_holidays for i in range(31)])
    
    df_monthly["Is_Holiday_Month"] = df_monthly["MonthStart"].apply(check_month_holiday).astype(bool)
    df_monthly["Is_Weekend_Month"] = (df_monthly["MonthStart"].dt.weekday >= 5).astype(bool)
    df_monthly["Near_Holiday"] = df_monthly["Is_Holiday_Month"] | df_monthly["Is_Weekend_Month"]
    
    threshold_drop_monthly = -15
    penurunan_signifikan_bulanan = df_monthly[df_monthly["Pct_Change"] <= threshold_drop_monthly]

    # ----- TAHUNAN -----
    df_filtered["Year"] = df_filtered["Tgl Pemesanan"].dt.year
    df_yearly = (
        df_filtered.groupby("Year")["Harga Jual (Num)"]
        .sum()
        .reset_index()
        .sort_values("Year")
    )
    df_yearly["Pct_Change"] = df_yearly["Harga Jual (Num)"].pct_change() * 100

    def check_year_holiday(y):
        # Cek apakah ada hari libur di tahun tersebut
        # Diasumsikan selalu ada, tapi bisa dioptimasi sesuai kebutuhan
        return any([date.year == y for date in id_holidays])

    df_yearly["Is_Holiday_Year"] = df_yearly["Year"].apply(check_year_holiday)
    df_yearly["Near_Holiday"] = df_yearly["Is_Holiday_Year"]  # Tahun lebih longgar, cuma cek ada libur

    threshold_drop_yearly = -10
    penurunan_signifikan_tahunan = df_yearly[df_yearly["Pct_Change"] <= threshold_drop_yearly]

    # --- Output Analisa ---
    st.markdown("### 📉 Penurunan Signifikan Harian ( > 20% drop )")
    if not penurunan_signifikan_harian.empty:
        for _, row in penurunan_signifikan_harian.iterrows():
            date_str = row["Tgl Pemesanan"].strftime("%Y-%m-%d")
            drop = row["Pct_Change"]
            near_holiday = "Ya" if row["Near_Holiday"] else "Tidak"
            st.write(f"- 📅 {date_str} : Penurunan {drop:.2f}% dari hari sebelumnya.")
            st.write(f"  - Dekat Hari Libur / Weekend? **{near_holiday}**")
    else:
        st.write("✅ Tidak ada penurunan signifikan harian terdeteksi.")

    st.markdown("### 📉 Penurunan Signifikan Bulanan ( > 15% drop )")
    if not penurunan_signifikan_bulanan.empty:
        for _, row in penurunan_signifikan_bulanan.iterrows():
            month_str = row["YearMonth"].strftime("%Y-%m")
            drop = row["Pct_Change"]
            near_holiday = "Ya" if row["Near_Holiday"] else "Tidak"
            st.write(f"- 🗓️ {month_str} : Penurunan {drop:.2f}% dari bulan sebelumnya.")
            st.write(f"  - Bulan ada hari libur / weekend panjang? **{near_holiday}**")
    else:
        st.write("✅ Tidak ada penurunan signifikan bulanan terdeteksi.")

    st.markdown("### 📉 Penurunan Signifikan Tahunan ( > 10% drop )")
    if not penurunan_signifikan_tahunan.empty:
        for _, row in penurunan_signifikan_tahunan.iterrows():
            year_str = str(int(row["Year"]))
            drop = row["Pct_Change"]
            near_holiday = "Ya" if row["Near_Holiday"] else "Tidak"
            st.write(f"- 📆 {year_str} : Penurunan {drop:.2f}% dari tahun sebelumnya.")
            st.write(f"  - Tahun dengan libur nasional? **{near_holiday}**")
    else:
        st.write("✅ Tidak ada penurunan signifikan tahunan terdeteksi.")

    # --- Rekomendasi ---
    st.markdown("### 💡 Rekomendasi:")
    if not penurunan_signifikan_harian.empty or not penurunan_signifikan_bulanan.empty or not penurunan_signifikan_tahunan.empty:
        st.markdown("""
        - Tinjau aktivitas pemasaran dan operasional di tanggal/bulan/tahun yang mengalami penurunan.
        - Periksa apakah penurunan terkait dengan hari libur panjang, weekend, atau faktor eksternal lain.
        - Buat strategi promosi yang menyasar periode rentan tersebut.
        - Analisa faktor internal seperti stok, harga, layanan untuk menemukan penyebab penurunan.
        """)
    else:
        st.markdown("Tidak ada penurunan signifikan, pertahankan strategi yang berjalan.")

    # --- Visualisasi ---
    st.markdown("### 📈 Grafik Penjualan Harian dengan Penurunan & Hari Libur")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_daily["Tgl Pemesanan"], df_daily["Harga Jual (Num)"], label="Penjualan Harian", marker='o')
    ax.scatter(penurunan_signifikan_harian["Tgl Pemesanan"], penurunan_signifikan_harian["Harga Jual (Num)"], color='red', label="Penurunan Signifikan")
    holidays_weekends = df_daily[df_daily["Near_Holiday"]]
    ax.scatter(holidays_weekends["Tgl Pemesanan"], holidays_weekends["Harga Jual (Num)"], color='green', alpha=0.3, label="Hari Libur / Weekend")
    ax.set_xlabel("Tanggal")
    ax.set_ylabel("Total Penjualan")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

    st.markdown("### 📈 Grafik Penjualan Bulanan")
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.plot(df_monthly["YearMonth"].dt.to_timestamp(), df_monthly["Harga Jual (Num)"], label="Penjualan Bulanan", marker='o')
    ax2.scatter(penurunan_signifikan_bulanan["MonthStart"], penurunan_signifikan_bulanan["Harga Jual (Num)"], color='red', label="Penurunan Signifikan")
    ax2.set_xlabel("Bulan")
    ax2.set_ylabel("Total Penjualan")
    ax2.legend()
    ax2.grid(True)
    st.pyplot(fig2)

    st.markdown("### 📈 Grafik Penjualan Tahunan")
    fig3, ax3 = plt.subplots(figsize=(10, 4))
    ax3.plot(df_yearly["Year"], df_yearly["Harga Jual (Num)"], label="Penjualan Tahunan", marker='o')
    ax3.scatter(penurunan_signifikan_tahunan["Year"], penurunan_signifikan_tahunan["Harga Jual (Num)"], color='red', label="Penurunan Signifikan")
    ax3.set_xlabel("Tahun")
    ax3.set_ylabel("Total Penjualan")
    ax3.legend()
    ax3.grid(True)
    st.pyplot(fig3)

#===============================================================================================================================
import pandas as pd
import streamlit as st

def read_existing_keys_from_sheet(worksheet, key_cols):
    """Baca data kolom kunci dari worksheet Google Sheets sebagai DataFrame."""
    data = worksheet.get_all_values()
    if not data or len(data) < 2:
        return pd.DataFrame(columns=key_cols)

    header = data[0]
    rows = data[1:]
    key_indices = []
    for k in key_cols:
        if k not in header:
            st.error(f"Kolom '{k}' tidak ditemukan di worksheet.")
            return pd.DataFrame(columns=key_cols)
        key_indices.append(header.index(k))

    filtered_rows = [[r[i] for i in key_indices] for r in rows]
    df = pd.DataFrame(filtered_rows, columns=key_cols)

    # Parsing tipe data khusus jika perlu
    if "Tanggal" in key_cols:
        df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors='coerce').dt.date
    if "Jumlah" in key_cols:
        df["Jumlah"] = pd.to_numeric(df["Jumlah"], errors='coerce')

    return df


def create_dupe_key(df, key_cols):
    """Buat kolom duplikat key sebagai penggabungan kolom kunci."""
    return df[key_cols].astype(str).agg("__".join, axis=1)


def save_kas(df: pd.DataFrame, worksheet):
    """
    Simpan data kas ke Google Sheets dengan pengecekan duplikat berdasarkan kolom kunci.
    df: DataFrame berisi data kas baru
    worksheet: objek gspread worksheet
    """
    key_cols = ["Tanggal", "Tipe", "Kategori", "No Invoice", "Jumlah"]

    if df is None or df.empty:
        st.warning("❌ Data kosong atau invalid.")
        return

    # Parsing kolom penting sesuai tipe data
    df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors='coerce').dt.date
    df["Jumlah"] = pd.to_numeric(df["Jumlah"], errors='coerce')

    # Baca data kunci yang sudah ada di sheet
    existing_df = read_existing_keys_from_sheet(worksheet, key_cols)

    # Buat duplikat key
    df["dupe_key"] = create_dupe_key(df, key_cols)
    existing_df["dupe_key"] = create_dupe_key(existing_df, key_cols)

    # Cari duplikat
    dupes = df[df["dupe_key"].isin(set(existing_df["dupe_key"]))]
    if not dupes.empty:
        st.error("❌ Ditemukan duplikat data yang sudah ada di GSheet:")
        st.dataframe(dupes[key_cols])
        st.warning("Mohon periksa data sebelum mengirim ulang.")
        return

    # Hapus kolom bantu sebelum simpan
    df = df.drop(columns=["dupe_key"])

    # Append ke Google Sheets
    from sheets_utility import append_dataframe_to_sheet  # pastikan import sesuai lokasi utilitas
    append_dataframe_to_sheet(df, worksheet)
    st.success("✅ Berhasil simpan data Arus Kas ke Google Sheets.")

#=============================================================================================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime

SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# ---------------------------
# Helper function format Rupiah
# ---------------------------
def format_rp(x):
    return f"Rp {x:,.0f}"

# ---------------------------
# Input Manual Cashflow
# ---------------------------
def clean_price_column(col):
    """Bersihkan kolom harga: hapus non-digit, ubah NaN menjadi 0, konversi ke float."""
    col = col.fillna("").astype(str)
    col = col.str.replace(r"[^\d]", "", regex=True)
    col = col.replace("", "0")
    return col.astype(float)

# ---------------------------
# Parse otomatis cashflow dengan Invoice_Key
# ---------------------------
def parse_cashflow_from_data(df_data, df_cashflow_existing):
    """
    Menghasilkan DataFrame cashflow otomatis dari Data, menghindari duplikasi invoice,
    agregasi per pemesan + invoice (Invoice_Key), dan aman untuk transaksi tanpa invoice.
    """
    if df_data.empty:
        return pd.DataFrame(columns=["Tanggal","Tipe","Kategori","No Invoice","Keterangan","Jumlah","Status","Sumber"])

    # Bersihkan harga
    df_data["Harga Beli"] = clean_price_column(df_data.get("Harga Beli", pd.Series([0]*len(df_data))))
    df_data["Harga Jual"] = clean_price_column(df_data.get("Harga Jual", pd.Series([0]*len(df_data))))

    # Pastikan kolom penting
    df_data["No Invoice"] = df_data["No Invoice"].fillna("").astype(str)
    df_data["Tgl Pemesanan"] = pd.to_datetime(df_data["Tgl Pemesanan"], dayfirst=True, errors="coerce")
    df_data["Keterangan"] = df_data.get("Keterangan", "").astype(str)
    df_data["Nama Pemesan"] = df_data.get("Nama Pemesan", "").astype(str)

    # Buat Invoice_Key: Nama Pemesan + No Invoice, atau Nama Pemesan + index jika kosong
    df_data["Invoice_Key"] = df_data.apply(
        lambda x: f"{x['Nama Pemesan']}_MANUAL_{x.name}" if x["No Invoice"]=="" else f"{x['Nama Pemesan']}_{x['No Invoice']}",
        axis=1
    )

    # Ambil daftar invoice_key yang sudah ada di cashflow_existing untuk hindari duplikasi
    existing_keys = set()
    if not df_cashflow_existing.empty:
        # Buat Invoice_Key di existing juga supaya bisa dibandingkan
        df_cashflow_existing["Invoice_Key"] = df_cashflow_existing.apply(
            lambda x: f"{x.get('Nama Pemesan','')}_MANUAL_{x.name}" if x.get("No Invoice","")=="" else f"{x.get('Nama Pemesan','')}_{x.get('No Invoice','')}",
            axis=1
        )
        existing_keys = set(df_cashflow_existing["Invoice_Key"])

    cashflow_rows = []

    # Group berdasarkan Invoice_Key
    grouped = df_data.groupby("Invoice_Key")
    for key, group in grouped:
        if key in existing_keys:
            continue  # skip duplikasi

        tgl = group["Tgl Pemesanan"].min()
        keterangan = "; ".join(group["Keterangan"].unique())
        invoice_no = group["No Invoice"].iloc[0] if group["No Invoice"].iloc[0] else ""
        total_beli = group["Harga Beli"].sum()
        total_jual = group["Harga Jual"].sum()
        status = "Belum Lunas" if any("Belum Lunas" in k for k in group["Keterangan"]) else "Lunas"

        # Baris Keluar (Harga Beli)
        cashflow_rows.append({
            "Tanggal": tgl,
            "Tipe": "Keluar",
            "Kategori": "Penjualan",
            "No Invoice": invoice_no,
            "Keterangan": keterangan,
            "Jumlah": total_beli,
            "Status": status,
            "Sumber": "Data Otomatis",
            "Nama Pemesan": group["Nama Pemesan"].iloc[0],
            "Invoice_Key": key
        })

        # Baris Masuk (Harga Jual) hanya jika Lunas
        if status == "Lunas":
            cashflow_rows.append({
                "Tanggal": tgl,
                "Tipe": "Masuk",
                "Kategori": "Pembayaran Customer",
                "No Invoice": invoice_no,
                "Keterangan": keterangan,
                "Jumlah": total_jual,
                "Status": status,
                "Sumber": "Data Otomatis",
                "Nama Pemesan": group["Nama Pemesan"].iloc[0],
                "Invoice_Key": key
            })

    return pd.DataFrame(cashflow_rows)


# --------------------------
# Input Manual Cashflow
# --------------------------
with st.expander("✏️ Input Data Cashflow Manual"):
    # --- Input Dasar ---
    tanggal = st.date_input("Tanggal", value=date.today(), key="tgl_input")
    tipe = st.selectbox("Tipe", ["Masuk", "Keluar"], key="tipe_input")

    # --- Kategori ---
    kategori_masuk = [
        "Penjualan Tiket Pesawat", "Penjualan Hotel", "Penjualan Kereta",
        "Komisi Agen", "Lain-lain"
    ]
    kategori_keluar = [
        "Pembelian Tiket Pesawat", "Pembelian Hotel", "Pembelian Kereta",
        "Gaji Karyawan", "Operasional Kantor", "Marketing & Promosi",
        "Pajak dan Biaya Lainnya", "Kerugian Salah Order", "Kerugian Pembatalan",
        "Kerugian Kerusakan / Rusak", "Kerugian Lainnya", "Lain-lain"
    ]
    kategori_opsi = kategori_masuk if tipe == "Masuk" else kategori_keluar
    kategori = st.selectbox("Kategori", kategori_opsi, key="kategori_input")
    if kategori == "Lain-lain":
        kategori = st.text_input("Jelaskan kategori lainnya", key="kategori_lain_input")

    # --- No Invoice wajib ---
    no_invoice = st.text_input(
        "No Invoice (unik, misal OPR-YYYYMMDD-001 untuk pengeluaran operasional)",
        key="no_invoice_input"
    )

    keterangan = st.text_input("Keterangan", key="keterangan_input")
    jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1, format="%d", key="jumlah_input")
    status_manual = st.selectbox("Status", ["Lunas", "Belum Lunas"], key="status_input")

    if st.button("Simpan Data Manual", key="btn_simpan_manual"):
        # --- Validasi dasar ---
        if jumlah <= 0:
            st.error("Jumlah harus lebih dari 0")
        elif no_invoice.strip() == "":
            st.error("No Invoice wajib diisi dan harus unik")
        else:
            # --- Buat row baru ---
            new_row = {
                "Tanggal": pd.to_datetime(tanggal),
                "Tipe": tipe,
                "Kategori": kategori,
                "No Invoice": str(no_invoice).strip(),
                "Keterangan": keterangan,
                "Jumlah": jumlah,
                "Status": status_manual,
                "Sumber": "Manual Input"
            }

            # --- Simpan sementara di session state ---
            if "cashflow_manual" not in st.session_state:
                st.session_state.cashflow_manual = []
            st.session_state.cashflow_manual.append(new_row)

            st.success(f"✅ Data berhasil disimpan sementara (belum dikirim ke GSheets). Jumlah: Rp {jumlah:,}")

# --- Catatan untuk sistem ---
# 1. Semua transaksi manual akan tercatat di df_cashflow,
#    tapi tidak akan mempengaruhi Aging Report jika bukan invoice pelanggan.
# 2. Pastikan No Invoice unik untuk transaksi manual agar tidak terjadi duplikasi.
# 3. Transaksi operasional atau pengeluaran lainnya cukup dibuat No Invoice dummy (misal OPR-YYYYMMDD-001).


# --------------------------
# Laporan Cashflow Realtime
# --------------------------
with st.expander("💸 Laporan Cashflow Realtime"):

    # Ambil Sheet Data & Arus Kas
    ws_data = connect_to_gsheet(SHEET_ID, "Data")
    df_data = pd.DataFrame(ws_data.get_all_records())
    
    ws_cashflow = connect_to_gsheet(SHEET_ID, "Arus Kas")
    df_cashflow_existing = pd.DataFrame(ws_cashflow.get_all_records())

    # Parse otomatis dari Data
    df_cf_auto = parse_cashflow_from_data(df_data, df_cashflow_existing)
    
    # Gabungkan existing + otomatis
    df_cashflow = pd.concat([df_cashflow_existing, df_cf_auto], ignore_index=True)
    
    # Gabungkan manual
    if "cashflow_manual" in st.session_state and st.session_state.cashflow_manual:
        df_manual = pd.DataFrame(st.session_state.cashflow_manual)
        df_cashflow = pd.concat([df_cashflow, df_manual], ignore_index=True)
    
    # Ringkasan
    total_masuk = df_cashflow[df_cashflow["Tipe"]=="Masuk"]["Jumlah"].sum()
    total_keluar = df_cashflow[df_cashflow["Tipe"]=="Keluar"]["Jumlah"].sum()
    saldo = total_masuk - total_keluar
    invoices = df_cashflow["No Invoice"].unique()

    piutang_total = 0

    # Gunakan Invoice_Key, bukan No Invoice
    invoice_keys = df_cashflow["Invoice_Key"].unique()
    
    for key in invoice_keys:
    
        # Data cashflow untuk invoice ini
        df_inv_cf = df_cashflow[df_cashflow["Invoice_Key"] == key]
    
        # Ambil NO INVOICE untuk pemetaan ke df_data
        inv_no = df_inv_cf["No Invoice"].iloc[0]
    
        # Ambil harga jual dari DF_DATA
        df_inv_data = df_data[df_data["Invoice_Key"] == key]
        total_harga_jual = df_inv_data["Harga Jual"].sum()
    
        # Total pembayaran masuk
        total_sudah_diterima = df_inv_cf[df_inv_cf["Tipe"]=="Masuk"]["Jumlah"].sum()
    
        # Rumus piutang yang benar
        piutang_invoice = total_harga_jual - total_sudah_diterima
    
        if piutang_invoice > 0:
            piutang_total += piutang_invoice

    
    total_piutang = piutang_total

    #col1, col2, col3, col4 = st.columns(4)
    st.metric("Total Masuk", format_rp(total_masuk))
    st.metric("Total Keluar", format_rp(total_keluar))
    st.metric("Saldo Akhir", format_rp(saldo))
    st.metric("Piutang Belum Lunas", format_rp(total_piutang))

    st.markdown("### 🔍 Data Cashflow Realtime")
    st.dataframe(df_cashflow.sort_values(by="Tanggal", ascending=False), use_container_width=True)

    def generate_aging_report(df_cashflow, df_data, overdue_days=30):
        """
        Menghasilkan laporan aging berdasarkan harga jual & pembayaran actual.
        Menggunakan Invoice_Key agar akurat, termasuk invoice tanpa nomor.
        """
        # Ambil hanya invoice dengan status Belum Lunas (cashflow existing)
        df_unpaid = df_cashflow[df_cashflow["Status"] == "Belum Lunas"].copy()
    
        aging_rows = []
    
        # Loop berdasarkan Invoice_Key
        for key in df_unpaid["Invoice_Key"].unique():
            
            # Cashflow untuk invoice ini
            df_inv = df_unpaid[df_unpaid["Invoice_Key"] == key]
            if df_inv.empty:
                continue
    
            # Data "DATA" untuk ambil harga jual
            df_inv_data = df_data[df_data["Invoice_Key"] == key]
    
            # Nama & invoice number
            nama_pemesan = df_inv["Nama Pemesan"].iloc[0] if "Nama Pemesan" in df_inv.columns and not df_inv["Nama Pemesan"].isna().all() else "Unknown"
            no_invoice = df_inv["No Invoice"].iloc[0] if "No Invoice" in df_inv.columns and not df_inv["No Invoice"].isna().all() else ""
    
            # Tanggal pemesanan = tanggal paling awal pada invoice
            tgl_pemesanan = df_inv_cf["Tanggal"].min()
    
            # 📌 Harga Jual dari DF_DATA (yg benar)
            total_harga_jual = df_inv_data["Harga Jual"].sum()
    
            # 📌 Total pembayaran masuk
            total_sudah_diterima = df_inv_cf[df_inv_cf["Tipe"] == "Masuk"]["Jumlah"].sum()
    
            # 📌 Piutang yang benar
            piutang_invoice = total_harga_jual - total_sudah_diterima
    
            # Skip jika piutang sudah 0
            if piutang_invoice <= 0:
                continue
    
            # Aging hari
            aging = (pd.Timestamp.today() - tgl_pemesanan).days
            overdue = aging > overdue_days
    
            aging_rows.append({
                "Nama Pemesan": nama_pemesan,
                "No Invoice": no_invoice,
                "Tanggal Pemesanan": tgl_pemesanan,
                "Piutang": piutang_invoice,
                "Aging (hari)": aging,
                "Overdue": overdue
            })
    
        df_aging = pd.DataFrame(aging_rows)

        # Formatting kolom Piutang
        df_aging["Piutang"] = df_aging["Piutang"].apply(lambda x: f"Rp {int(x):,}".replace(",", "."))
    
        return df_aging

    
    # Contoh penggunaan:
    df_aging = generate_aging_report(df_cashflow, df_data, overdue_days=30)
    df_aging = df_aging.sort_values(by="Aging (hari)", ascending=False)

    # Highlight overdue
    def highlight_overdue(row):
        return ["background-color: #FF9999" if row.Overdue else "" for _ in row]
    
    st.markdown("### ⏳ Aging Report / Invoice Belum Lunas")
    st.dataframe(df_aging.style.apply(highlight_overdue, axis=1), use_container_width=True)
#======================================================================================================================================
from streamlit_option_menu import option_menu
import streamlit as st

# Sidebar Menu
with st.sidebar:
    selected = option_menu(
        menu_title="Menu Utama",  # required
        options=["Dashboard", "Cashflow", "Invoice", "Transaksi", "Settings"],  # required
        icons=["bar-chart", "currency-dollar", "file-earmark-text", "truck", "gear"],  # optional
        menu_icon="cast",  # optional
        default_index=0,  # optional
    )

# Konten berdasarkan menu
if selected == "Dashboard":
    st.title("📊 Ringkasan Dashboard")
    
elif selected == "Cashflow":
    st.title("💸 Laporan Arus Kas")
    # tampilkan kode cashflow Anda di sini

elif selected == "Invoice":
    st.title("🧾 Manajemen Invoice")
    # tampilkan invoice belum lunas, reminder, dll

elif selected == "Transaksi":
    st.title("📦 Transaksi Pemesanan")
    # tampilkan semua transaksi

elif selected == "Settings":
    st.title("⚙️ Pengaturan Sistem")
    # form setting admin, kategori, dll

            
        
