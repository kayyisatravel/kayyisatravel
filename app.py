
import generatornew
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
import itertools
from streamlit_mic_recorder import speech_to_text
import finance_engine
import visualizer
import ai_auditor
import ai_input_processor

now = datetime.now(ZoneInfo("Asia/Jakarta"))


#refresh
# --- PAGE CONFIG ---
st.set_page_config(page_title="OCR & Dashboard Tiket", layout="centered", initial_sidebar_state="expanded")

# --- CACHE RESOURCES ----
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

def buat_invoice_pdf(data, tanggal_invoice, unique_invoice_no, output_pdf_filename, logo_path, ttd_path=None, status_lunas="BELUM LUNAS", nama_pemesan="Pelanggan"):
    import os
    import re
    import math
    import pandas as pd
    from datetime import datetime
    
    # =============================
    # Inisialisasi PDF
    # =============================
    # =====================================================================
    # 1. INISIALISASI PDF & WARNA UTAMA FLAT DESIGN (BARU)
    # =====================================================================
    pdf = FPDF(orientation="P", unit="mm", format="A4")  # Portrait
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Warna abu-abu gelap korporat untuk teks agar tidak jadul (bukan hitam pekat)
    COLOR_TEXT_MAIN = 44  # Setara dengan RGB (44, 62, 80) / #2c3e50
    pdf.set_text_color(COLOR_TEXT_MAIN, COLOR_TEXT_MAIN, COLOR_TEXT_MAIN)
    
    # =====================================================================
    # 2. HEADER UTAMA (ALAMAT + LOGO) - DIOPTIMALKAN MODERN
    # =====================================================================
    # Mengubah Font menjadi Helvetica dengan ukuran 8.5 yang lebih elegan
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_y(15)  # Jarak dari atas halaman diturunkan sedikit agar lapang
    
    alamat_perusahaan = (
        "KAYYISA TOUR & TRAVEL\n"
        "The Taman Dhika Cluster Wilis Blok F2 No. 2 Buduran, Sidoarjo - Jawa Timur\n"
        "Mobile: 081217026522  Email: kayyisatour@gmail.com"
    )
    pdf.set_x(pdf.l_margin)
    # Mengurangi tinggi baris multi_cell dari 5 menjadi 4.2 agar teks alamat padat dan rapi
    pdf.multi_cell(0, 4.2, alamat_perusahaan, align="L")
    
    # Render Logo Perusahaan di Kanan Atas
    if logo_path and os.path.exists(logo_path):
        try:
            logo_width = 38 # Sedikit dikecilkan agar proporsional dengan alamat baru
            logo_x = pdf.w - pdf.r_margin - logo_width
            pdf.image(logo_path, x=logo_x, y=10, w=logo_width)
        except Exception as e:
            print("Gagal load logo:", e)

    # Garis Pembatas Tipis Elegan Di Bawah Header Alamat
    pdf.ln(4)  
    pdf.set_draw_color(224, 228, 236)  # Mengubah warna garis menjadi abu-abu tipis halus
    pdf.set_line_width(0.2)  # Ketebalan garis dipertipis agar terlihat mewah
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())  
    pdf.set_y(pdf.get_y() + 2)  

    # Teks Judul INVOICE Minimalis Tengah
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "INVOICE", ln=True, align="C")
    pdf.ln(2)

    # === LANJUT KE SKRIP IDENTITAS MANIFES ANDA YANG SUDAH FIX ===
    if not isinstance(tanggal_invoice, datetime):
        tanggal_invoice = datetime.now()

    pdf.set_font("Arial", "", 9) # Bagian bawah ini tetap menggunakan font lama Anda agar tidak rusak
    pdf.cell(0, 5, f"Nama Pemesan: {nama_pemesan}", ln=True)
    # ... (skrip identitas ke bawah tetap utuh seperti milik Anda sebelumnya)

    pdf.cell(0, 5, f"Tanggal Invoice: {tanggal_invoice.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(0, 5, f"No. Invoice: {unique_invoice_no}", ln=True)
    
    pdf.set_font("Arial", "B", 9)
    pdf.write(5, "Status Pembayaran: ")
    if str(status_lunas).upper() == "LUNAS":
        pdf.set_text_color(39, 174, 96) # Hijau
        pdf.cell(0, 5, "LUNAS", ln=True)
    else:
        pdf.set_text_color(192, 41, 43) # Merah
        pdf.cell(0, 5, "BELUM LUNAS", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # =====================================================================
    # LEBAR KOLOM PROPORSIONAL PAS 190mm (BATAS MAKSIMAL KERTAS A4)
    # =====================================================================
    col_widths = {
        "No": 8,
        "Tgl Pemesanan": 21,
        "Tgl Berangkat": 21,
        "Kode Booking": 21,
        "No Penerbangan / Hotel / Kereta": 36,  # Kolom diperlebar khusus teks panjang
        "Durasi": 13,
        "Nama Customer": 32,  # Kolom diperlebar khusus nama panjang
        "Rute": 16,
        "Harga Jual": 22
    }

    kolom_pdf = [c for c in col_widths.keys() if c != "No" and c in data[0].keys()]
    header_mapping = {
        "Harga Jual": "Harga",
        "No Penerbangan / Hotel / Kereta": "Item / Armada"
    }

    # =====================================================================
    # CETAK HEADER JUDUL KOLOM TABEL
    # =====================================================================
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(224, 235, 255)  # Latar biru muda pastel khas korporat
    pdf.set_draw_color(180, 200, 230)  # Bingkai biru pastel tipis disamakan dengan rute
    
    pdf.cell(col_widths["No"], 8, "No", border=1, align="C", fill=True)
    for col in kolom_pdf:
        label_header = header_mapping.get(col, col)
        pdf.cell(col_widths[col], 8, label_header, border=1, align="C", fill=True)
    pdf.ln()

    # =====================================================================
    # ISI DATA TABEL (FIX METODE RENDER ADVANCED ROW HEIGHT SYNC)
    # =====================================================================
     
    pdf.set_font("Arial", "", 7.5)  
    total_harga = 0.0
    
    def to_number(val):
        if isinstance(val, (int, float)): return float(val)
        digits = re.findall(r"\d+", str(val))
        return float("".join(digits)) if digits else 0.0

    # FIX MUTLAK: Mengunci tinggi baris secara seragam sebesar 11 mm untuk estetika profesional
    FIXED_ROW_H = 11.0 

    for i, row in enumerate(data, start=1):
        # Format nilai dan masukkan ke dalam dictionary baris sementara
        row_formatted = {}
        for col in kolom_pdf:
            val_str = str(row.get(col, ""))
            if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                try: val_str = pd.to_datetime(val_str, dayfirst=True).strftime("%d-%m-%Y")
                except: pass
            elif col == "Harga Jual":
                num_val = to_number(val_str)
                if i == 1:
                    total_harga = sum(to_number(r.get("Harga Jual", 0)) for r in data)
                val_str = f"Rp {num_val:,.0f}".replace(',', '.')
            row_formatted[col] = val_str

        # Jaring pengaman ganti halaman baru otomatis berbasis tinggi seragam
        if pdf.get_y() + FIXED_ROW_H > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font("Arial", "B", 8)
            pdf.set_fill_color(224, 235, 255)
            pdf.cell(col_widths["No"], 8, "No", border=1, align="C", fill=True)
            for col in kolom_pdf:
                pdf.cell(col_widths[col], 8, header_mapping.get(col, col), border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_font("Arial", "", 7.5)

        # Kunci koordinat baris dasar
        start_x = pdf.l_margin
        start_y = pdf.get_y()
        
        # Gambar kotak luar nomor urut & isi teks nomor (Tinggi Seragam)
        pdf.rect(start_x, start_y, col_widths["No"], FIXED_ROW_H)
        pdf.set_xy(start_x, start_y)
        # Vertical centering untuk nomor urut tunggal (padding atas 3.5mm)
        pdf.set_y(start_y + 3.5)
        pdf.cell(col_widths["No"], 4, str(i), border=0, align="C")
        
        current_x = start_x + col_widths["No"]
        
        # Render cell data dengan tinggi seragam dan posisi vertikal pas di tengah
        for col in kolom_pdf:
            val_text = row_formatted[col]
            
            if col == "Harga Jual":
                align_cell = "R"  # Harga tetap kanan
            elif col in ["No Penerbangan / Hotel / Kereta", "Kode Booking", "Durasi", "Rute", "Tgl Pemesanan", "Tgl Berangkat"]:
                align_cell = "C"  # FIX: Item/Armada kembali dikunci rata tengah secara kuat
            else:
                align_cell = "L"  # Nama Customer tetap rata kiri agar lurus vertikal

            # Gambar bingkai kotak sel terluar dengan tinggi seragam yang rapi
            pdf.rect(current_x, start_y, col_widths[col], FIXED_ROW_H)
            
            # Hitung jumlah baris teks sebenarnya untuk menentukan padding vertikal tengah
            string_width = pdf.get_string_width(val_text)
            actual_lines = math.ceil(string_width / (col_widths[col] - 3))
            
            # --- LOGIKA OTOMATIS VERTICAL CENTERING (ANTI-GANTUNG) ---
            if actual_lines == 1:
                # Teks pendek 1 baris didorong turun 3.5 mm agar pas di tengah kotak
                padding_top = 3.5
            else:
                # Teks panjang 2 baris didorong turun 1.3 mm agar seimbang
                padding_top = 1.3

            # Set koordinat presisi tepat di dalam kotak sel terkait
            pdf.set_xy(current_x, start_y + padding_top)

            # Cetak teks menggunakan multi_cell tanpa border (Kotak sudah diwakili pdf.rect)
            pdf.multi_cell(col_widths[col], 4.2, val_text, border=0, align=align_cell)
            
            # Geser koordinat X ke kanan untuk kolom berikutnya
            current_x += col_widths[col]
            
        # Kembalikan posisi kursor ke baris baru paling kiri di bawah kotak yang seragam
        pdf.set_xy(start_x, start_y + FIXED_ROW_H)


    # =====================================================================
    # LOGIKA FINANSIAL RINGKASAN DATA KANAN BAWAH SUMMARY
    # =====================================================================
    pdf.ln(4)
    if status_lunas.upper() == "LUNAS":
        terbayar = total_harga
        sisa_tagihan = total_harga - terbayar
    else:
        terbayar = 0
        sisa_tagihan = total_harga - terbayar
    
    left_blank_width = col_widths["No"] + sum(col_widths[col] for col in kolom_pdf if col not in ["Nama Customer", "Rute", "Harga Jual"])
    label_width = col_widths["Nama Customer"]
    value_width = col_widths["Rute"] + col_widths["Harga Jual"]

    def summary_row_custom(label, value, bold=False, red=False):
        pdf.set_font("Arial", "B" if bold else "", 8)
        pdf.set_text_color(200, 0, 0) if red else pdf.set_text_color(0, 0, 0)
        pdf.cell(left_blank_width, 6, "", 0, 0)
        pdf.cell(label_width, 6, label, 1, 0, 'C')
        pdf.cell(value_width, 6, f"Rp {value:,.0f}".replace(',', '.'), 1, 1, 'R')
        pdf.set_text_color(0, 0, 0)

    summary_row_custom("Total Harga", total_harga, bold=True)
    summary_row_custom("Terbayar", terbayar)
    summary_row_custom("Sisa Tagihan", sisa_tagihan, bold=True, red=(sisa_tagihan > 0))
    pdf.ln(3)
    
    # =====================================================================
    # SEGMEN KALIMAT TERBILANG & DAFTAR REKENING BANK
    # =====================================================================
    def terbilang(n):
        angka = ["Nol", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]
        n = int(n)
        if n == 0: return "Nol"
        elif n < 12: return angka[n]
        elif n < 20: return terbilang(n - 10) + " Belas"
        elif n < 100:
            sisa = n % 10
            return terbilang(n // 10) + " Puluh" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 200: return "Seratus" + ("" if n == 100 else " " + terbilang(n - 100))
        elif n < 1000:
            sisa = n % 100
            return terbilang(n // 100) + " Ratus" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 2000: return "Seribu" + ("" if n == 1000 else " " + terbilang(n - 1000))
        elif n < 1_000_000:
            sisa = n % 1000
            return terbilang(n // 1000) + " Ribu" + ("" if sisa == 0 else " " + terbilang(sisa))
        elif n < 1_000_000_000:
            sisa = n % 1_000_000
            return terbilang(n // 1_000_000) + " Juta" + ("" if sisa == 0 else " " + terbilang(sisa))
        else:
            sisa = n % 1_000_000_000
            return terbilang(n // 1_000_000_000) + " Milyar" + ("" if sisa == 0 else " " + terbilang(sisa))

    pdf.set_font("Arial", "I", 8.5)
    terbilang_text = "Nol rupiah" if sisa_tagihan <= 0 else terbilang(sisa_tagihan).capitalize() + " rupiah"
    pdf.multi_cell(0, 5, f"Terbilang: ({terbilang_text})", align="L")
    pdf.ln(3)
    
    # Kunci koordinat vertikal mutlak setelah kalimat terbilang dicetak
    y_setelah_terbilang = pdf.get_y()
    left_x = pdf.l_margin
    right_x = pdf.w - 80

    # --- BLOCK 1: SEBELAH KIRI (INFORMASI BANK / STATUS LUNAS) ---
    pdf.set_xy(left_x, y_setelah_terbilang)
    if status_lunas.upper() == "LUNAS":
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(39, 174, 96)
        pdf.cell(100, 5, "- STATUS PEMBAYARAN: LUNAS (KUITANSI RESMI)", ln=False) # Ganti ke ln=False agar kursor tidak jatuh ke bawah
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(100, 5, "Mohon Transfer Pembayaran Ke Rekening Resmi:", ln=True)
        pdf.set_font("Arial", "", 8)
        bank_list = [
            "Bank BCA - 0881651041", "Bank Mandiri - 1420022043888",
            "Bank BNI - 0197267094", "Bank BRI - 008601138769506", "Bank BSI - 2204899994"
        ]    
        for bank in bank_list:
            pdf.set_x(left_x)
            pdf.cell(100, 4, f"- {bank} a.n Josirma Sari Pratiwi", ln=True) # Menggunakan ln=True khusus di dalam loop bank

    # Kunci posisi Y paling bawah setelah daftar bank selesai digambar agar footer tidak tertabrak
    y_maksimal_bank = pdf.get_y()

    # --- BLOCK 2: SEBELAH KANAN (TANDA TANGAN ELEKTRONIK MANAJEMEN) ---
    # Tarik koordinat kembali sejajar ke atas secara independen menggunakan set_xy
    pdf.set_xy(right_x, y_setelah_terbilang)
    if not ttd_path or not os.path.exists(ttd_path):
        pdf.set_font("Arial", "I", 7.5)
        pdf.cell(70, 5, "Invoice sah diterbitkan secara elektronik oleh sistem.", align="C", ln=False)
    else:
        try:
            pdf.set_font("Arial", "", 8.5)
            pdf.cell(70, 5, "Hormat kami,", ln=False, align="C")
            pdf.image(ttd_path, x=right_x + 17, y=y_setelah_terbilang + 6, w=35)
            
            # Gambar teks penutup di bawah gambar stempel tanda tangan digital
            pdf.set_xy(right_x, y_setelah_terbilang + 25)
            pdf.set_font("Arial", "B", 8.5)
            pdf.cell(70, 5, "Management Kayyisa", border="T", ln=False, align="C")
        except:
            pass

    # Ambil titik koordinat Y terendah di antara TTD atau daftar Bank untuk menaruh footer
    y_final_footer = max(y_maksimal_bank, pdf.get_y())

    # --- BLOCK 3: FOOTER UTAMA (PAS DI BAGIAN PALING BAWAH KERTAS - ANTI TUMPUK) ---
    pdf.set_xy(left_x, y_final_footer + 6)
    pdf.set_font("Arial", "I", 7.5)
    pdf.set_text_color(100, 100, 100) # Warna abu-abu elegan untuk footer
    pdf.multi_cell(0, 4, "Invoice ini diterbitkan oleh sistem manajemen Kayyisa Tour & Travel dan sah tanpa tanda tangan fisik basah sesuai aturan transaksi elektronik.", align="C")

    # Output eksekusi simpan berkas fisik PDF final di server
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



import streamlit as st
import os

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

# Path logo lokal
logo_path = os.path.join("assets", "Logo Perusahaan.jpeg")

# Layout: 2 kolom
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        '<div class="main-header">Management Dashboard |<span class="highlight">Kayyisa Tour & Travel</span></div>', 
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-header">Business Management System</div>', 
        unsafe_allow_html=True
    )

with col2:
    st.image(logo_path, width=250)  # ganti URL dengan logo lokal


# Garis horizontal
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

#==================COBA GEMINI AI===============================================
import streamlit as st
import pandas as pd
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# 🎫 [TAMBAHAN BARU]: FUNGSI GENERATOR TIKET PDF RESMI - KAI, HOTEL, PESAWAT
# ==============================================================================
from fpdf import FPDF

def buat_voucher_pdf_kayyisa(data_list: list) -> bytes:
    """Fungsi mandiri merubah data hasil bacaan AI menjadi file PDF Voucher resmi berlogo Kayyisa"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for idx, item in enumerate(data_list):
        pdf.add_page()
        
        # --- HEADER PERUSAHAAN ---
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(16, 44, 87) # Warna Biru Gelap Profesional Kayyisa
        pdf.cell(0, 10, "| Kayyisa Tour & Travel", ln=True, align="L")
        
        pdf.set_font("Arial", "I", 10)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, f"E-VOUCHER / E-TICKET RESERVASI - ENTRI {idx+1}", ln=True, align="L")
        
        # Garis Pembatas Atas
        pdf.set_draw_color(16, 44, 87)
        pdf.set_line_width(0.8)
        pdf.line(10, 27, 200, 27)
        pdf.ln(10)
        
        # --- DETAIL UTAMA TIKET ---
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, f"Tipe Reservasi: {str(item.get('tipe', 'TRAVEL')).upper()}", ln=True)
        pdf.ln(2)
        
        # Buat struktur baris detail berkiri-kanan (Format rapi tanpa nominal uang)
        pdf.set_font("Arial", "", 10)
        
        # Baris 1: Kode PNR
        pdf.cell(45, 7, "Kode Booking (PNR)", border=0)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, f": {item.get('kode_booking', '-')}", border=0, ln=True)
        pdf.set_font("Arial", "", 10)
        
        # Baris 2: Nama Hotel / Kendaraan
        label_nama = "Nama Hotel" if item.get('tipe') == 'HOTEL' else "Nama Kendaraan"
        pdf.cell(45, 7, label_nama, border=0)
        pdf.cell(0, 7, f": {item.get('item_name', '-')}", border=0, ln=True)
        
        # Baris 3: Nama Tamu
        pdf.cell(45, 7, "Nama Tamu / Penumpang", border=0)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, f": {item.get('nama_customer', '-')}", border=0, ln=True)
        pdf.set_font("Arial", "", 10)
        
        # Baris 4: Rute atau Kota
        label_rute = "Kota Properti" if item.get('tipe') == 'HOTEL' else "Rute Perjalanan"
        pdf.cell(45, 7, label_rute, border=0)
        pdf.cell(0, 7, f": {item.get('rute', '-')}", border=0, ln=True)
        
        # Baris 5: Durasi atau Jam
        label_durasi = "Lama Menginap" if item.get('tipe') == 'HOTEL' else "Jam Perjalanan"
        pdf.cell(45, 7, label_durasi, border=0)
        pdf.cell(0, 7, f": {item.get('durasi', '-')}", border=0, ln=True)
        
        # Baris 6: Tanggal Keberangkatan
        pdf.cell(45, 7, "Tanggal Berangkat/Check-in", border=0)
        pdf.cell(0, 7, f": {item.get('tgl_berangkat', '-')}", border=0, ln=True)
        
        # Khusus Hotel, munculkan fasilitas makanan jika ada
        if item.get('tipe') == 'HOTEL' and item.get('bf_status'):
            pdf.cell(45, 7, "Fasilitas Makanan", border=0)
            pdf.cell(0, 7, f": {'Termasuk Sarapan (BF)' if item.get('bf_status') == 'BF' else 'Tanpa Sarapan (Room Only)'}", border=0, ln=True)
            
        pdf.ln(15)
        
        # --- FOOTER DAN CATATAN PENTING ---
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, "Catatan Penting:", ln=True)
        pdf.set_font("Arial", "", 8)
        pdf.cell(0, 4, "- Voucher ini adalah bukti reservasi resmi yang sah dari Kayyisa Tour & Travel.", ln=True)
        pdf.cell(0, 4, "- Saat check-in hotel atau boarding transportasi, tunjukkan file PDF ini langsung dari HP Anda.", ln=True)
        pdf.cell(0, 4, "- Jika ada kendala teknis di lapangan, segera hubungi layanan darurat kami via email/WhatsApp.", ln=True)

    # Mengembalikan data dokumen dalam bentuk biner bytes agar bisa diunduh langsung via Streamlit
    return pdf.output(dest="S")


# =======================================================
# === 1. SKEMA DATA UNTUK MENGUNCI OUTPUT GEMINI AI ===
# =======================================================
class AITicketEntry(BaseModel):
    tgl_pemesanan: str = Field(description="Tanggal pemesanan format YYYY-MM-DD. Jika tidak ada, samakan dengan tgl berangkat")
    tgl_berangkat: str = Field(description="Tanggal keberangkatan tiket / check-in hotel format YYYY-MM-DD")
    kode_booking: Optional[str] = Field(description="Kode booking, PNR, atau ID Pesanan")
    item_name: str = Field(description="Nama Hotel, Nomor Penerbangan (cth: JT 883), atau Info Kursi Kereta")
    durasi: str = Field(description="Durasi, contoh: '1 mlm' untuk hotel, atau jam perjalanan '17:52-20:35' untuk transportasi")
    nama_customer: Optional[str] = Field(description="Nama lengkap tamu atau penumpang")
    rute: Optional[str] = Field(description="Kota hotel (cth: Tuban), rute bandara (cth: SUB-HLP), atau stasiun (cth: BG-JR)")
    harga_beli: Optional[int] = Field(description="Harga modal/beli total dibagi rata per kamar/pax (integer bersih)")
    harga_jual: Optional[int] = Field(description="Harga jual ke pembeli total dibagi rata per kamar/pax (integer bersih)")
    tipe: str = Field(description="Wajib pilih salah satu dari tiga kata ini: HOTEL, PESAWAT, KERETA")
    bf_status: Optional[str] = Field(description="Khusus HOTEL: isi 'BF' jika include sarapan, 'NBF' jika tidak. Transportasi isi kosong ''")
    platform: str = Field(description="Nama OTA/Platform asal teks, wajib salah satu dari: Tiket.com, Traveloka, Agoda, Trip.com, Book Cabin, KAI Access, RedDoorz, Lainnya")

class AITicketParserResult(BaseModel):
    entries: List[AITicketEntry]

# =======================================================
# === 2. FUNGSI UTAMA PANGGILAN API GEMINI           ===
# =======================================================
def panggil_gemini_ai_parser(text_block: str) -> list:
    """JALUR 1: Fungsi AI Gemini 3.1 Flash-Lite KHUSUS UNTUK MEMBACA TEKS / DIKTE SUARA"""
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        
        prompt = f"""
        Kamu adalah sistem AI parser data manifes travel. Ekstrak teks OCR berikut menjadi JSON Array secara presisi.
        
        ATURAN STRUKTUR HARGA GABUNGAN VENDOR & INTERNAL (SANGAT KETAT):
        1. Tentukan "Jumlah Kamar" (untuk Hotel) atau "Jumlah Penumpang" (untuk Transportasi) terlebih dahulu.
           (Contoh pada teks: 'Jumlah Kamar: 2' dan terdapat 2 nama tamu: Jane Susanna & Gascha Firga Prananda, maka data wajib dipecah menjadi 2 baris entri).
        
        2. "harga_beli" (MODAL PER KAMAR / PER PAX):
           - Cari teks nominal modal yang dibayarkan ke pihak vendor/OTA. Kata kuncinya wajib berada di dekat kata 'JUMLAH PEMBAYARAN', 'TOTAL', atau 'Dibayar Hari Ini' pada rincian kuitansi vendor (Contoh pada teks: 'JUMLAH PEMBAYARAN 1.596.000').
           - Kamu WAJIB membagi rata nominal total vendor tersebut dengan jumlah kamar atau jumlah penumpang (Contoh: 1.596.000 / 2 kamar = 798000).
           - Masukkan hasil pembagian bersih per kamar/per pax ini sebagai "harga_beli".
        
        3. "harga_jual" (HARGA TOKO PER KAMAR / PER PAX):
           - Langkah 1: Jika admin mengetik kata manual (cth: 'Jual 950000'), gunakan angka itu. Atau (ATURAN SHORTCUT): Jika admin mengetik manual kata 'Harga' diikuti nominal angka (Contoh: 'Harga Rp 1.000.000' atau 'Harga 1000000'), maka nominal tersebut WAJIB kamu tetapkan sebagai "harga_jual".
           - Langkah 2: Jika tidak ada input manual, cari teks nominal yang ditawarkan ke konsumen di dalam tabel itinerary internal Kayyisa. Kata kuncinya berada di dekat label 'Total Harga' atau 'Rate per Malam' (Contoh pada teks: 'Total Harga Rp 1.860.000').
           - Kamu WAJIB membagi rata nominal total internal tersebut dengan jumlah kamar atau jumlah penumpang (Contoh: 1.860.000 / 2 kamar = 930000).
           - Masukkan hasil pembagian bersih per kamar/per pax ini sebagai "harga_jual".
           - Jika dokumen HOTEL, tidak ada instruksi 'Jual'/'Harga' manual, tetapi ada kolom 'Total Harga' resmi dari tabel voucher (cth: 'Total Harga Rp 1.860.000'), ambil angka ini sebagai total omzet jual. Kamu WAJIB membagi rata total harga ini dengan 'Jumlah Kamar' (Contoh: Total Harga tabel 1.860.000 / 2 kamar = 930000). Masukkan hasil pembagian per kamar ini sebagai "harga_jual".
           - Langkah 3 (FALLBACK): Jika Langkah 1 dan 2 tidak ada, samakan nilai "harga_jual" dengan "harga_beli" per baris.
        
        ATURAN STRUKTUR DATA UTAMA (WAJIB DIPATUHI BAGAIMANAPUN INPUT TEKSNYA):
        
        0. NAMA CUSTOMER: Wajib ubah ke format Title Case / Huruf Kapital di Awal Kata (EYD Baku). 
           Wajib bersihkan dan balik total jika mendeteksi format nama maskapai/internasional (Last Name/First Name) serta hapus gelar sapaan seperti 'MR', 'MRS', 'MS', 'TN', 'NY'.
           (Contoh: 'UTOMO/PRABOWO MR' -> Hasil: 'Prabowo Utomo').
           (Contoh: 'SUTRISNO/DEWI MRS' -> Hasil: 'Dewi Sutrisno').
        1. Tipe PESAWAT: "item_name" berisi Nama Maskapai dan No Penerbangan (cth: "QG997-QG 174"). Durasi format 'HH:MM - HH:MM'. Rute HANYA kode bandara 3 huruf (cth: "TKG - SUB").
        2. Tipe HOTEL:
           - "item_name": Nama properti hotel bersih (Contoh: "Montana Hotel Syariah Banjarbaru").
           - "durasi": Jumlah malam + kata 'mlm' (Contoh: "2 mlm").
           - "rute": HANYA nama kota/kabupaten lokasi hotel (Contoh: "Banjarbaru").
           - "bf_status": Isi 'BF' (jika ada sarapan) atau 'NBF' (jika tanpa sarapan/Room Only).
        3. Tipe KERETA (Termasuk Whoosh): "item_name" format penulisan WAJIB: [Nama Kereta] [Singkatan Kelas] [Nomor Gerbong]/[Nomor Kursi] (Contoh: "Sembrani Eks 4/5D"). Durasi format 'HH:MM - HH:MM'. Rute berisi kode stasiun asal - tujuan (cth: "GMR - SBI").
            INGAT: Jika kelasnya 'Business Class', singkatan kelasnya adalah 'Bis' (Contoh: "Whoosh Bis 2/4A"). JANGAN PERNAH menulis kata "Bus"!
        4. TANGGAL: Format standar ISO 'YYYY-MM-DD'. Jika tanggal pemesanan ragu, samakan dengan tgl berangkat.
        5. PLATFORM: Pilih salah satu dari: "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin", "KAI Access", "RedDoorz", "Lainnya".
        6. KETERANGAN PAKET TAMBAHAN: Jika di dalam teks input terdapat informasi paket wisata tambahan (add-on promo ticket seperti Dufan, Ancol, Jatim Park, dll), kamu WAJIB menuliskan nama paket tersebut secara ringkas ke dalam field "keterangan" di database agar datanya tidak hilang.
        
        Format Output Wajib JSON Array:
        {{
          "entries": [
            {{
              "tgl_pemesanan": "YYYY-MM-DD",
              "tgl_berangkat": "YYYY-MM-DD",
              "kode_booking": "KODE123",
              "item_name": "Nama Kendaraan/Hotel Sesuai Aturan Ketat di Atas",
              "durasi": "Sesuai Aturan",
              "nama_customer": "Nama Lengkap",
              "rute": "Sesuai Aturan",
              "harga_beli": 1500000,
              "harga_jual": 1500000, 
              "tipe": "PESAWAT atau HOTEL atau KERETA",
              "bf_status": "BF atau NBF atau kosong jika bukan hotel",
              "platform": "Nama Platform"
            }}
          ]
        }}
        
        Teks OCR Mentah yang Harus Kamu Ekstrak:
        {text_block}
        """
        
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        
        import json
        parsed_json = json.loads(response.text)
        return parsed_json.get("entries", [])
    except Exception as e:
        st.error(f"Error pada sistem AI Teks: {e}")
        return []


def panggil_gemini_vision_parser(uploaded_file) -> list:
    """JALUR 2: Fungsi AI Gemini 3.1 Flash-Lite KHUSUS UNTUK MEMBACA GAMBAR SCREENSHOT / FILE PDF"""
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Ekstraksi biner dokumen gambar/pdf
        file_bytes = uploaded_file.read()
        mime_type = uploaded_file.type
        image_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        
        prompt = """
        Kamu adalah sistem AI Computer Vision untuk agen travel. Analisis GAMBAR screenshot booking atau file PDF e-ticket ini.
        Pahami isinya layaknya manusia dan ekstrak informasinya menjadi JSON Array secara presisi.
        
        ATURAN STRUKTUR HARGA GABUNGAN VENDOR & INTERNAL (SANGAT KETAT):
        1. Tentukan "Jumlah Kamar" (untuk Hotel) atau "Jumlah Penumpang" (untuk Transportasi) terlebih dahulu.
           (Contoh pada teks: 'Jumlah Kamar: 2' dan terdapat 2 nama tamu: Jane Susanna & Gascha Firga Prananda, maka data wajib dipecah menjadi 2 baris entri).
        
        2. "harga_beli" (MODAL PER KAMAR / PER PAX):
           - Cari teks nominal modal yang dibayarkan ke pihak vendor/OTA. Kata kuncinya wajib berada di dekat kata 'JUMLAH PEMBAYARAN', 'TOTAL', atau 'Dibayar Hari Ini' pada rincian kuitansi vendor (Contoh pada teks: 'JUMLAH PEMBAYARAN 1.596.000').
           - Kamu WAJIB membagi rata nominal total vendor tersebut dengan jumlah kamar atau jumlah penumpang (Contoh: 1.596.000 / 2 kamar = 798000).
           - Masukkan hasil pembagian bersih per kamar/per pax ini sebagai "harga_beli".
        
        3. "harga_jual" (HARGA TOKO PER KAMAR / PER PAX):
           - Langkah 1: Jika admin mengetik kata manual (cth: 'Jual 950000'), gunakan angka itu. Atau (ATURAN SHORTCUT): Jika admin mengetik manual kata 'Harga' diikuti nominal angka (Contoh: 'Harga Rp 1.000.000' atau 'Harga 1000000'), maka nominal tersebut WAJIB kamu tetapkan sebagai "harga_jual".
           - Langkah 2: Jika tidak ada input manual, cari teks nominal yang ditawarkan ke konsumen di dalam tabel itinerary internal Kayyisa. Kata kuncinya berada di dekat label 'Total Harga' atau 'Rate per Malam' (Contoh pada teks: 'Total Harga Rp 1.860.000').
           - Kamu WAJIB membagi rata nominal total internal tersebut dengan jumlah kamar atau jumlah penumpang (Contoh: 1.860.000 / 2 kamar = 930000).
           - Masukkan hasil pembagian bersih per kamar/per pax ini sebagai "harga_jual".
           - Jika dokumen HOTEL, tidak ada instruksi 'Jual'/'Harga' manual, tetapi ada kolom 'Total Harga' resmi dari tabel voucher (cth: 'Total Harga Rp 1.860.000'), ambil angka ini sebagai total omzet jual. Kamu WAJIB membagi rata total harga ini dengan 'Jumlah Kamar' (Contoh: Total Harga tabel 1.860.000 / 2 kamar = 930000). Masukkan hasil pembagian per kamar ini sebagai "harga_jual".
           - Langkah 3 (FALLBACK): Jika Langkah 1 dan 2 tidak ada, samakan nilai "harga_jual" dengan "harga_beli" per baris.
        
        ATURAN STRUKTUR DATA UTAMA (WAJIB DIPATUHI BAGAIMANAPUN INPUT TEKSNYA):
        0. NAMA CUSTOMER: Wajib ubah ke format Title Case / Huruf Kapital di Awal Kata (EYD Baku). 
           Wajib bersihkan dan balik total jika mendeteksi format nama maskapai/internasional (Last Name/First Name) serta hapus gelar sapaan seperti 'MR', 'MRS', 'MS', 'TN', 'NY'.
           (Contoh: 'UTOMO/PRABOWO MR' -> Hasil: 'Prabowo Utomo').
           (Contoh: 'SUTRISNO/DEWI MRS' -> Hasil: 'Dewi Sutrisno').
        1. Tipe PESAWAT: "item_name" berisi Nama Maskapai dan No Penerbangan (cth: "QG997-QG 174"). Durasi format 'HH:MM - HH:MM'. Rute HANYA kode bandara 3 huruf (cth: "TKG - SUB").
        2. Tipe HOTEL:
           - "item_name": Nama properti hotel bersih (Contoh: "Montana Hotel Syariah Banjarbaru").
           - "durasi": Jumlah malam + kata 'mlm' (Contoh: "2 mlm").
           - "rute": HANYA nama kota/kabupaten lokasi hotel (Contoh: "Banjarbaru").
           - "bf_status": Isi 'BF' (jika ada sarapan) atau 'NBF' (jika tanpa sarapan/Room Only).
        3. Tipe KERETA (Termasuk Whoosh): "item_name" format penulisan WAJIB: [Nama Kereta] [Singkatan Kelas] [Nomor Gerbong]/[Nomor Kursi] (Contoh: "Sembrani Eks 4/5D"). Durasi format 'HH:MM - HH:MM'. Rute berisi kode stasiun asal - tujuan (cth: "GMR - SBI").
            INGAT: Jika kelasnya 'Business Class', singkatan kelasnya adalah 'Bis' (Contoh: "Whoosh Bis 2/4A"). JANGAN PERNAH menulis kata "Bus"!
        4. TANGGAL: Format standar ISO 'YYYY-MM-DD'. Jika tanggal pemesanan ragu, samakan dengan tgl berangkat.
        5. PLATFORM: Pilih salah satu dari: "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin", "KAI Access", "RedDoorz", "Lainnya".
        6. KETERANGAN PAKET TAMBAHAN: Jika di dalam teks input terdapat informasi paket wisata tambahan (add-on promo ticket seperti Dufan, Ancol, Jatim Park, dll), kamu WAJIB menuliskan nama paket tersebut secara ringkas ke dalam field "keterangan" di database agar datanya tidak hilang.
        
        Format Output Wajib JSON Array:
        {
          "entries": [
            {
              "tgl_pemesanan": "YYYY-MM-DD",
              "tgl_berangkat": "YYYY-MM-DD",
              "kode_booking": "KODE123",
              "item_name": "Nama Lengkap Sesuai Aturan",
              "durasi": "Sesuai Aturan",
              "nama_customer": "Nama Lengkap",
              "rute": "Sesuai Aturan",
              "harga_beli": 275000,
              "harga_jual": 303500, 
              "tipe": "PESAWAT atau HOTEL atau KERETA",
              "bf_status": "BF atau NBF atau kosong jika bukan hotel",
              "platform": "Nama Platform"
            }
          ]
        }
        """
        
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        
        import json
        parsed_json = json.loads(response.text)
        return parsed_json.get("entries", [])
    except Exception as e:
        st.error(f"Error pada Vision AI Gambar: {e}")
        return []



# =======================================================
# === 3. ATURAN OTOMATISASI DATA (LOGIKA BUSINESS)     ===
# =======================================================
def terapkan_otomatisasi_pembayaran(platform_name: str) -> (str, str):
    """Fungsi aturan default sesuai kesepakatan ide kita"""
    p_lower = platform_name.lower()
    
    if "traveloka" in p_lower:
        return "Credit Card", "UOB"
    elif "tiket" in p_lower:
        return "Credit Card", "UOB"
    elif "kai" in p_lower or "access" in p_lower:
        return "Credit Card", "UOB"
    elif "agoda" in p_lower:
        return "Dana Tunai/Cash", "BNI"
    elif "book cabin" in p_lower:
        return "Credit Card", "BNI"
    else:
        return "Credit Card", "UOB" # Kosongkan jika platform lainnya

# --- SECTION 2: BULK MANUAL INPUT ---
#st.markdown('---')

# ==============================================================================
# 🤖 [FIXED FINAL]: EXPANDER UTAMA - MULTI-INPUT (TEKS, GAMBAR, & SUARA) CERDAS AI
# ==============================================================================
with st.expander('⌨️ Upload Data Reservasi)', expanded=True):
    st.markdown("""
    *Pilih metode input yang paling praktis. Sistem otomatis menyelaraskan format KAI, Hotel, maupun Pesawat.*
    """)
    
    # Inisialisasi memori teks utama jika belum ada di sistem
    if "konten_teks_travel_utama" not in st.session_state:
        st.session_state["konten_teks_travel_utama"] = ""
        
    hasil_pilihan_ai = None
    input_mentah_ref = ""
    tombol_ditekan = False 
    
    # 🎛️ SAKLAR INTERAKTIF TAB
    tab_text, tab_file = st.tabs([
        "📝 Input Teks / Suara (Copas & Dikte)", 
        "📷 Input Gambar / File PDF"
    ])
    
    # --- JALUR INPUT 1: KOTAK TEKS + MIKROFON SUARA ---
    with tab_text:
        col_textarea, col_microphone = st.columns([0.80, 0.20])
        
        with col_microphone:
            st.write("🎙️ **Input Suara**")
            teks_suara_langsung = speech_to_text(
                start_prompt="🎙️ Mulai", stop_prompt="🛑 Stop", language='id', 
                key="fitur_speech_to_text_kayyisa", just_once=True, use_container_width=True
            )
            if teks_suara_langsung:
                st.session_state["konten_teks_travel_utama"] = teks_suara_langsung
                st.rerun() 
                
        with col_textarea:
            ai_raw = st.text_area(
                "Tempelkan teks atau klik 'Mulai' di samping untuk mendikte data (pisahkan dengan '==='):",
                key="konten_teks_travel_utama", height=200
            )
        
        if st.button("📊 Proses ke Database", key="btn_proses_text_finance", use_container_width=True):
            if ai_raw.strip():
                tombol_ditekan = True
                with st.spinner("Gemini AI sedang membaca salinan teks..."):
                    # 🚀 SINKRONISASI MODULAR: Memanggil fungsi mesin universal baru
                    import ai_input_processor
                    hasil_pilihan_ai = ai_input_processor.proses_pembacaan_multimodal_universal(text_input=ai_raw.strip())
                    input_mentah_ref = ai_raw.strip()

    # --- JALUR INPUT 2: KOTAK UPLOAD FILE ---
    with tab_file:
        file_input = st.file_uploader(
            "Seret dan lepas file screenshot booking atau file PDF e-ticket asli dari vendor ke sini:",
            type=["png", "jpg", "jpeg", "pdf"], key="asisten_ai_file_input"
        )
        if st.button("🤖 Jalankan Proses Cerdas Gambar AI", key="btn_proses_vision_finance", use_container_width=True):
            if file_input is not None:
                tombol_ditekan = True
                with st.spinner("Vision AI sedang membedah dokumen gambar/PDF Anda..."):
                    # 🚀 SINKRONISASI MODULAR: Memanggil fungsi mesin universal baru
                    import ai_input_processor
                    hasil_pilihan_ai = ai_input_processor.proses_pembacaan_multimodal_universal(file_input=file_input)
                    input_mentah_ref = f"gambar_upload {file_input.name}"

    # --------------------------------------------------------------------------
    # LOGIKA PEMROSESAN GABUNGAN HIBRIDA (BISNIS & PRIBADI)
    # --------------------------------------------------------------------------
    if "peringatan_admin_ai" in st.session_state and st.session_state.peringatan_admin_ai:
        st.warning(st.session_state.peringatan_admin_ai)

    if tombol_ditekan:
        if hasil_pilihan_ai:
            ai_entries = []
            pemberitahuan_masalah_data = [] 
            blok_teks_list = input_mentah_ref.split("===")
            
            for idx, item in enumerate(hasil_pilihan_ai, start=1):
                # Deteksi otomatis jalur dari parameter AI
                is_bisnis_line = item.get("Is_Bisnis", True)
                
                hb = item.get("harga_beli") or 0
                hj = item.get("harga_jual") or hb
                kode_b = item.get("kode_booking", "")
                rute_p = item.get("rute", "")
                tipe_p = item.get("tipe", "").upper()
                
                # ✈️ JALUR A: JARING PENGAMAN MANDATORY TRANSAKSI BISNIS TRAVEL
                if is_bisnis_line:
                    kolom_bermasalah = []
                    if not kode_b: kolom_bermasalah.append("Kode Booking")
                    if not rute_p: kolom_bermasalah.append("Rute/Kota")
                    
                    # Celah aman Redeem Point: Harga Beli = 0 lolos jaring jika platform ada kata 'point'
                    if hb == 0 and "point" not in str(item.get("platform", "")).lower():
                        kolom_bermasalah.append("Harga Beli (0 tidak sah jika bukan Redeem Point)")
                        
                    if kolom_bermasalah:
                        nama_c = item.get("nama_customer") or "Nama Tidak Terbaca"
                        pemberitahuan_masalah_data.append(f"Entri ke-{idx} (Bisnis: {nama_c}) ➔ Kolom kosong: **{', '.join(kolom_bermasalah)}**")

                    laba = hj - hb
                    persen_laba = f"{round((laba / hb) * 100, 2)}%" if hb > 0 else "0.0%"
                    sumber_dana, detail_dana = terapkan_otomatisasi_pembayaran(item.get("platform", "Lainnya"))

                    ai_entries.append({
                        'Tgl Pemesanan': item.get("tgl_pemesanan", ""), 'Tgl Berangkat': item.get("tgl_berangkat", ""),
                        'Kode Booking': kode_b, 'No Penerbangan / Hotel / Kereta': item.get("item_name", ""),
                        'Durasi': item.get("durasi", ""), 'Nama Customer': item.get("nama_customer", ""), 'Rute': rute_p,
                        'Harga Beli': hb, 'Harga Jual': hj, 'Laba': laba, 'Tipe': tipe_p,
                        'BF/NBF': item.get("bf_status", ""), 'No Invoice': '', 'Keterangan': 'Belum Lunas',
                        'Pemesan': 'ER ENDO', 'Admin': 'PA', ' % Laba': persen_laba,
                        'Sumber Dana': sumber_dana, 'Detail Dana': detail_dana, 'Platform': item.get("platform", "Lainnya"),
                        'No Rekening': '' # Kosongkan kolom anggaran dompet jika ini data bisnis
                    })
                
                # 🏦 JALUR B: JARING PENGAMAN PENGELUARAN DOMPET PRIBADI / KAS RUMAH TANGGA
                else:
                    if hj <= 0:
                        pemberitahuan_masalah_data.append(f"Entri ke-{idx} (Pribadi: {item.get('item_name')}) ➔ Nominal belanja kosong!")

                    ai_entries.append({
                        'Tgl Pemesanan': item.get("tgl_pemesanan", ""), 'Tgl Berangkat': '',
                        'Kode Booking': '', 'No Penerbangan / Hotel / Kereta': item.get("item_name", ""),
                        'Durasi': '', 'Nama Customer': item.get("nama_customer", ""), 'Rute': '',
                        'Harga Beli': 0, 'Harga Jual': hj, 'Laba': 0, 'Tipe': '',
                        'BF/NBF': '', 'No Invoice': '', 'Keterangan': item.get("keterangan_tambahan", "Mutasi Pribadi"),
                        'Pemesan': 'OWNER', 'Admin': 'PA', ' % Laba': '0.0%',
                        'Sumber Dana': 'Dana Tunai/Cash', 'Detail Dana': 'BCA', 'Platform': 'Lainnya',
                        'No Rekening': item.get("no_rekening", "Rumah Tangga") # Mengambil porsi tebakan cerdas pos dompet dari AI
                    })

            st.session_state.bulk_parsed = pd.DataFrame(ai_entries)
            st.session_state.edit_mode_bulk = True
            
            if pemberitahuan_masalah_data:
                st.session_state.peringatan_admin_ai = "⚠️ **Peringatan Validasi Entri!** Ditemukan beberapa kolom wajib masih kosong:\n\n" + "\n".join([f"- {e}" for e in pemberitahuan_masalah_data]) + "\n\n**Mohon lengkapi data kosong tersebut** pada menu edit manual di bawah ini sebelum disimpan!"
            else:
                if "peringatan_admin_ai" in st.session_state: del st.session_state["peringatan_admin_ai"]
            st.rerun()
        else:
            st.error("⚠️ AI gagal mengekstrak data. Pastikan teks berisi data valid atau kualitas gambar/suara cukup jelas.")

    # ==============================================================================
    # FORM EDIT MANUAL INTERAKTIF (DENGAN SUNTIKAN DROPDOWN REKENING PRIBADI REAKTIF)
    # ==============================================================================
    if "bulk_parsed" in st.session_state and not st.session_state.bulk_parsed.empty:
        df = st.session_state.bulk_parsed
        
        required_cols = ["Sumber Dana", "Detail Dana", "Platform", "No Rekening"]
        for col in required_cols:
            if col not in df.columns: df[col] = ""

        edit_mode = st.checkbox("✏️ Edit Data Manual", value=st.session_state.get("edit_mode_bulk", False))

        if edit_mode:
            st.session_state.edit_mode_bulk = True
            st.markdown("#### 📝 Edit Beberapa Baris")

            selected_rows = st.multiselect("Pilih baris yang ingin diedit:", options=df.index.tolist())
            edited_rows = {}

            for i in selected_rows:
                row_data = df.iloc[i].to_dict()
                st.markdown(f"---\n##### ✏️ Baris ke-{i}")
                
                with st.expander(f"📝 Edit Data Baris {i}", expanded=True):
                    updated_row = {}
                
                    for col, val in row_data.items():
                        # ========== REAKTIF: SUNTIKAN DROPDOWN POS REKENING DOMPET KELUARGA ==========
                        if col == "No Rekening":
                            # Munculkan dropdown 6 pos dompet keluarga secara live jika ini baris data pribadi
                            if str(df.at[i, "Pemesan"]) == "OWNER":
                                pos_options = ["Rumah Tangga", "Aset Kantor", "Investasi", "Lifestyle", "Cadangan Bisnis", "Dana Sosial / Titipan"]
                                default_val = str(val) if str(val) in pos_options else "Rumah Tangga"
                                new_val = st.selectbox(f"Pos Dompet Keluarga (Baris {i})", options=pos_options, index=pos_options.index(default_val), key=f"No_Rekening_{i}")
                                updated_row[col] = new_val
                            else:
                                updated_row[col] = ""
                            continue
                            
                        # ========== HANDLE TANGGAL (FIX VALUEERROR) ==========
                        if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                            import datetime
                            
                            # Logika Normalisasi: Paksa string dari AI menjadi objek date resmi Python
                            if isinstance(val, str) and val.strip() != "":
                                try:
                                    # Coba tebak jika formatnya DD-MM-YYYY (Bawaan Prompt AI kita)
                                    val_date = pd.to_datetime(val, dayfirst=True).date()
                                except:
                                    try:
                                        # Cadangan jika formatnya YYYY-MM-DD
                                        val_date = pd.to_datetime(val).date()
                                    except:
                                        val_date = datetime.date.today()
                            elif isinstance(val, (pd.Timestamp, datetime.datetime)):
                                val_date = val.date()
                            elif isinstance(val, datetime.date):
                                val_date = val
                            else:
                                # Jika data kosong/NaT, setel otomatis ke tanggal hari ini
                                val_date = datetime.date.today()
                                
                            new_val = st.date_input(
                                f"{col} (Baris {i})", 
                                value=val_date, 
                                key=f"{col}_{i}"
                            )
                            updated_row[col] = new_val
                            continue

                            
                        # ========== HANDLE NUMERIC REAKTIF LIVE UPDATE ==========
                        elif col in ["Harga Beli", "Harga Jual", "Laba", " % Laba"]:
                            if col in ["Harga Beli", "Harga Jual"]:
                                val_clean = str(val).split('.')[0] if '.' in str(val) else str(val)
                                val_num = int(val_clean) if str(val_clean).isdigit() else 0
                                new_val = st.text_input(f"{col} (Baris {i})", value=str(val_num), key=f"{col}_{i}")
                                updated_row[col] = int(new_val) if new_val.isdigit() else 0
                            elif col == "Laba":
                                hb_live = st.session_state.get(f"Harga Beli_{i}", str(df.at[i, "Harga Beli"]))
                                hj_live = st.session_state.get(f"Harga Jual_{i}", str(df.at[i, "Harga Jual"]))
                                laba_live = (int(hj_live) if str(hj_live).isdigit() else 0) - (int(hb_live) if str(hb_live).isdigit() else 0)
                                st.markdown(f"💵 Laba Terkini (Baris {i}): Rp {laba_live:,}")
                                updated_row["Laba"] = laba_live
                            elif col == " % Laba":
                                hb_live = st.session_state.get(f"Harga Beli_{i}", str(df.at[i, "Harga Beli"]))
                                hj_live = st.session_state.get(f"Harga Jual_{i}", str(df.at[i, "Harga Jual"]))
                                hb_int = int(hb_live) if str(hb_live).isdigit() else 0
                                laba_live = (int(hj_live) if str(hj_live).isdigit() else 0) - hb_int
                                persen_live = f"{round((laba_live / hb_int) * 100, 2)}%" if hb_int > 0 else "0.0%"
                                st.markdown(f"📈 % Laba Terkini (Baris {i}): {persen_live}")
                                updated_row[" % Laba"] = persen_live
                            continue
                            
                        # ========== HANDLE DROPDOWN CASCADING REAKTIF ==========
                        elif col == "Sumber Dana":
                            sumber_dana_options = ["Dana Tunai/Cash", "Credit Card", "Reedem Point"]
                            default_val = str(val) if str(val) in sumber_dana_options else "Dana Tunai/Cash"
                            new_val = st.selectbox(f"{col} (Baris {i})", options=sumber_dana_options, index=sumber_dana_options.index(default_val), key=f"{col}_{i}")
                            updated_row[col] = new_val
                            continue
                            
                        elif col == "Detail Dana":
                            sumber_dana = updated_row.get("Sumber Dana", row_data.get("Sumber Dana", ""))
                            if sumber_dana == "Dana Tunai/Cash":
                                detail_options = ["BCA", "Mandiri", "BRI", "BNI", "BSI", "Mega", "SeaBank", "VA BCA", "VA Mandiri", "VA BRI", "VA BNI", "Ovo", "Dana", "Gopay", "ShopeePay", "Sakuku", "Blu Instant", "Bibli Pay"]
                            elif sumber_dana == "Credit Card":
                                detail_options = ["BCA", "Mandiri", "BRI", "BNI", "BSI", "UOB", "Mega", "Allo", "CIMB"]
                            elif sumber_dana == "Reedem Point":
                                detail_options = ["Tikom", "Traveloka", "Garuda"]
                            else:
                                detail_options = [""]
                            default_val = str(val) if str(val) in detail_options else detail_options[0]
                            new_val = st.selectbox(f"{col} (Baris {i})", options=detail_options, index=detail_options.index(default_val) if default_val in detail_options else 0, key=f"{col}_{i}")
                            updated_row[col] = new_val
                            continue
                            
                        elif col == "Platform":
                            platform_options = ["Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin", "KAI Access", "RedDoorz", "Garuda App", "Citilink App", "Lion Air Group App", "AirAsia App", "Booking.com", "OYO", "Dafam", "Lainnya"]
                            default_val = str(val) if str(val) in platform_options else "Lainnya"
                            new_val = st.selectbox(f"{col} (Baris {i})", options=platform_options, index=platform_options.index(default_val), key=f"{col}_{i}")
                            updated_row[col] = new_val
                            continue
                            
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
                
            if st.button("💾 Simpan Semua Perubahan"):
                for i, updated in edited_rows.items():
                    for col, val in updated.items(): 
                        df.at[i, col] = val
                st.session_state.bulk_parsed = df
                st.session_state.edit_mode_bulk = False
                st.success(f"✅ {len(edited_rows)} baris berhasil diperbarui.")
                st.rerun()
        else:
            st.session_state.edit_mode_bulk = False
            st.markdown("#### 📊 Data Gabungan Hasil Bulk")
            st.dataframe(st.session_state.bulk_parsed, use_container_width=True)
        
        # 📤 TOMBOL UTAMA PENYALUR DATA DUA JALUR (ROUTING ENTRi TO GSHEETS)
        if st.session_state.get("bulk_parsed") is not None and st.button("📤 Simpan Bulk ke GSheet", use_container_width=True):
            with st.spinner("Sedang menyalurkan data pembukuan ke Google Sheets secara paralel..."):
                df_final_save = st.session_state.bulk_parsed.copy()
                
                # Membagi gerbong data penjualan vs dompet pribadi
                is_bisnis_mask = df_final_save["Pemesan"] != "OWNER"
                df_save_bisnis = df_final_save[is_bisnis_mask].copy()
                df_save_pribadi = df_final_save[~is_bisnis_mask].copy()
                
                # Tembak Massal Jalur A: Ke Worksheet "Data" (Jika ada transaksi tiket)
                if not df_save_bisnis.empty:
                    df_save_bisnis_clean = df_save_bisnis.drop(columns=["No Rekening"], errors="ignore")
                    # Hubungkan dan kirim ke fungsi simpan utama existing Anda
                    save_gsheet(df_save_bisnis_clean)
                    
                # Tembak Massal Jalur B: Ke Worksheet "Pribadi" (Jika ada mutasi dompet/KPR/RT)
                if not df_save_pribadi.empty:
                    # Ambil data item/keterangan secara aman menggunakan metode .get() bawaan Pandas
                    # Ini menjamin aplikasi 100% kebal dari crash jika kolom bisnis tidak terbaca
                    item_name_pribadi = df_save_pribadi["No Penerbangan / Hotel / Kereta"] if "No Penerbangan / Hotel / Kereta" in df_save_pribadi.columns else "Pengeluaran"
                    nama_cust_pribadi = df_save_pribadi["Nama Customer"] if "Nama Customer" in df_save_pribadi.columns else "Owner"
                    
                    # Normalisasi penulisan kata Pengeluaran agar tidak typo 'Penggeluaran'
                    def tentukan_kategori_pribadi(row):
                        text_ket = str(row.get("Keterangan", "")).lower()
                        if "pemasukan" in text_ket or "ganti" in text_ket or "iuran" in text_ket:
                            return "Pemasukan"
                        return "Pengeluaran"

                    df_pribadi_structured = pd.DataFrame({
                        "Tanggal": df_save_pribadi["Tgl Pemesanan"],
                        "Bank_Sumber": df_save_pribadi["Detail Dana"].fillna("BCA"), 
                        "No_Rekening_AI": df_save_pribadi["No Rekening"].fillna("Rumah Tangga"),
                        "Kategori": df_save_pribadi.apply(tentukan_kategori_pribadi, axis=1),
                        "Nominal": df_save_pribadi["Harga Jual"],
                        "Keterangan": item_name_pribadi.astype(str) + " - " + nama_cust_pribadi.astype(str)
                    })
                    
                    # Eksekusi Tembak Massal ke GSheets dengan Konversi Tipe Data String Bersih
                    try:
                        ws_pribadi_sheet = connect_to_gsheet("1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8", "Pribadi")
                        
                        # Ubah baris dataframe menjadi list string/angka murni agar mulus diterima oleh API Google
                        for _, r_p in df_pribadi_structured.iterrows():
                            # Konversi tanggal ke format teks string YYYY-MM-DD atau DD-MM-YYYY agar terbaca rapi di GSheets
                            row_list = r_p.tolist()
                            if hasattr(row_list[0], 'strftime'):
                                row_list[0] = row_list[0].strftime('%d-%m-%Y')
                                
                            ws_pribadi_sheet.append_row(row_list)
                    except Exception as e:
                        st.error(f"❌ Gagal menyimpan jurnal pos pribadi ke GSheets: {str(e)}")
                        
                # PROSES PEMBERSIHAN MEMORI WIDGET SEPERTI SKRIP LAMA ANDA
                kunci_wajib_bersih = ["bulk_parsed", "konten_teks_travel_utama", "asisten_ai_file_input", "fitur_speech_to_text_kayyisa"]
                for kunci in kunci_wajib_bersih:
                    st.session_state.pop(kunci, None)
                    
                st.success("🚀 Sukses! Data tersortir otomatis ke masing-masing tab dan form telah bersih suci kembali.")
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
    # === SUMBER DANA ===
    sumber_dana = st.selectbox(
        "Sumber Dana",
        ["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"]
    )
    
    # === DETAIL DANA ===
    detail_mapping = {
        "Dana Tunai/Cash": [
            "BCA", "Mandiri", "BRI", "BNI", "BSI",
            "Mega", "SeaBank",
            "VA BCA", "VA Mandiri", "VA BRI", "VA BNI",
            "OVO", "DANA", "GOPAY", "ShopeePay", "Sakuku", "Blu Instant", "Biblipay"
        ],
        "Credit Card": [
            "BCA", "Mandiri", "BRI", "BNI", "BSI", "UOB", "Mega", "Allo", "CIMB"
        ],
        "Redeem Point": [
            "Tiket.com Points", "Traveloka Points", "Garuda Miles"
        ]
    }
    
    detail_dana = st.selectbox(
        "Detail Dana",
        [""] + detail_mapping.get(sumber_dana, [])
    )
    
    # === PLATFORM ===
    platform = st.selectbox(
        "Platform",
        ["", "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin",
         "KAI Access", "RedDoorz", "Garuda App", "Citilink App", "Lainnya..."]
    )

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
            "% Laba": pct_laba,
            "Sumber Dana": sumber_dana,
            "Detail Dana": detail_dana,
            "Platform": platform
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
            # === Pastikan kolom baru tersedia ===
            required_cols = ["Sumber Dana", "Detail Dana", "Platform"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = ""

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
                
                row_index = st.number_input(
                    "Pilih baris ke-",
                    min_value=0,
                    max_value=len(df) - 1,
                    step=1
                )
            
                row_data = df.iloc[row_index].to_dict()
                updated_row = {}
            
                # === Mapping Detail Dana ===
                detail_mapping = {
                    "Dana Tunai/Cash": [
                        "BCA", "Mandiri", "BRI", "BNI", "BSI",
                        "Mega", "SeaBank",
                        "VA BCA", "VA Mandiri", "VA BRI", "VA BNI",
                        "OVO", "DANA", "GOPAY", "ShopeePay", "Sakuku", "Blu Instant", "Biblipay"
                    ],
                    "Credit Card": [
                        "BCA", "Mandiri", "BRI", "BNI", "BSI", "UOB", "Mega", "Allo", "CIMB"
                    ],
                    "Redeem Point": [
                        "Tiket.com Points", "Traveloka Points", "Garuda Miles"
                    ]
                }
            
                # === Platform options ===
                platform_options = [
                    "", "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin",
                    "KAI Access", "RedDoorz", "Garuda App", "Citilink App", "Lainnya..."
                ]
            
                # === Render fields ===
                for col, val in row_data.items():
            
                    # 🔹 DATE FIELDS
                    if col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                        try:
                            val = pd.to_datetime(val).date()
                        except:
                            val = date.today()
                        new_val = st.date_input(f"{col}", value=val)
            
                    # 🔹 NUMERIC FIELDS
                    elif col in ["Harga Beli", "Harga Jual"]:
                        new_val = st.number_input(
                            f"{col}",
                            value=float(val) if str(val).strip() != "" else 0.0,
                            step=1000.0,
                            format="%.0f"
                        )
            
                    # 🔹 AUTO-CALCULATED (READ ONLY)
                    elif col in ["Laba", "% Laba"]:
                        st.info(f"{col}: {val}")
                        new_val = val
            
                    # 🔹 SUMBER DANA (dropdown)
                    elif col == "Sumber Dana":
                        new_val = st.selectbox(
                            "Sumber Dana",
                            ["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"],
                            index=(["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"].index(val)
                                   if val in ["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"] else 0)
                        )
            
                    # 🔹 DETAIL DANA (dependent dropdown)
                    elif col == "Detail Dana":
                        sumber_selected = updated_row.get("Sumber Dana", row_data.get("Sumber Dana", ""))
            
                        if sumber_selected in detail_mapping:
                            choices = [""] + detail_mapping[sumber_selected]
                        else:
                            choices = [""]
            
                        new_val = st.selectbox(
                            "Detail Dana",
                            choices,
                            index=(choices.index(val) if val in choices else 0)
                        )
            
                    # 🔹 PLATFORM (dropdown)
                    elif col == "Platform":
                        new_val = st.selectbox(
                            "Platform Pembelian",
                            platform_options,
                            index=(platform_options.index(val) if val in platform_options else 0)
                        )
            
                    # 🔹 TEXT INPUT (default)
                    else:
                        new_val = st.text_input(
                            f"{col}",
                            value=str(val) if pd.notna(val) else ""
                        )
            
                    updated_row[col] = new_val
            
                # === SAVE BUTTON ===
                if st.button("💾 Simpan Perubahan"):
                    for col, val in updated_row.items():
            
                        if col in ["Harga Beli", "Harga Jual"]:
                            try:
                                df.at[row_index, col] = float(val)
                            except:
                                df.at[row_index, col] = 0.0
            
                        elif col in ["Tgl Pemesanan", "Tgl Berangkat"]:
                            try:
                                df.at[row_index, col] = pd.to_datetime(val).date()
                            except:
                                df.at[row_index, col] = date.today()
            
                        elif col not in ["Laba", "% Laba"]:
                            df.at[row_index, col] = val
            
                    # === Recalculate laba ===
                    df.at[row_index, "Laba"] = df.at[row_index, "Harga Jual"] - df.at[row_index, "Harga Beli"]
                    df.at[row_index, "% Laba"] = (
                        round((df.at[row_index, "Laba"] / df.at[row_index, "Harga Beli"]) * 100, 2)
                        if df.at[row_index, "Harga Beli"] > 0 else 0.0
                    )
            
                    st.session_state.bulk_parsed = df
                    st.session_state.edit_mode_bulk = False
                    st.success("✅ Perubahan disimpan.")
                    st.rerun()

        
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

    # Hubungkan langsung ke finance_engine untuk standarisasi angka
    import finance_engine

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
    
        if "Tgl Pemesanan" not in df.columns:
            st.error("❌ Kolom 'Tgl Pemesanan' tidak ditemukan.")
            st.stop()
            
        # ----------------------------------------------------------------------
        # 🛡️ FIX DUPLIKASI: Hapus baris yang kembar identik agar tidak terhitung ganda
        # ----------------------------------------------------------------------
        df = df.dropna(how="all") # Hapus jika ada baris kosongan di GSheets
        df = df.drop_duplicates(keep="first") # Buang 7 duplikat, sisakan 1 data utama yang sah
        # ----------------------------------------------------------------------
    
        # FIX 1: Parsing Tanggal Satu Pintu yang Ketat (DD-MM-YYYY)
        df["Tgl Pemesanan_Parsed"] = pd.to_datetime(df["Tgl Pemesanan"], format="%d-%m-%Y", errors="coerce")
        df = df.dropna(subset=["Tgl Pemesanan_Parsed"])
    
        return df

    if st.button("🔄 Refresh Data", key="btn_refresh_db_lama"):
        st.cache_data.clear()
        df = load_data()
    else:
        df = load_data()

    st.markdown("### 📊 Filter Data")
    
    filter_mode = st.radio(
        "Pilih Jenis Filter Tanggal",
        ["📆 Rentang Tanggal", "🗓️ Bulanan", "📅 Tahunan"],
        horizontal=True,
        key="filter_mode_radio_db_lama"
    )
    
    # Ambil tanggal hari ini mengacu waktu operasional Juni 2026
    today = date.today()
    
    if filter_mode == "📆 Rentang Tanggal":
        default_start = today - timedelta(days=30)
        tgl_awal = st.date_input("Tanggal Awal", default_start, key="db_lama_start")
        tgl_akhir = st.date_input("Tanggal Akhir", today, key="db_lama_end")
    
        if tgl_awal > tgl_akhir:
            tgl_awal, tgl_akhir = tgl_akhir, tgl_awal
            
        # FIX 2: Normalisasi jam agar presisi menyapu hingga akhir hari 23:59:59
        ts_mulai = pd.Timestamp(tgl_awal).normalize()
        ts_akhir = pd.Timestamp(tgl_akhir).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
        df_filtered = df[(df["Tgl Pemesanan_Parsed"] >= ts_mulai) & (df["Tgl Pemesanan_Parsed"] <= ts_akhir)]

    elif filter_mode == "🗓️ Bulanan":
        bulan_nama = {
            "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
            "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11, "Desember": 12
        }
        bulan_label = list(bulan_nama.keys())
        bulan_pilihan = st.selectbox("Pilih Bulan", bulan_label, index=today.month - 1, key="db_lama_month")
        tahun_bulan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan_Parsed"].dt.year.dropna().unique(), reverse=True), key="db_lama_year_m")
        
        df_filtered = df[
            (df["Tgl Pemesanan_Parsed"].dt.month == bulan_nama[bulan_pilihan]) &
            (df["Tgl Pemesanan_Parsed"].dt.year == tahun_bulan)
        ]

    elif filter_mode == "📅 Tahunan":
        tahun_pilihan = st.selectbox("Pilih Tahun", sorted(df["Tgl Pemesanan_Parsed"].dt.year.dropna().unique(), reverse=True), key="db_lama_year_y")
        df_filtered = df[df["Tgl Pemesanan_Parsed"].dt.year == tahun_pilihan]

    if "Keterangan" in df_filtered.columns:
        filter_belum_lunas = st.checkbox("Tampilkan hanya yang Belum Lunas", key="db_lama_unpaid")
        if filter_belum_lunas:
            df_filtered = df_filtered[df_filtered["Keterangan"].str.contains("Belum Lunas", case=False, na=False)]



    # === Filter Tambahan ===
    st.markdown("### 🧍 Filter Tambahan")
    
    tampilkan_uninvoice_saja = st.checkbox("🔍 Tampilkan hanya yang belum ada Invoice", value=True)
    auto_select_25jt = st.checkbox("⚙️ Auto-pilih total penjualan sampai Rp 25 juta")
    
    # Tambahan input baru untuk Nama Customer
    nama_customer_filter = st.text_input("Cari Nama Customer")
    df_filtered["Nama Pemesan"] = (
        df_filtered["Nama Pemesan"]
            .astype(str)
            .str.replace("\u00A0", " ", regex=False)   # NBSP → spasi biasa
            .str.replace(r"\s+", " ", regex=True)      # gabungkan spasi/tab/linebreak
            .str.strip()
    )

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

        import pandas as pd

        def auto_select_smart(df, max_total):
            """
            Auto-select booking untuk mendekati max_total.
            Strategi:
            1️⃣ Prioritas tanggal paling lama
            2️⃣ Pilih subset booking di tiap tanggal untuk mendekati max_total
            3️⃣ Efisien untuk dataset besar
            """
            temp_df = df.copy()
            
            # Pastikan tanggal datetime
            temp_df["Tgl Pemesanan"] = pd.to_datetime(temp_df["Tgl Pemesanan"], errors="coerce")
            
            # Group per Kode Booking → total Harga Jual dan ambil tanggal paling awal
            grouped = temp_df.groupby("Kode Booking").agg({
                "Harga Jual": lambda x: sum(parse_harga(v) for v in x),
                "Tgl Pemesanan": "min"
            }).dropna(subset=["Tgl Pemesanan"]).reset_index()
            
            # Urutkan berdasarkan tanggal paling lama dulu, lalu harga besar
            grouped = grouped.sort_values(by=["Tgl Pemesanan", "Harga Jual"], ascending=[True, False])
            
            selected = []
            total = 0
            
            # Ambil tanggal unik
            unique_dates = grouped["Tgl Pemesanan"].sort_values().unique()
            
            for date in unique_dates:
                daily = grouped[grouped["Tgl Pemesanan"] == date].copy()
                # Sort harga besar dulu di tanggal ini
                daily = daily.sort_values(by="Harga Jual", ascending=False)
                
                for _, row in daily.iterrows():
                    harga = row["Harga Jual"]
                    if total + harga <= max_total:
                        selected.append(row["Kode Booking"])
                        total += harga
                
                # Jika max_total sudah tercapai, hentikan loop
                if total >= max_total:
                    break
            
            return selected


        MAX_TOTAL = 25_000_000
        if auto_select_25jt:

            best_bookings = auto_select_smart(
                editable_df,
                MAX_TOTAL
            )
        
            editable_df["Pilih"] = False
        
            editable_df.loc[
                editable_df["Kode Booking"].isin(best_bookings),
                "Pilih"
            ] = True

        if "editable_df" not in st.session_state:
            st.session_state.editable_df = editable_df

        if not st.session_state.editable_df.equals(editable_df):
            st.session_state.editable_df = editable_df.copy()
            st.session_state.editable_df["Pilih"] = False

        if auto_select_25jt:

            best_bookings = auto_select_smart(
                st.session_state.editable_df,
                MAX_TOTAL
            )
        
            st.session_state.editable_df["Pilih"] = False
        
            st.session_state.editable_df.loc[
                st.session_state.editable_df["Kode Booking"].isin(best_bookings),
                "Pilih"
            ] = True

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
        
                row_to_edit = selected_data.iloc[0]
        
                # ===== Fungsi bantu amankan tanggal =====
                def safe_date(val):
                    return None if pd.isna(val) else val.date()

        
                # ============================
                # === INPUT FIELD EDIT MODE ===
                # ============================
                tgl_pemesanan_val = safe_date(row_to_edit["Tgl Pemesanan"])
                tgl_berangkat_val = safe_date(row_to_edit["Tgl Berangkat"])
                nama_pemesan_form = st.text_input("Nama Pemesan", row_to_edit.get("Nama Pemesan", ""), key="edit_nama_pemesan")
                tgl_pemesanan_form = st.date_input("Tgl Pemesanan", value=tgl_pemesanan_val if tgl_pemesanan_val else date.today(), key="edit_tgl_pemesanan")
                tgl_berangkat_form = st.date_input("Tgl Berangkat", value=tgl_berangkat_val if tgl_berangkat_val else date.today(), key="edit_tgl_berangkat")
                kode_booking_form = st.text_input("Kode Booking", row_to_edit.get("Kode Booking", ""), key="edit_kode_booking")
                no_penerbangan_form = st.text_input("No Penerbangan / Hotel / Kereta", row_to_edit.get("No Penerbangan / Hotel / Kereta", ""), key="edit_no_penerbangan")
                nama_customer_form = st.text_input("Nama Customer", row_to_edit.get("Nama Customer", ""), key="edit_nama_customer")
                rute_form = st.text_input("Rute", row_to_edit.get("Rute", ""), key="edit_rute")
                harga_beli_form = st.number_input("Harga Beli", value=parse_harga(row_to_edit.get("Harga Beli", 0)), format="%.0f", key="edit_harga_beli")
                harga_jual_form = st.number_input("Harga Jual", value=parse_harga(row_to_edit.get("Harga Jual", 0)), format="%.0f", key="edit_harga_jual")
                no_invoice_form = st.text_input("No Invoice", row_to_edit.get("No Invoice", ""), key="edit_no_invoice")
                keterangan_form = st.text_input("Keterangan", row_to_edit.get("Keterangan", ""), key="edit_keterangan")
                admin_form = st.text_input("Admin", row_to_edit.get("Admin", ""), key="edit_admin")
        
                # ===========================================
                # === BARU: SUMBER DANA / DETAIL DANA / PLATFORM ===
                # ===========================================
        
                sumber_dana_form = st.selectbox(
                    "Sumber Dana",
                    ["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"],
                    index=(["", "Dana Tunai/Cash", "Credit Card", "Redeem Point"]
                           .index(row_to_edit.get("Sumber Dana", ""))),
                    key="edit_sumber_dana"
                )
        
                # Mapping detail dana
                detail_mapping = {
                    "Dana Tunai/Cash": [
                        "BCA", "Mandiri", "BRI", "BNI", "BSI",
                        "Mega", "SeaBank",
                        "VA BCA", "VA Mandiri", "VA BRI", "VA BNI",
                        "OVO", "DANA", "GOPAY", "ShopeePay", "Sakuku", "Blu Instant", "Biblipay"
                    ],
                    "Credit Card": [
                        "BCA", "Mandiri", "BRI", "BNI", "BSI", "UOB", "Mega", "Allo", "CIMB"
                    ],
                    "Redeem Point": [
                        "Tiket.com Points", "Traveloka Points", "Garuda Miles"
                    ]
                }
        
                detail_choices = [""] + detail_mapping.get(sumber_dana_form, [])
        
                detail_dana_form = st.selectbox(
                    "Detail Dana",
                    detail_choices,
                    index=(detail_choices.index(row_to_edit.get("Detail Dana", ""))
                           if row_to_edit.get("Detail Dana", "") in detail_choices else 0),
                    key="edit_detail_dana"
                )
        
                platform_choices = [
                    "", "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin",
                    "KAI Access", "RedDoorz", "Garuda App", "Citilink App", "Lainnya..."
                ]
        
                platform_form = st.selectbox(
                    "Platform",
                    platform_choices,
                    index=(platform_choices.index(row_to_edit.get("Platform", ""))
                           if row_to_edit.get("Platform", "") in platform_choices else 0),
                    key="edit_platform"
                )
        
                # ===========================================
                # === SIMPAN PERUBAHAN KE GSheet ===
                # ===========================================
        
                if st.button("💾 Simpan Perubahan ke GSheet"):
                    try:
                        worksheet = connect_to_gsheet(SHEET_ID, WORKSHEET_NAME)
                        all_data = worksheet.get_all_records()
                        df_all = pd.DataFrame(all_data)
        
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
                                "No Invoice": no_invoice_form,
                                "Keterangan": keterangan_form,
                                "Admin": admin_form,
        
                                # ==== BARU TAMBAHAN ====
                                "Sumber Dana": sumber_dana_form,
                                "Detail Dana": detail_dana_form,
                                "Platform": platform_form
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
                            for col in ["Nama Pemesan", "Kode Booking", "Tgl Berangkat", "Nama Customer", "No Penerbangan / Hotel / Kereta"]:
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
                                (df_all["Nama Customer_str"] == row["Nama Customer_str"]) &
                                (df_all["No Penerbangan / Hotel / Kereta_str"] == row["No Penerbangan / Hotel / Kereta_str"])
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

        
    
        total_harga_jual = df_filtered['Harga Jual'].apply(finance_engine.bersihkan_angka).sum()
        total_laba = df_filtered['Laba'].apply(finance_engine.bersihkan_angka).sum()
        
                # === Kode Cetak Total & Sukses Anda yang Sudah Berjalan Lancar ===
        st.markdown(f"**Total Harga Jual Hasil Filter: Rp {total_harga_jual:,.0f}**.af".replace(",", ".").replace(".af", ""))
        st.markdown(f"**Total Laba Hasil Filter: Rp {total_laba:,.0f}**.af".replace(",", ".").replace(".af", ""))
        
        if total_harga_jual >= MAX_TOTAL:
            st.success(f"✅ Total penjualan mencapai Rp {total_harga_jual:,.0f} (batas 25 juta tercapai)".replace(",", "."))
        elif total_harga_jual >= MAX_TOTAL * 0.99:
            st.warning(f"⚠️ Total penjualan mendekati batas: Rp {total_harga_jual:,.0f}".replace(",", "."))
        
        # =========================================================================
        # 🔧 FIX LOGIKA: Menghitung Data yang Belum Punya Invoice Menggunakan Variabel V2
        # =========================================================================
        
        # 1. Pastikan rentang waktu terdefinisi dengan aman baik untuk mode Rentang, Bulanan, maupun Tahunan
        if filter_mode == "📆 Rentang Tanggal":
            tgl_awal_calc = pd.Timestamp(tgl_awal).normalize()
            tgl_akhir_calc = pd.Timestamp(tgl_akhir).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        elif filter_mode == "🗓️ Bulanan":
            # Jika memilih bulanan, kunci batas dari tanggal 1 hingga akhir bulan yang dipilih
            tgl_awal_calc = pd.Timestamp(year=tahun_bulan, month=bulan_nama[bulan_pilihan], day=1)
            tgl_akhir_calc = (tgl_awal_calc + pd.offsets.MonthEnd(1)) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        else:
            # Jika tahunan, kunci dari 1 Januari hingga 31 Desember
            tgl_awal_calc = pd.Timestamp(year=tahun_pilihan, month=1, day=1)
            tgl_akhir_calc = pd.Timestamp(year=tahun_pilihan, month=12, day=31, hour=23, minute=59, second=59)

        # 2. Saring dataframe master (df) menggunakan kolom 'Tgl Pemesanan_Parsed' yang sudah aman dan seragam
        uninvoice_df = df[
            (df["Tgl Pemesanan_Parsed"] >= tgl_awal_calc) &
            (df["Tgl Pemesanan_Parsed"] <= tgl_akhir_calc) &
            (
                df["No Invoice"].isna() |
                (df["No Invoice"].astype(str).str.strip() == "") |
                (df["No Invoice"].astype(str).str.lower() == "nan")
            )
        ]
        
        # 3. Jalankan filter pencarian nama jika parameter nama_filter aktif di sistem Anda
        if 'nama_filter' in locals() or 'nama_filter' in globals():
            if nama_filter:
                uninvoice_df = uninvoice_df[uninvoice_df["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
        
        # 4. Gunakan mesin pembersih angka dari finance_engine agar hitungan uninvoice akurat 100%
        total_uninvoice = uninvoice_df["Harga Jual"].apply(finance_engine.bersihkan_angka).sum()
        
        # Cetak info uninvoice jika diperlukan di UI Anda
        if total_uninvoice > 0:
            st.info(f"📋 Terdeteksi total nilai penjualan tanpa nomor invoice sebesar: Rp {total_uninvoice:,.0f}".replace(",", "."))

        
        # Tampilkan notifikasi di sidebar
        with st.sidebar:
            st.markdown("---")
            
            # Greeting profesional di sidebar
            st.markdown("""
            <div style="padding: 10px; border-radius: 10px; background-color: #34495e; color: #ecf0f1; margin-bottom: 20px;">
                <h3 style="color:#f39c12; margin-bottom:5px;">Selamat Datang di Management Dashboard | Kayyisa Tour & Travel</h3>
                <p style="font-size:0.9em; margin:0 0 10px 0;">
                Platform ini memberikan visibilitas penuh atas kinerja bisnis perusahaan, menyatukan data keuangan dan operasional dalam satu tampilan yang mudah dipahami, sehingga memungkinkan strategi yang lebih efisien dan tepat sasaran.
                </p>
                <p style="font-size:0.9em; margin:0;">
                Sistem ini dirancang untuk memudahkan manajemen operasional dan keuangan perusahaan, memberikan informasi secara real-time, serta mendukung pengambilan keputusan yang cepat dan tepat untuk pertumbuhan bisnis yang berkelanjutan.
                </p>
            </div>
            """, unsafe_allow_html=True)

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
            # ============================
            # OPSI PEMILIHAN NAMA PEMESAN
            # ============================
            
            opsi_nama = st.radio(
                "Pilih sumber Nama Pemesan:",
                ("Gunakan Nama Customer", "Input Manual")
            )
            
            if opsi_nama == "Gunakan Nama Customer":
                # Ambil nama dari baris pertama data
                try:
                    nama_customer_awal = selected_data["Nama Customer"].iloc[0]
                except:
                    nama_customer_awal = "Pelanggan"
                nama_pemesan = f"Bapak/Ibu {nama_customer_awal}"
            else:
                # Admin mengetik sendiri
                nama_pemesan = st.text_input("Masukkan Nama Pemesan:", "")
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
                        status_lunas=status_lunas,
                        nama_pemesan=nama_pemesan
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

#======================GENERATOR TIKET BARU==========================================
with st.expander("🎫 Generator AI E-Tiket"):

    tipe_tiket_ai = st.radio("Pilih tipe tiket:", ["Kereta", "Whoosh", "Hotel"], key="tipe_tiket_radio_ai_new")
    st.session_state['tipe_tiket_ai'] = tipe_tiket_ai

    # Template default berdasarkan tipe tiket
    if tipe_tiket_ai == "Hotel":
        default_text_ai = "Order ID:\nItinerary ID:\n\nHarga "
    else:
        default_text_ai = "Kode booking: "

    # Mengubah nama input_key agar unik khusus untuk AI
    input_key_ai = f"input_text_ai_{tipe_tiket_ai}"
    if input_key_ai not in st.session_state:
        st.session_state[input_key_ai] = default_text_ai

    # Area input teks manifest khusus AI
    input_text_ai = st.text_area(
        f"Tempelkan teks tiket {tipe_tiket_ai}",
        value=st.session_state[input_key_ai],
        height=300,
        key=input_key_ai
    )

    # 1. TOMBOL GENERATE UTAMA (Murni Mengisi Memori Session State)
    if st.button("Generate Tiket AI", key="btn_generate_ai_master_key", use_container_width=True):
        if input_text_ai.strip() and input_text_ai != default_text_ai:
            with st.spinner(f"AI Gemini 3.1 sedang mengekstrak manifest {tipe_tiket_ai} (EYD Baku)..."):
                
                # Memanggil modul parsing AI dari generatornew.py
                if tipe_tiket_ai in ["Kereta", "Whoosh"]:
                    data_ai = generatornew.parse_input_dynamic(input_text_ai.strip())
                elif tipe_tiket_ai == "Hotel":
                    data_ai = generatornew.parse_evoucher_text(input_text_ai.strip())
                
                if data_ai:
                    # Kunci data hasil parsing ke state permanen agar aman saat soft refresh Android
                    st.session_state['last_data_ai'] = data_ai
                    st.session_state['tipe_tiket_ai'] = tipe_tiket_ai
                    st.success("🎉 AI Gemini 3.1 sukses menstrukturkan data secara presisi!")
                else:
                    st.error("AI gagal mengekstrak data. Periksa teks masukan Anda.")
        else:
            st.warning("Silakan masukkan data tiket terlebih dahulu.")

    # =====================================================================
    # 2. LOGIKA PROSES UPLOAD (Dipindahkan ke Bawah Setelah Tombol Sukses)
    # =====================================================================
    if 'last_data_ai' in st.session_state and st.session_state.get('tipe_tiket_ai') == "Whoosh" and tipe_tiket_ai == "Whoosh":
        data_aktif_ai = st.session_state['last_data_ai']
        st.markdown("#### 📷 Kolom Upload QR Code Asli Whoosh")
        
        for index, penumpang in enumerate(data_aktif_ai.get("penumpang", []), start=1):
            placeholder_key = penumpang.get("qr_placeholder_key", f"qr_penumpang_{index}")
            st.caption(f"🔹 **Passenger {index}: {penumpang.get('nama', '-')} ({penumpang.get('kursi', '-')})**")
            
            file_qr_uploaded = st.file_uploader(
                f"Pilih screenshot QR Code untuk {penumpang.get('nama', '-')}",
                type=["png", "jpg", "jpeg"],
                key=f"uploader_bin_ai_key_{placeholder_key}"
            )
            if file_qr_uploaded is not None:
                st.session_state[placeholder_key] = file_qr_uploaded

    # =====================================================================
    # 3. TAMPILKAN PRATINJAU VISUAL HTML (Membaca Data Kamus State Hasil AI)
    # =====================================================================
    if 'last_data_ai' in st.session_state and st.session_state.get('tipe_tiket_ai') == tipe_tiket_ai:
        data_render_ai = st.session_state['last_data_ai']
        try:
            if tipe_tiket_ai in ["Kereta", "Whoosh"]:
                html_ai = generatornew.generate_eticket(data_render_ai)
            elif tipe_tiket_ai == "Hotel":
                html_ai = generatornew.generate_evoucher_html(data_render_ai)
                
            st.components.v1.html(html_ai, height=800, scrolling=True)
        except Exception as e:
            st.warning(f"⚠️ Gagal membuat tampilan tiket: {e}")


#=====================================================================================

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
from gspread.exceptions import APIError


# ---------------------------
# Config
# ---------------------------
SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# ---------------------------
# Helper: format Rupiah
# ---------------------------
def format_rp(x):
    try:
        return f"Rp {x:,.0f}"
    except Exception:
        return f"Rp 0"

# ---------------------------
# Small metric card helper (simple HTML card)
# ---------------------------
card_style = """
    <style>
    .metric-card {
        background: #ffffff;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        text-align: center;
        border: 1px solid #e6e6e6;
    }
    .metric-title {
        font-size: 18px;
        font-weight: 600;
        color: #555;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #000;
        margin-top: 6px;
    }
    </style>
    """
st.markdown(card_style, unsafe_allow_html=True)
    
def metric_card(title, value):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ---------------------------
# Clean price column
# ---------------------------
def clean_price_column(col):
    col = col.fillna("").astype(str)
    col = col.str.replace(r"[^\d]", "", regex=True)
    col = col.replace("", "0")
    return col.astype(float)

# ---------------------------
# GSheet connector
# ---------------------------
def connect_to_gsheet(SHEET_ID, worksheet_name="Arus Kas"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets.get("gcp_service_account")
    if not creds_dict:
        raise Exception("Missing gcp_service_account in Streamlit secrets")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet(worksheet_name)

# ---------------------------
# Utility: ensure columns present
# ---------------------------
def clean_price_column(col):
    col = col.fillna("").astype(str)
    col = col.str.replace(r"[^\d]", "", regex=True)

    # Jika terlalu panjang, batasi max 12 digit (maks 999 miliar)
    col = col.apply(lambda x: x[:12])

    col = col.replace("", "0")
    return pd.to_numeric(col, errors="coerce").fillna(0)


def safe_first(df, col):
    if col not in df.columns: 
        return ""
    if df.empty:
        return ""
    return df[col].iloc[0]

@st.cache_data(ttl=600)  # cache 10 menit
def load_sheet(sheet_id, worksheet_name):
    try:
        ws = connect_to_gsheet(sheet_id, worksheet_name)
        records = ws.get_all_records()
        df = pd.DataFrame(records)
    except Exception:
        st.warning(f"Tidak bisa ambil sheet '{worksheet_name}'. Menggunakan data kosong.")
        df = pd.DataFrame()
    return df
    

# ---------------------------------------
# Clean angka Rupiah
# ---------------------------------------
def clean_price(x):
    x = str(x)
    x = re.sub(r"[^\d]", "", x)
    return float(x) if x else 0

def _ensure_columns(df, cols):
    """
    Pastikan dataframe df punya semua kolom di list cols.
    Jika kolom tidak ada, buat dengan nilai default kosong atau NaN.
    """
    for c in cols:
        if c not in df.columns:
            df[c] = "" if df.empty else pd.NA
    return df


# ---------------------------------------
# Fungsi utama (HYBRID)
# ---------------------------------------
def parse_financial_data(df_data, df_cashflow_existing):
    import pandas as pd

    # --- SAFETY HANDLING ---
    if df_data.empty and df_cashflow_existing.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # --- CLEANING DATA ---
    def clean_price(x):
        if pd.isna(x):
            return 0
        if isinstance(x, str):
            return float(x.replace("Rp", "").replace(",", "").strip())
        return float(x)

    for col in ["Harga Beli", "Harga Jual"]:
        if col in df_data.columns:
            df_data[col] = df_data[col].apply(clean_price)
        else:
            df_data[col] = 0.0

    df_data["No Invoice"] = df_data.get("No Invoice", "").fillna("").astype(str)
    df_data["Nama Pemesan"] = df_data.get("Nama Pemesan", "").astype(str)
    df_data["Keterangan"] = df_data.get("Keterangan", "").astype(str)
    df_data["Tgl Pemesanan"] = pd.to_datetime(
        df_data.get("Tgl Pemesanan", pd.NaT), dayfirst=True, errors="coerce"
    )

    for col in ["Sumber Dana", "Detail Dana", "Platform"]:
        if col not in df_data.columns:
            df_data[col] = ""

    # --- GENERATE INVOICE_KEY ---
    df_data["Invoice_Key"] = df_data.apply(
        lambda x: f"{x['Nama Pemesan']}_{x['No Invoice']}" if x["No Invoice"] else f"{x['Nama Pemesan']}_MANUAL_{x.name}",
        axis=1
    )

    # --- EXISTING KEYS ---
    existing_keys = set(df_cashflow_existing.get("Invoice_Key", []))

    cashflow_rows = []
    piutang_rows = []
    hutang_cc_rows = []
    jurnal_rows = []

    # --- 1. LOOP PER INVOICE BARU ---
    for key, group in df_data.groupby("Invoice_Key"):

        # Skip jika invoice sudah ada di cashflow, tapi tetap buat jurnal nanti
        if key in existing_keys:
            continue

        nama = group["Nama Pemesan"].iloc[0]
        invoice_no = group["No Invoice"].iloc[0]
        tgl = group["Tgl Pemesanan"].min()

        sumber_dana = group["Sumber Dana"].iloc[0].strip().lower()
        detail = group["Detail Dana"].iloc[0]
        platform = group["Platform"].iloc[0]

        total_modal = group["Harga Beli"].sum()
        total_jual = group["Harga Jual"].sum()

        # --- STATUS ---
        status = "Lunas"
        if invoice_no == "" or any("Belum Lunas" in x for x in group["Keterangan"]):
            status = "Belum Lunas"

        # --- MODAL ---
        if "credit" in sumber_dana or "kartu" in sumber_dana or "cc" in sumber_dana:
            kategori_modal = "Penjualan (Credit Card)"
        elif "redeem" in sumber_dana or "point" in sumber_dana:
            kategori_modal = "Penjualan (Redeem Points)"
            total_modal = 0
        else:
            kategori_modal = "Penjualan (Cash/Tunai)"

        # --- CASHFLOW KELUAR ---
        cashflow_rows.append({
            "Tanggal": tgl,
            "Tipe": "Keluar",
            "Kategori": kategori_modal,
            "No Invoice": invoice_no,
            "Keterangan": "; ".join(group["Keterangan"].unique()),
            "Jumlah": total_modal,
            "Sumber": "Data Otomatis",
            "Invoice_Key": key,
            "Nama Pemesan": nama,
            "Sumber Dana": sumber_dana,
            "Detail Dana": detail,
            "Platform": platform,
        })

        # --- CASHFLOW MASUK (Pelunasan Customer) ---
        total_bayar = total_jual if status == "Lunas" else 0
        if total_bayar > 0:
            cashflow_rows.append({
                "Tanggal": tgl,
                "Tipe": "Masuk",
                "Kategori": "Pembayaran Customer",
                "No Invoice": invoice_no,
                "Keterangan": "; ".join(group["Keterangan"].unique()),
                "Jumlah": total_bayar,
                "Sumber": "Data Otomatis",
                "Invoice_Key": key,
                "Nama Pemesan": nama,
                "Sumber Dana": "Customer",
                "Detail Dana": "-",
                "Platform": platform,
            })

        # --- PIUTANG ---
        sisa = total_jual - total_bayar
        if sisa > 0:
            piutang_rows.append({
                "Invoice_Key": key,
                "No Invoice": invoice_no,
                "Nama Pemesan": nama,
                "Total": total_jual,
                "Terbayar": total_bayar,
                "Sisa": sisa,
                "Status": "Belum Lunas",
            })

        # --- HUTANG CC ---
        if kategori_modal == "Penjualan (Credit Card)":
            hutang_cc_rows.append({
                "Invoice_Key": key,
                "Tanggal": tgl,
                "Nama Pemesan": nama,
                "Jumlah": total_modal,
                "Bank": sumber_dana,
                "Status": "Belum Dibayar CC"
            })

        # --- JURNAL BARU ---
        # 1. HPP
        jurnal_rows.append({
            "Invoice_Key": key,
            "Tanggal": tgl,
            "Keterangan": f"HPP invoice {invoice_no}",
            "Debit": "HPP",
            "Kredit": "Persediaan",
            "Jumlah": total_modal,  # pastikan nominal modal masuk
        })
        # 2. Penjualan
        jurnal_rows.append({
            "Invoice_Key": key,
            "Tanggal": tgl,
            "Keterangan": f"Penjualan invoice {invoice_no}",
            "Debit": "Kas" if total_bayar > 0 else "Piutang",
            "Kredit": "Penjualan",
            "Jumlah": total_jual,  # pastikan nominal penjualan masuk
        })
        # 3. Hutang CC
        if kategori_modal == "Penjualan (Credit Card)":
            jurnal_rows.append({
                "Invoice_Key": key,
                "Tanggal": tgl,
                "Keterangan": f"Modal CC invoice {invoice_no}",
                "Debit": "Persediaan",
                "Kredit": "Hutang Kartu Kredit",
                "Jumlah": total_modal,  # nominal modal via CC
            })
    # --- 2. LOOP CASHFLOW EXISTING UNTUK JURNAL PELUNASAN ---
    if not df_cashflow_existing.empty:
        # Pastikan jumlah numeric
        df_cashflow_existing["Jumlah"] = df_cashflow_existing["Jumlah"].replace('[Rp,]', '', regex=True).astype(float)

        for idx, row in df_cashflow_existing.iterrows():
            key = row.get("Invoice_Key", "")
            if not key:
                continue
            tipe = row.get("Tipe", "")
            no_invoice = row.get("No Invoice", "")
            tgl = row.get("Tanggal")
            jumlah = row.get("Jumlah", 0)
            keterangan = row.get("Keterangan", "")

            if jumlah <= 0:
                continue

            if tipe == "Masuk":
                jurnal_rows.append({
                    "Invoice_Key": key,
                    "Tanggal": tgl,
                    "Keterangan": f"Pelunasan invoice {no_invoice} - {keterangan}",
                    "Debit": "Kas",
                    "Kredit": "Piutang",
                    "Jumlah": jumlah,
                })
            elif tipe == "Keluar":
                jurnal_rows.append({
                    "Invoice_Key": key,
                    "Tanggal": tgl,
                    "Keterangan": f"Pengeluaran invoice {no_invoice} - {keterangan}",
                    "Debit": "HPP",
                    "Kredit": "Persediaan",
                    "Jumlah": jumlah,
                })

    # --- RETURN 4 DATAFRAME ---
    return (
        pd.DataFrame(cashflow_rows),
        pd.DataFrame(piutang_rows),
        pd.DataFrame(hutang_cc_rows),
        pd.DataFrame(jurnal_rows)
    )


@st.cache_resource
def get_ws(sheet_id, worksheet_name):
    """
    Cache worksheet connection agar tidak reconnect terus ke GSheet
    """
    return connect_to_gsheet(sheet_id, worksheet_name)


@st.cache_data(ttl=300)
def load_sheet_cached(sheet_id, worksheet_name):
    """
    Cache dataframe selama 5 menit
    """
    ws = get_ws(sheet_id, worksheet_name)
    return pd.DataFrame(ws.get_all_records())


def refresh_cached_data():
    """
    Refresh cache manual setelah save/update data
    """
    st.cache_data.clear()

    st.session_state.df_data = load_sheet_cached(SHEET_ID, "Data")
    st.session_state.df_cashflow_existing = load_sheet_cached(SHEET_ID, "Arus Kas")


# =========================================================
# JURNAL AKUNTANSI
# =========================================================
with st.expander("📘 Jurnal Akuntansi"):

    # =====================================================
    # LOAD DATA (CACHED)
    # =====================================================
    if "df_data" not in st.session_state:
        st.session_state.df_data = load_sheet_cached(SHEET_ID, "Data")

    if "df_cashflow_existing" not in st.session_state:
        st.session_state.df_cashflow_existing = load_sheet_cached(
            SHEET_ID,
            "Arus Kas"
        )

    df_data = st.session_state.df_data.copy()
    df_cashflow_existing = (
        st.session_state.df_cashflow_existing.copy()
    )

    # =====================================================
    # NORMALISASI DATA
    # =====================================================
    if not df_data.empty:

        # -----------------------------
        # Numeric Columns
        # -----------------------------
        for col in ["Harga Beli", "Harga Jual"]:

            if col in df_data.columns:
                df_data[col] = clean_price_column(df_data[col])
            else:
                df_data[col] = 0.0

        # -----------------------------
        # Required Columns
        # -----------------------------
        required_cols = [
            "Keterangan",
            "No Invoice",
            "Nama Pemesan",
            "Sumber Dana",
            "Detail Dana",
            "Platform",
            "Card_Account",
            "Paid_Amount"
        ]

        for col in required_cols:
            if col not in df_data.columns:
                df_data[col] = ""

        # -----------------------------
        # Date Parsing
        # -----------------------------
        df_data["Tgl Pemesanan"] = pd.to_datetime(
            df_data.get("Tgl Pemesanan", pd.NaT),
            dayfirst=True,
            errors="coerce"
        )

        # -----------------------------
        # Invoice Key
        # -----------------------------
        df_data["No Invoice"] = (
            df_data["No Invoice"]
            .fillna("")
            .astype(str)
        )

        df_data["Nama Pemesan"] = (
            df_data["Nama Pemesan"]
            .fillna("")
            .astype(str)
        )

        df_data["Invoice_Key"] = df_data.apply(
            lambda x:
                f"{x['Nama Pemesan']}_MANUAL_{x.name}"
                if x["No Invoice"] == ""
                else f"{x['Nama Pemesan']}_{x['No Invoice']}",
            axis=1
        )

    else:

        df_data = pd.DataFrame(columns=[
            "Tgl Pemesanan",
            "Harga Beli",
            "Harga Jual",
            "Keterangan",
            "No Invoice",
            "Nama Pemesan",
            "Sumber Dana",
            "Detail Dana",
            "Platform",
            "Invoice_Key"
        ])

    # =====================================================
    # PARSE FINANCIAL DATA
    # =====================================================
    (
        df_cf_auto,
        df_piutang_auto,
        df_hutang_cc_auto,
        df_journal_auto
    ) = parse_financial_data(
        df_data,
        df_cashflow_existing
    )

    # =====================================================
    # CASHFLOW COMBINED
    # =====================================================
    df_cashflow_combined = pd.concat(
        [
            (
                df_cashflow_existing
                if not df_cashflow_existing.empty
                else pd.DataFrame()
            ),

            (
                df_cf_auto
                if not df_cf_auto.empty
                else pd.DataFrame()
            ),

            pd.DataFrame(
                st.session_state.get(
                    "cashflow_manual",
                    []
                )
            )
        ],
        ignore_index=True
    )

    # =====================================================
    # ENSURE REQUIRED COLUMNS
    # =====================================================
    required_cf_cols = [
        "Tanggal",
        "Tipe",
        "Kategori",
        "No Invoice",
        "Keterangan",
        "Jumlah",
        "Status",
        "Sumber",
        "Nama Pemesan",
        "Invoice_Key",
        "Sumber Dana",
        "Detail Dana",
        "Platform",
        "Akun"
    ]

    for c in required_cf_cols:
        if c not in df_cashflow_combined.columns:
            df_cashflow_combined[c] = None

    # =====================================================
    # CLEAN DATA TYPES
    # =====================================================
    df_cashflow_combined["Jumlah"] = pd.to_numeric(
        df_cashflow_combined["Jumlah"],
        errors="coerce"
    ).fillna(0.0)

    df_cashflow_combined["Tanggal"] = pd.to_datetime(
        df_cashflow_combined["Tanggal"],
        errors="coerce"
    )

    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================
    df_cashflow_combined = (
        df_cashflow_combined
        .drop_duplicates()
    )

    # =====================================================
    # FILTER CREDIT CARD
    # =====================================================
    df_cashflow_combined["Sumber Dana"] = (
        df_cashflow_combined["Sumber Dana"]
        .fillna("")
        .astype(str)
    )

    credit_mask = (
        df_cashflow_combined["Sumber Dana"]
        .str.lower()
        .str.contains(
            "credit|cc|kartu|card|kart",
            na=False
        )
    )

    df_cash_only = (
        df_cashflow_combined[
            ~(
                (
                    df_cashflow_combined["Tipe"] == "Keluar"
                )
                & credit_mask
            )
        ]
        .copy()
    )

    df_cash_only = (
        df_cash_only
        .dropna(subset=["Tanggal"])
    )

    # =====================================================
    # TOTALS
    # =====================================================
    total_masuk = (
        df_cash_only
        .query("Tipe=='Masuk'")["Jumlah"]
        .sum()
        if not df_cash_only.empty
        else 0.0
    )

    total_keluar = (
        df_cash_only
        .query("Tipe=='Keluar'")["Jumlah"]
        .sum()
        if not df_cash_only.empty
        else 0.0
    )

    saldo = total_masuk - total_keluar

    # =====================================================
    # PIUTANG
    # =====================================================
    list_piutang = []
    piutang_total = 0.0

    if not df_data.empty:

        for inv_key, group in df_data.groupby("Invoice_Key"):

            total_harga_jual = (
                group["Harga Jual"].sum()
            )

            total_sudah_diterima = (
                df_cash_only[
                    (
                        df_cash_only["Invoice_Key"]
                        == inv_key
                    )
                    &
                    (
                        df_cash_only["Tipe"]
                        == "Masuk"
                    )
                ]["Jumlah"].sum()
                if not df_cash_only.empty
                else 0.0
            )

            sisa_piutang = max(
                0.0,
                total_harga_jual - total_sudah_diterima
            )

            if sisa_piutang > 0:

                piutang_total += sisa_piutang

                inv_no = (
                    group["No Invoice"].iloc[0]
                    if group["No Invoice"].iloc[0]
                    else f"MANUAL_{group.index[0]}"
                )

                list_piutang.append([
                    inv_no,
                    total_harga_jual,
                    total_sudah_diterima,
                    sisa_piutang
                ])

    df_piutang = (
        pd.DataFrame(
            list_piutang,
            columns=[
                "Invoice",
                "Total",
                "Terbayar",
                "Sisa"
            ]
        )
        if list_piutang
        else pd.DataFrame(
            columns=[
                "Invoice",
                "Total",
                "Terbayar",
                "Sisa"
            ]
        )
    )

    # =====================================================
    # HUTANG CREDIT CARD
    # =====================================================
    df_hutang_cc_combined = (
        df_hutang_cc_auto.copy()
        if not df_hutang_cc_auto.empty
        else pd.DataFrame()
    )

    if not df_hutang_cc_combined.empty:

        df_hutang_cc_combined["Jumlah"] = pd.to_numeric(
            df_hutang_cc_combined["Jumlah"],
            errors="coerce"
        ).fillna(0.0)

        summary_hutang = (
            df_hutang_cc_combined
            .groupby("Bank", as_index=False)
            .agg({"Jumlah": "sum"})
            .query("Jumlah != 0")
        )

    else:

        summary_hutang = pd.DataFrame(
            columns=["Bank", "Jumlah"]
        )

    # =====================================================
    # JURNAL COMBINED
    # =====================================================
    df_journal_combined = pd.concat(
        [
            pd.DataFrame(
                st.session_state.get(
                    "journal_manual",
                    []
                )
            ),

            (
                df_journal_auto
                if not df_journal_auto.empty
                else pd.DataFrame()
            )
        ],
        ignore_index=True
    )

    journal_cols = [
        "Tanggal",
        "Ref",
        "Akun_Debit",
        "Debit",
        "Akun_Kredit",
        "Kredit",
        "Keterangan"
    ]

    for c in journal_cols:
        if c not in df_journal_combined.columns:
            df_journal_combined[c] = None

    df_journal_combined["Tanggal"] = pd.to_datetime(
        df_journal_combined["Tanggal"],
        errors="coerce"
    )

    df_journal_combined = (
        df_journal_combined
        .dropna(subset=["Tanggal"])
        .drop_duplicates(
            subset=journal_cols,
            keep="last"
        )
    )

    # =====================================================
    # DISPLAY HUTANG CC
    # =====================================================
    if summary_hutang.empty:

        st.markdown(
            f"""
            <div style="
                background-color:#d9edf7;
                padding:15px;
                border-radius:5px;
                border-left:5px solid #31708f;
                border-right:5px solid #31708f;
                text-align:center;
                font-weight:bold;
                color:#31708f;
                font-size:24px;
            ">
                💳 Belum ada hutang kartu tercatat.
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        for _, r in summary_hutang.iterrows():

            st.markdown(
                f"""
                <div style="
                    background-color:#d9edf7;
                    padding:15px;
                    border-radius:5px;
                    border-left:5px solid #31708f;
                    border-right:5px solid #31708f;
                    text-align:center;
                    font-weight:bold;
                    color:#31708f;
                    font-size:24px;
                ">
                    💳 Sisa Hutang Kartu Kredit ({r['Bank']}):
                    {format_rp(r['Jumlah'])}
                </div>
                """,
                unsafe_allow_html=True
            )

    # =====================================================
    # METRICS
    # =====================================================
    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "💰 Total Pemasukan",
            format_rp(total_masuk)
        )

    with col2:
        metric_card(
            "📤 Total Pengeluaran (non Credit Card)",
            format_rp(total_keluar)
        )

    col3, col4 = st.columns(2)

    with col3:
        metric_card(
            "🏦 Saldo Akhir",
            format_rp(saldo)
        )

    with col4:
        metric_card(
            "🧾 Piutang Belum Lunas",
            format_rp(piutang_total)
        )

    # =====================================================
    # DISPLAY JURNAL
    # =====================================================
    st.subheader(
        "📘 Jurnal Akuntansi (Auto Generated)"
    )

    if not df_journal_combined.empty:

        if "Jumlah" in df_journal_combined.columns:

            df_journal_combined["Jumlah"] = (
                df_journal_combined["Jumlah"]
                .apply(format_rp)
            )

        st.dataframe(
            df_journal_combined
            .reindex(
                columns=[
                    "Tanggal",
                    "Ref",
                    "Akun_Debit",
                    "Debit",
                    "Akun_Kredit",
                    "Kredit",
                    "Jumlah",
                    "Keterangan"
                ]
            )
            .sort_values(
                by="Tanggal",
                ascending=False
            )
            .head(200)
        )

        csv = (
            df_journal_combined
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "Download jurnal.csv",
            data=csv,
            file_name="jurnal_akuntansi.csv",
            mime="text/csv"
        )

    else:

        st.write(
            "Tidak ada jurnal otomatis saat ini."
        )

    # =====================================================
    # ALERTS
    # =====================================================
    if saldo < 0:

        st.error(
            "⚠️ Saldo negatif. "
            "Perlu kontrol pengeluaran "
            "atau percepat penagihan piutang."
        )

    elif piutang_total > total_masuk:

        st.warning(
            "🟡 Piutang lebih besar dari pemasukan. "
            "Cashflow berpotensi ketat."
        )

    elif total_keluar > total_masuk:

        st.warning(
            "📉 Pengeluaran lebih besar "
            "dari pemasukan bulan ini."
        )

    else:

        st.success(
            "🟢 Cashflow sehat. "
            "Arus kas berjalan stabil."
        )

#Footer notes
    st.markdown("---")
    st.markdown("**Catatan:**\n- Pembelian via kartu kredit dicatat sebagai `Hutang Kartu - <Nama>` (liability) dan tidak mengurangi kas sampai pembayaran tagihan tercatat.\n- Pembayaran tagihan kartu dicatat sebagai pengurangan kas dan mengurangi liability.\n- Untuk otomasi pendapatan (cash-basis), sertakan kolom `Paid_Amount` atau catatan `Masuk` pada sheet 'Arus Kas'.")

#======================================================================================================================================
#                                                        LAPORAN KEUANGAN BARU
#======================================================================================================================================

# Pindahkan baris import ini ke bagian paling atas file app.py Anda
import finance_engine
import visualizer
import ai_auditor

# =========================================================================
# ISI KODE DI BAWAH INI UNTUK MENGGANTIKAN ISI EXPANDER LAMA DI app.py ANDA
# =========================================================================

#with st.expander("📘 Laporan Baru - AI Base"):
with st.expander("💸 Laporan Cashflow Realtime (AI Powered)", expanded=False):
    #st.markdown("### Filter Cashflow & Transaksi")
    
    # 📥 AMBIL DATA AMAN: Panggil fungsi load_data() global yang sudah ter-cache
    # Ini 100% hemat kuota API karena mengambil dari memori RAM server, bukan dari Google
    try:
        # Memanggil fungsi load_data yang murni menarik data segar dari Google Sheets
        df_raw = load_data().copy()
    except Exception as e:
        st.error(f"Gagal memuat data segar: {str(e)}")
        df_raw = pd.DataFrame()
    # ----------------------------------------------------------------------

    if not df_raw.empty:
        # Sisa kode Anda ke bawah sudah 100% Sempurna dan Benar
        df_raw["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_raw["Tgl Pemesanan"], dayfirst=True, errors="coerce")
        df_raw = df_raw.dropna(subset=["Tgl Pemesanan_Parsed"])
        
        # ----------------------------------------------------------------------
        # 💡 OPTIMASI DEFAULT FILTER: Setel dari Tanggal 1 Bulan Berjalan s/d Hari Ini
        # ----------------------------------------------------------------------
        hari_ini = date.today()
        awal_bulan_berjalan = hari_ini.replace(day=1)
        
        col_filt1, col_filt2 = st.columns(2)
        
        with col_filt1:
            # Set default start ke tanggal 1 bulan ini agar pembacaan Pandas sangat ringan dan instan!
            tgl_pilihan = st.date_input(
                "Rentang Tanggal", 
                [awal_bulan_berjalan, hari_ini], 
                key="v2_date_filter"
            )
        
        with col_filt2:
            list_admin = ["(Semua)"] + sorted(df_raw["Admin"].dropna().unique().tolist())
            selected_admin = st.selectbox("Saring Berdasarkan Admin", list_admin, key="v2_admin_filter")
        # ----------------------------------------------------------------------
        
        # Eksekusi pemotongan data berdasarkan rentang waktu yang diperketat
        if len(tgl_pilihan) == 2:
            tgl_mulai, tgl_akhir = tgl_pilihan
            
            # Normalisasi jam transaksional demi akurasi 100%
            ts_mulai = pd.Timestamp(tgl_mulai).normalize()
            ts_akhir = pd.Timestamp(tgl_akhir).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            
            df_filtered = df_raw[
                (df_raw["Tgl Pemesanan_Parsed"] >= ts_mulai) &
                (df_raw["Tgl Pemesanan_Parsed"] <= ts_akhir)
            ].copy()
        else:
            # Jika user mengosongkan tanggal, amankan dengan mengunci bulan berjalan saja
            df_filtered = df_raw[df_raw["Tgl Pemesanan_Parsed"].dt.month == hari_ini.month].copy()
            
        if selected_admin != "(Semua)":
            df_filtered = df_filtered[df_filtered["Admin"] == selected_admin]

        st.markdown("---")

        if 'df_cashflow_combined' not in locals() and 'df_cashflow_combined' not in globals():
            df_cashflow_combined = pd.DataFrame(columns=["Invoice_Key", "Jumlah", "Tipe"])
            
        # paksa sistem memanggil fungsi load_data_all_tabs() untuk menyedot data segar dari GSheets
        if 'df_pribadi' in locals() or 'df_pribadi' in globals():
            df_pribadi_current = df_pribadi
        else:
            try:
                # Panggil fungsi penarik multi-tab global milik Anda
                _, df_pribadi_fresh = load_data_all_tabs()
                df_pribadi_current = df_pribadi_fresh
            except:
                # Jika fungsi load gagal/belum terbaca di scope ini, buatkan DataFrame cadangan agar anti-crash
                df_pribadi_current = pd.DataFrame(columns=["Tanggal", "Bank_Sumber", "No_Rekening_AI", "Kategori", "Nominal", "Keterangan"])

        # =========================================================================
        # 🚀 EKSEKUSI ENGINE V5: Panggil dengan 3 Parameter Data yang Sudah Steril
        # =========================================================================
        metrics = finance_engine.hitung_performa_dan_reconciliation_v5(
            df_filtered, 
            df_pribadi_current, 
            df_cashflow_combined
        )

        # 5️⃣ TAMPILKAN INTERFACES TABS (Bersih, Rapi, & Padat di Dalam Expander)
        tab_ringkasan, tab_aging, tab_ai_audit = st.tabs([
            "📊 Ringkasan Keuangan", 
            "⏳ Aging Report Piutang", 
            "🕵️‍♂️ AI Real-time Auditor"
        ])
        
        # --- TAB 1: RINGKASAN DATA ANGKA & GRAFIK INTERAKTIF ---
                # --- TAB 1: RINGKASAN DATA ANGKA & GRAFIK INTERAKTIF ---
    with tab_ringkasan:
        st.subheader("📌 Indikator Utama Kinerja Keuangan")
        
        # 🎨 1. SUNTIKAN CSS UNTUK STYLE KARTU METRIK KUSTOM (EFEK BAYANGAN & SUDUT TUMPUL)
        card_style = """
        <style>
        .fin-card {
            background-color: #ffffff;
            padding: 24px;
            border-radius: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            border: 1px solid #f0f0f0;
            text-align: center;
            margin-bottom: 16px;
        }
        .fin-title {
            font-size: 16px;
            color: #555555;
            font-weight: 500;
            margin-bottom: 12px;
        }
        .fin-value {
            font-size: 26px;
            font-weight: 700;
            color: #111111;
        }
        .fin-delta {
            font-size: 14px;
            color: #2e7d32;
            background-color: #e8f5e9;
            padding: 4px 10px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 8px;
            font-weight: 600;
        }
        </style>
        """
        st.markdown(card_style, unsafe_allow_html=True)

        # 🧮 Ambil dan format angka nominal dari mesin hitung
        txt_pendapatan = f"Rp {int(metrics['pendapatan']):,}".replace(",", ".")
        txt_hpp = f"Rp {int(metrics['hpp']):,}".replace(",", ".")
        txt_laba = f"Rp {int(metrics['laba_bersih']):,}".replace(",", ".")
        txt_margin = f"↑ Margin {metrics['margin_laba_bersih']:.2f}%"

        # 🏗️ 2. RENDER LAYOUT KARTU METRIK KUSTOM HINGGA 2 BARIS (PERSIS SEPERTI GAMBAR)
        # Baris 1: Total Penjualan & Total Pembelian (Berdampingan)
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f"""
            <div class="fin-card">
                <div class="fin-title">💰 Total Penjualan</div>
                <div class="fin-value">{txt_pendapatan}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_m2:
            st.markdown(f"""
            <div class="fin-card">
                <div class="fin-title">💸 Total Pembelian</div>
                <div class="fin-value">{txt_hpp}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Baris 2: Profit Bersih Buku (Ukuran Penuh / Full Width)
        st.markdown(f"""
        <div class="fin-card">
            <div class="fin-title">📈 Profit Bersih Buku</div>
            <div class="fin-value">{txt_laba}</div>
            <div class="fin-delta">{txt_margin}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        
        # 📊 3. BAGIAN GRAFIK INTERAKTIF
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            df_daily_chart = df_filtered.copy()
            def _clean_chart_num(val):
                if pd.isna(val): return 0.0
                try: return float(str(val).replace("Rp", "").replace(".", "").replace(" ", "").replace(",", ""))
                except: return 0.0
            df_daily_chart["Harga Jual (Num)"] = df_daily_chart["Harga Jual"].apply(_clean_chart_num)
            df_daily_grouped = df_daily_chart.groupby("Tgl Pemesanan_Parsed")["Harga Jual (Num)"].sum().reset_index()
            
            # Panggil grafik harian Plotly Express
            visualizer.render_grafik_tren_harian(df_daily_grouped)
            
        with col_g2:
            # Panggil grafik batang murni versi aman tanpa update_layout sensitif
            visualizer.render_grafik_margin_aman(df_filtered)


        # --- TAB 2: AGING REPORT (OTOMATISASI STATUS BELUM LUNAS) ---
        with tab_aging:
            st.subheader("⏳ Daftar Sisa Tagihan Invoice Klien (Hasil Rekonsiliasi)")
            
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.warning(f"🔴 Total Sisa Piutang: Rp {int(metrics['total_piutang']):,}".replace(",", ".") + f" ({metrics['jumlah_invoice_piutang']} Invoice)")
            with col_a2:
                st.error(f"⚠️ Kritis (Overdue > 30 Hari): Rp {int(metrics['overdue_lebih_30_hari']):,}".replace(",", "."))
            st.markdown("---")
            
            df_aging = metrics["df_aging_report"]
            if df_aging.empty:
                st.success("🎉 Luar biasa! Seluruh tagihan invoice berdasarkan transaksi masuk dan keluar sudah Lunas.")
            else:
                # Fungsi inline styling warna merah muda milik Anda
                def style_row_overdue(row):
                    return ["background-color: #FF9999" if row.Overdue else "" for _ in row]
                
                df_display_aging = df_aging.copy()
                
                # Format Tanggal agar rapi tanpa jam jam 00:00:00
                df_display_aging["Tanggal Pemesanan"] = df_display_aging["Tanggal Pemesanan"].dt.strftime('%Y-%m-%d')
                
                # Format nominal sisa piutang ke mata uang rupiah
                df_display_aging["Piutang"] = df_display_aging["Piutang"].apply(lambda x: f"Rp {int(x):,}".replace(",", "."))
                df_display_aging = df_display_aging.rename(columns={"Piutang": "Sisa Tagihan"})
                
                st.dataframe(
                    df_display_aging.style.apply(style_row_overdue, axis=1), 
                    use_container_width=True, 
                    height=400
                )
                st.caption("💡 Info Visual: Baris berwarna merah muda menandakan sisa tagihan telah menunggak parah melebihi 30 hari sejak nota dibuat.")

        # --- TAB 3: AUDIT FORENSIK OTOMATIS GEMINI 3.1 FLASH LITE ---
        with tab_ai_audit:
            st.subheader("🕵️‍♂️ Laporan Hasil Penelaahan Audit Forensik AI")
            st.info("Fitur ini meringkas data indikator keuangan Anda lalu mengirimkannya ke Gemini 3.1 Flash Lite untuk di-audit secara berkala.")
            
            val_total_transaksi = metrics.get('total_transaksi', len(df_filtered))
            val_pendapatan = metrics.get('pendapatan', 0.0)
            val_hpp = metrics.get('hpp', 0.0)
            val_laba_bersih = metrics.get('laba_bersih', 0.0)
            val_margin = metrics.get('margin_laba_bersih', 0.0)
            val_top_admin = metrics.get('top_admin', 'N/A')
            val_text_segmentasi = metrics.get('text_segmentasi', '- Data distribusi belum siap\n')
            val_total_piutang = metrics.get('total_piutang', 0.0)
            val_jumlah_invoice = metrics.get('jumlah_invoice_piutang', 0)
            val_overdue_30 = metrics.get('overdue_lebih_30_hari', 0.0)
            val_jumlah_boncos = metrics.get('jumlah_transaksi_rugi', 0)
            val_total_kerugian = metrics.get('total_kerugian', 0.0)
            val_text_debitur = metrics.get('text_top_debitur', '- Belum ada data debitur\n')

            # 🧮 KALKULASI ARSENAL RASIO DARURAT (Mencegah KeyError di app.py)
            val_roi = metrics.get('roi', (val_laba_bersih / val_hpp * 100) if val_hpp > 0 else 0.0)
            val_kas_riil = metrics.get('kas_riil', (val_pendapatan - val_total_piutang) - val_hpp)
            val_keterikatan_modal = metrics.get('rasio_keterikatan_modal', (val_total_piutang / val_pendapatan * 100) if val_pendapatan > 0 else 0.0)
            val_kerentanan_laba = metrics.get('rasio_kerentanan_laba', (val_total_piutang / val_laba_bersih * 100) if val_laba_bersih > 0 else 0.0)
            # ----------------------------------------------------------------------

            # Merakit Paket Payload Senjata Lengkap ke Gemini (100% Bebas Crash KeyError!)
            text_payload_ai = f"""
            INDIKATOR UTAMA AKUNTANSI:
            - Total Baris Transaksi Terproses: {val_total_transaksi} baris
            - Omzet Penjualan Kotor: Rp {int(val_pendapatan):,}
            - Total Pengeluaran Modal (HPP): Rp {int(val_hpp):,}
            - Laba Bersih Buku (Paper Profit): Rp {int(val_laba_bersih):,}
            
            ARSENAL RASIO FINANSIAL (REALISASI AKTUAL):
            - Realisasi Net Profit Margin (NPM): {val_margin:.2f}%
            - Realisasi Return on Investment (ROI): {val_roi:.2f}%
            - Estimasi Sisa Kas Riil Lapangan: Rp {int(val_kas_riil):,}
            - Rasio Keterikatan Modal dalam Piutang: {val_keterikatan_modal:.2f}%
            - Rasio Kerentanan Laba terhadap Piutang: {val_kerentanan_laba:.2f}%
            - Admin dengan Penjualan Tertinggi: Admin [{val_top_admin}]
            
            DISTRIBUSI KINERJA SEGMEN PRODUK:
            {val_text_segmentasi}
            
            🚨 LAPORAN FORENSIK PIUTANG MACET & KEBOCORAN DANA:
            - Total Nilai Piutang Klien Keseluruhan: Rp {int(val_total_piutang):,}
            - Jumlah Invoice Menggantung: {val_jumlah_invoice} nota belum lunas
            - Dana Piutang Macet Kritis Jangka Panjang (>30 Hari): Rp {int(val_overdue_30):,}
            - Kebocoran Harga (Transaksi Rugi/Minus): {val_jumlah_boncos} kali transaksi, total kerugian riil Rp {int(val_total_kerugian):,}
            
            DAFTAR NAMA PENGUTANG (TOP DEBITUR TERBESAR):
            {val_text_debitur}
            """
                
            if "response_audit_ai" not in st.session_state:
                st.session_state.response_audit_ai = None
                
            if st.button("🔍 Mulai Jalankan Audit Finansial Sekarang", type="primary", key="btn_audit_keuangan_v2"):
                with st.spinner("Gemini AI sedang meneliti struktur pembukuan dan mengalkulasi risiko keuangan Anda..."):
                    hasil_lhpa = ai_auditor.audit_forensik_dashboard(text_payload_ai)
                    st.session_state.response_audit_ai = hasil_lhpa
                    
            if st.session_state.response_audit_ai:
                st.markdown("---")
                st.markdown(st.session_state.response_audit_ai)

                import re
            
                # 🛠️ Mesin Mini Pengubah Otomatis: Mengubah Tabel Markdown Gemini Menjadi Tabel HTML Word Resmi
                def markdown_to_html_word(md_text):
                    lines = md_text.strip().split("\n")
                    html_output = []
                    in_table = False
                    
                    for line in lines:
                        # Deteksi baris tabel markdown
                        if line.strip().startswith("|"):
                            if not in_table:
                                html_output.append('<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse; font-family:Arial; font-size:11pt; width:100%; margin-bottom:14px;">')
                                in_table = True
                            
                            # Abaikan baris pembatas tabel | :--- | :--- |
                            if "---" in line:
                                continue
                                
                            cells = [c.strip() for c in line.split("|")[1:-1]]
                            tag = "th" if html_output[-1].endswith("</table>") or html_output[-1].strip() == '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse; font-family:Arial; font-size:11pt; width:100%; margin-bottom:14px;">' else "td"
                            
                            # Deteksi apakah ini baris header pertama
                            if html_output[-1].strip().startswith('<table'):
                                tag = "th"
                                bg_style = ' style="background-color:#f2f2f2; font-weight:bold; text-align:left;"'
                            else:
                                tag = "td"
                                bg_style = ''
                                
                            row_html = "  <tr>"
                            for cell in cells:
                                # Jika sel bertuliskan tebal **teks**, bersihkan tanda bintangnya
                                cell_clean = cell.replace("**", "")
                                row_html += f'<{tag}{bg_style}>{cell_clean}</{tag}>'
                            row_html += "</tr>"
                            html_output.append(row_html)
                        else:
                            if in_table:
                                html_output.append("</table>")
                                in_table = False
                            
                            # Konversi format penulisan judul standar markdown ke HTML
                            if line.strip().startswith("###"):
                                html_output.append(f'<h3 style="font-family:Arial; color:#1b5e20; margin-top:18px;">{line.replace("###", "").strip()}</h3>')
                            elif line.strip().startswith("##"):
                                html_output.append(f'<h2 style="font-family:Arial; color:#2e7d32; margin-top:22px;">{line.replace("##", "").strip()}</h2>')
                            elif line.strip().startswith("#"):
                                html_output.append(f'<h1 style="font-family:Arial; color:#111111; text-align:center;">{line.replace("#", "").strip()}</h1>')
                            elif line.strip().startswith("-") or line.strip().startswith("*"):
                                # Bersihkan tanda bintang tebal di list poin
                                bullet_text = line.strip()[1:].strip().replace("**", "")
                                html_output.append(f'<li style="font-family:Arial; font-size:11pt; margin-left:20px; margin-bottom:6px;">{bullet_text}</li>')
                            else:
                                # Bersihkan teks paragraf biasa dari bintang-bintang tebal markdown
                                clean_line = line.replace("**", "")
                                html_output.append(f'<p style="font-family:Arial; font-size:11pt; line-height:1.5;">{clean_line}</p>')
                                
                    if in_table:
                        html_output.append("</table>")
                        
                    return "\n".join(html_output)

                # Jalankan mesin konversi terhadap teks Gemini
                html_body_content = markdown_to_html_word(st.session_state.response_audit_ai)
                
                # Bungkus ke dalam template dokumen resmi Microsoft Word (MIME type HTML)
                word_html_template = f"""
                <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://w3.org'>
                <head>
                    <title>Laporan Audit Finansial Kayyisa Travel</title>
                    <!--[if gte mso 9]>
                    <xml>
                        <w:WordDocument>
                            <w:View>Print</w:View>
                            <w:Zoom>100</w:Zoom>
                        </w:WordDocument>
                    </xml>
                    <![endif]-->
                </head>
                <body style="font-family:Arial; padding:40px;">
                    <div style="text-align:center; margin-bottom:30px;">
                        <h1 style="font-family:Arial; margin-bottom:4px; color:#111111;">🏛️ REKOMENDASI CFO & LAPORAN AUDIT STRATEGIS</h1>
                        <p style="font-family:Arial; font-size:10pt; color:#666666; margin-top:0px;">
                            <b>Kayyisa Tour & Travel — Business Management System</b><br>
                            Tanggal Cetak Dokumen: {date.today().strftime('%d %B %Y')}
                        </p>
                    </div>
                    <hr style="border:1px solid #cccccc; margin-bottom:24px;">
                    {html_body_content}
                </body>
                </html>
                """
                
                # Sediakan tombol unduh Word pintar yang dijamin rapi kotak-kotaknya
                st.download_button(
                    label="📝 Unduh Dokumen Laporan Word Resmi (.doc)",
                    data=word_html_template,
                    file_name=f"Laporan_Audit_Kayyisa_Travel_{date.today().strftime('%Y%m%d')}.doc",
                    mime="application/msword",
                    type="primary",
                    key="btn_download_word_html_v3"
                )

# ---------------------------
# Streamlit UI
# ---------------------------
#st.set_page_config(page_title="Cashflow & Liabilities - UMKM", layout="wide")
#st.title("Cashflow & Liability Tracker (Refactor)")

# Manual input expander
with st.expander("✏️ Input Data Cashflow Manual"):
    try:
        ws_cashflow = connect_to_gsheet(SHEET_ID, "Arus Kas")
    except Exception:
        ws_cashflow = None
        st.warning("GSheets not connected (check secrets). Manual entry will still work locally in session_state.")

    tanggal = st.date_input("Tanggal", value=date.today(), key="tgl_input")
    tipe = st.selectbox("Tipe", ["Masuk", "Keluar"], key="tipe_input")

    kategori_masuk = ["Komisi & Fee dari Pihak Ketiga", "Service Fee (proses Refund/Reschedule)", "Fee dari Add-on/Produk Tambahan", 
        "Jasa Pengurusan Dokumen", "Paket Wisata / Tour", "Lain-lain"
    ]
    kategori_keluar = [
        "Gaji Karyawan", "Operasional Kantor", "Pembayaran Pinjaman (Hutang/Credit Card)", "Marketing & Promosi", "Pajak dan Biaya Lainnya",
        "Kerugian Salah Order", "Kerugian Pembatalan", "Kerugian Kerusakan / Rusak",
        "Kerugian Lainnya", "HPP", "Lain-lain"
    ]
    kategori_opsi = kategori_masuk if tipe == "Masuk" else kategori_keluar
    kategori = st.selectbox("Kategori", kategori_opsi, key="kategori_input")
    if kategori == "Lain-lain":
        kategori = st.text_input("Jelaskan kategori lainnya", key="kategori_lain_input")

    no_invoice = st.text_input("No Invoice (opsional)", key="no_invoice_input")
    keterangan = st.text_input("Keterangan", key="keterangan_input")
    jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1, format="%d", key="jumlah_input")
    status_manual = st.selectbox("Status", ["Lunas", "Belum Lunas"], key="status_input")

    # jika pembayaran CC, pilih akun kartu
    card_account = ""
    if tipe == "Keluar" and kategori == "Pembayaran Pinjaman (Hutang/Credit Card)":
        card_account = st.text_input("Bayar ke Akun Kartu (contoh: Hutang Kartu - BCA Visa)", key="card_account_input")

    if st.button("Simpan Data Manual", key="btn_simpan_manual"):
        if jumlah <= 0:
            st.error("Jumlah harus lebih dari 0")
        else:
            new_row = {
                "Tanggal": pd.to_datetime(tanggal),
                "Tipe": tipe,
                "Kategori": kategori,
                "No Invoice": str(no_invoice) if no_invoice else "",
                "Keterangan": keterangan,
                "Jumlah": jumlah,
                "Status": status_manual,
                "Sumber": "Manual Input",
                "Is_Invoice": False,
                "Nama Pemesan": keterangan,
                "Invoice_Key": f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "Card_Account": card_account
            }

            if "cashflow_manual" not in st.session_state:
                st.session_state.cashflow_manual = []
            st.session_state.cashflow_manual.append(new_row)

            # Jika ini pembayaran CC, juga catat entry liability pengurang hutang
            if kategori == "Pembayaran Pinjaman (Hutang/Credit Card)":
                liability_entry = {
                    "Tanggal": pd.to_datetime(tanggal),
                    "Invoice_Key": new_row["Invoice_Key"],
                    "Akun": card_account if card_account else "Hutang Kartu - Unknown",
                    "Jumlah": -jumlah,  # negatif untuk mengurangi hutang
                    "Keterangan": f"Pembayaran tagihan kartu {card_account}",
                    "Jenis": "KurangiHutang"
                }
                if "liabilities_manual" not in st.session_state:
                    st.session_state.liabilities_manual = []
                st.session_state.liabilities_manual.append(liability_entry)

            st.success("✅ Data berhasil disimpan sementara (belum dikirim ke GSheets)")

    if st.button("Kirim Manual ke GSheets"):
        if "cashflow_manual" in st.session_state and st.session_state.cashflow_manual:
            df_manual = pd.DataFrame(st.session_state.cashflow_manual)
            columns_gsheet = ["Tanggal","Tipe","Kategori","No Invoice","Keterangan","Jumlah","Status","Sumber","Card_Account"]
            df_manual_gsheet = df_manual.reindex(columns=columns_gsheet).copy()
            df_manual_gsheet["Tanggal"] = df_manual_gsheet["Tanggal"].dt.strftime("%Y-%m-%d")

            if ws_cashflow:
                ws_cashflow.append_rows(df_manual_gsheet.fillna("").values.tolist(), value_input_option='USER_ENTERED')
                st.success("✅ Data manual berhasil dikirim ke GSheets")
                st.session_state.cashflow_manual = []
            else:
                st.warning("GSheets tidak tersedia - data tetap disimpan di session_state")
        else:
            st.warning("Tidak ada data manual untuk dikirim")

# ---------------------------
# Laporan Cashflow Realtime
# ---------------------------
# with st.expander("📘 Jurnal Akuntansi"):

#     # --- Ambil data dari GSheet (Data & Arus Kas) dengan fallback ---
#     df_data = load_sheet(SHEET_ID, "Data")
#     df_cashflow_existing = load_sheet(SHEET_ID, "Arus Kas")


#     # --- Normalisasi df_data ---
#     if not df_data.empty:
#         # Numeric columns
#         for col in ["Harga Beli","Harga Jual"]:
#             df_data[col] = clean_price_column(df_data[col]) if col in df_data.columns else 0.0

#         # Pastikan kolom wajib ada
#         for col in ["Keterangan","No Invoice","Nama Pemesan","Sumber Dana","Detail Dana","Platform","Card_Account","Paid_Amount"]:
#             if col not in df_data.columns:
#                 df_data[col] = ""

#         # Tanggal
#         df_data["Tgl Pemesanan"] = pd.to_datetime(df_data.get("Tgl Pemesanan", pd.NaT), dayfirst=True, errors="coerce")

#         # Invoice_Key
#         df_data["No Invoice"] = df_data["No Invoice"].fillna("").astype(str)
#         df_data["Nama Pemesan"] = df_data["Nama Pemesan"].fillna("").astype(str)
#         df_data["Invoice_Key"] = df_data.apply(
#             lambda x: f"{x['Nama Pemesan']}_MANUAL_{x.name}" if x["No Invoice"]=="" else f"{x['Nama Pemesan']}_{x['No Invoice']}",
#             axis=1
#         )
#     else:
#         df_data = pd.DataFrame(columns=[
#             "Tgl Pemesanan","Harga Beli","Harga Jual","Keterangan","No Invoice",
#             "Nama Pemesan","Sumber Dana","Detail Dana","Platform","Invoice_Key"
#         ])

#     # --- Parse otomatis ---
#     df_cf_auto, df_piutang_auto, df_hutang_cc_auto, df_journal_auto = parse_financial_data(
#         df_data, df_cashflow_existing
#     )

#     # --- Gabungkan cashflow existing + auto + manual session ---
#     df_cashflow_combined = pd.concat([
#         df_cashflow_existing if not df_cashflow_existing.empty else pd.DataFrame(),
#         df_cf_auto if not df_cf_auto.empty else pd.DataFrame(),
#         pd.DataFrame(st.session_state.get("cashflow_manual", []))
#     ], ignore_index=True)

#     # Ensure common columns & numeric conversion
#     required_cf_cols = ["Tanggal","Tipe","Kategori","No Invoice","Keterangan","Jumlah",
#                         "Status","Sumber","Nama Pemesan","Invoice_Key","Sumber Dana","Detail Dana","Platform","Akun"]
#     for c in required_cf_cols:
#         if c not in df_cashflow_combined.columns:
#             df_cashflow_combined[c] = None

#     df_cashflow_combined["Jumlah"] = pd.to_numeric(df_cashflow_combined["Jumlah"], errors="coerce").fillna(0.0)
#     df_cashflow_combined["Tanggal"] = pd.to_datetime(df_cashflow_combined["Tanggal"], errors="coerce")

#     # Drop duplicates di semua kolom untuk menghindari double-count
#     df_cashflow_combined = df_cashflow_combined.drop_duplicates()

#     # --- Filter cash-only flows (exclude CC/Kartu keluar) ---
#     df_cashflow_combined["Sumber Dana"] = df_cashflow_combined["Sumber Dana"].fillna("").astype(str)
#     credit_mask = df_cashflow_combined["Sumber Dana"].str.lower().str.contains("credit|cc|kartu|card|kart", na=False)
#     df_cash_only = df_cashflow_combined[~((df_cashflow_combined["Tipe"]=="Keluar") & credit_mask)].copy()

#     df_cash_only = df_cash_only.dropna(subset=["Tanggal"])

#     # --- Totals ---
#     total_masuk = df_cash_only.query("Tipe=='Masuk'")["Jumlah"].sum() if not df_cash_only.empty else 0.0
#     total_keluar = df_cash_only.query("Tipe=='Keluar'")["Jumlah"].sum() if not df_cash_only.empty else 0.0
#     saldo = total_masuk - total_keluar

#     # --- Piutang: aggregate per Invoice_Key untuk mencegah overcount ---
#     list_piutang = []
#     piutang_total = 0.0
#     if not df_data.empty:
#         for inv_key, group in df_data.groupby("Invoice_Key"):
#             total_harga_jual = group["Harga Jual"].sum()
#             total_sudah_diterima = df_cash_only[(df_cash_only["Invoice_Key"]==inv_key) & (df_cash_only["Tipe"]=="Masuk")]["Jumlah"].sum() if not df_cash_only.empty else 0.0
#             sisa_piutang = max(0.0, total_harga_jual - total_sudah_diterima)
#             if sisa_piutang > 0:
#                 piutang_total += sisa_piutang
#                 inv_no = group["No Invoice"].iloc[0] if group["No Invoice"].iloc[0] else f"MANUAL_{group.index[0]}"
#                 list_piutang.append([inv_no, total_harga_jual, total_sudah_diterima, sisa_piutang])

#     df_piutang = pd.DataFrame(list_piutang, columns=["Invoice","Total","Terbayar","Sisa"]) if list_piutang else pd.DataFrame(columns=["Invoice","Total","Terbayar","Sisa"])

#     # --- Hutang CC ---
#     df_hutang_cc_combined = df_hutang_cc_auto.copy() if not df_hutang_cc_auto.empty else pd.DataFrame()
#     if not df_hutang_cc_combined.empty:
#         df_hutang_cc_combined["Jumlah"] = pd.to_numeric(df_hutang_cc_combined["Jumlah"], errors="coerce").fillna(0.0)
#         summary_hutang = df_hutang_cc_combined.groupby("Bank", as_index=False).agg({"Jumlah":"sum"}).query("Jumlah != 0")
#     else:
#         summary_hutang = pd.DataFrame(columns=["Bank","Jumlah"])

#     # --- Jurnal: gabungkan auto + manual, pastikan kolom lengkap, drop duplicates, filter NaT ---
#     df_journal_combined = pd.concat([
#         pd.DataFrame(st.session_state.get("journal_manual", [])),
#         df_journal_auto if not df_journal_auto.empty else pd.DataFrame()
#     ], ignore_index=True)

#     journal_cols = ["Tanggal","Ref","Akun_Debit","Debit","Akun_Kredit","Kredit","Keterangan"]
#     for c in journal_cols:
#         if c not in df_journal_combined.columns:
#             df_journal_combined[c] = None
#     df_journal_combined["Tanggal"] = pd.to_datetime(df_journal_combined["Tanggal"], errors="coerce")
#     df_journal_combined = df_journal_combined.dropna(subset=["Tanggal"]).drop_duplicates(subset=journal_cols, keep="last")

    
#     if summary_hutang.empty:
#         st.markdown(
#                 f"""
#                 <div style="
#                     background-color:#d9edf7;
#                     padding: 15px;
#                     border-radius: 5px;
#                     border-left: 5px solid #31708f;
#                     border-right: 5px solid #31708f;
#                     text-align: center;
#                     font-weight: bold;
#                     color: #31708f;
#                     font-size: 24px;
#                 ">
#                     💳 Belum ada hutang kartu tercatat.
#                 </div>
#                 """,
#                 unsafe_allow_html=True
#         )

#     else:
#         for _, r in summary_hutang.iterrows():
#             st.markdown(
#                 f"""
#                 <div style="
#                     background-color:#d9edf7;
#                     padding: 15px;
#                     border-radius: 5px;
#                     border-left: 5px solid #31708f;
#                     border-right: 5px solid #31708f;
#                     text-align: center;
#                     font-weight: bold;
#                     color: #31708f;
#                     font-size: 24px;
#                 ">
#                     💳 Sisa Hutang Kartu Kredit ({r['Bank']}): {format_rp(r['Jumlah'])}
#                 </div>
#                 """,
#                 unsafe_allow_html=True
#             )
#     # ROW 1
#     col1, col2 = st.columns(2)
#     with col1:
#         metric_card("💰 Total Pemasukan", format_rp(total_masuk))
#     with col2:
#         metric_card("📤 Total Pengeluaran (non Credit Card)", format_rp(total_keluar))
    
#     # ROW 2
#     col3, col4 = st.columns(2)
#     with col3:
#         metric_card("🏦 Saldo Akhir", format_rp(saldo))
#     with col4:
#         metric_card("🧾 Piutang Belum Lunas", format_rp(piutang_total))

#     st.subheader("📘 Jurnal Akuntansi (Auto Generated)")
#     if not df_journal_combined.empty:
#         df_journal_combined["Jumlah"] = df_journal_combined["Jumlah"].apply(format_rp)
#         st.dataframe(
#             df_journal_combined.reindex(
#                 columns=["Tanggal","Ref","Akun_Debit","Debit","Akun_Kredit","Kredit", "Jumlah", "Keterangan"]
#             ).sort_values(by="Tanggal", ascending=False).head(200)
#         )
#         csv = df_journal_combined.to_csv(index=False).encode("utf-8")
#         st.download_button("Download jurnal.csv", data=csv, file_name="jurnal_akuntansi.csv", mime="text/csv")
#     else:
#         st.write("Tidak ada jurnal otomatis saat ini.")

#     # --- Alerts ---
#     if saldo < 0:
#         st.error("⚠️ Saldo negatif. Perlu kontrol pengeluaran atau percepat penagihan piutang.")
#     elif piutang_total > total_masuk:
#         st.warning("🟡 Piutang lebih besar dari pemasukan. Cashflow berpotensi ketat.")
#     elif total_keluar > total_masuk:
#         st.warning("📉 Pengeluaran lebih besar dari pemasukan bulan ini.")
#     else:
#         st.success("🟢 Cashflow sehat. Arus kas berjalan stabil.")
# =========================================================
# CACHE HELPERS
# =========================================================
@st.cache_resource
def get_ws(sheet_id, worksheet_name):
    """
    Cache worksheet connection agar tidak reconnect terus ke GSheet
    """
    return connect_to_gsheet(sheet_id, worksheet_name)


@st.cache_data(ttl=300)
def load_sheet_cached(sheet_id, worksheet_name):
    """
    Cache dataframe selama 5 menit
    """
    ws = get_ws(sheet_id, worksheet_name)
    return pd.DataFrame(ws.get_all_records())


def refresh_cached_data():
    """
    Refresh cache manual setelah save/update data
    """
    st.cache_data.clear()

    st.session_state.df_data = load_sheet_cached(SHEET_ID, "Data")
    st.session_state.df_cashflow_existing = load_sheet_cached(SHEET_ID, "Arus Kas")


#Footer notes
    st.markdown("---")
    st.markdown("**Catatan:**\n- Pembelian via kartu kredit dicatat sebagai `Hutang Kartu - <Nama>` (liability) dan tidak mengurangi kas sampai pembayaran tagihan tercatat.\n- Pembayaran tagihan kartu dicatat sebagai pengurangan kas dan mengurangi liability.\n- Untuk otomasi pendapatan (cash-basis), sertakan kolom `Paid_Amount` atau catatan `Masuk` pada sheet 'Arus Kas'.")
with st.expander("📘 Laporan - laporan"):
    with st.expander("💸 Laporan Cashflow Realtime"): 
        st.markdown("### 🔧 Filter Cashflow")
        
        # Pastikan kolom Bulan/Tahun tersedia
        df_cashflow_combined["Tanggal"] = pd.to_datetime(df_cashflow_combined["Tanggal"], errors='coerce')
        df_cashflow_combined["Bulan"] = df_cashflow_combined["Tanggal"].dt.month
        df_cashflow_combined["Tahun"] = df_cashflow_combined["Tanggal"].dt.year
        df_cashflow = df_cashflow_combined
        
        # -----------------------------
        # 1️⃣ Pilih Jenis Filter Waktu
        # -----------------------------
        filter_mode = st.radio(
            "Pilih Jenis Filter Waktu",
            ["📆 Rentang Tanggal", "🗓️ Bulanan", "📅 Tahunan"],
            horizontal=True,
            key="filter_mode_radio_v2"
        )
        
        
        # -----------------------------
        # 2️⃣ Filter Waktu Dinamis
        # -----------------------------
        if filter_mode == "📆 Rentang Tanggal":
            cold1, cold2 = st.columns(2)
            tanggal_mulai = cold1.date_input("Dari tanggal", df_cashflow["Tanggal"].min())
            tanggal_akhir = cold2.date_input("Sampai tanggal", df_cashflow["Tanggal"].max())
            df_filtered = df_cashflow[
                (df_cashflow["Tanggal"] >= pd.to_datetime(tanggal_mulai)) &
                (df_cashflow["Tanggal"] <= pd.to_datetime(tanggal_akhir))
            ]
        
        elif filter_mode == "🗓️ Bulanan":
            tahun_filter = st.selectbox("Tahun", sorted(df_cashflow["Tahun"].unique()))
            bulan_map = {
                "Januari":1,"Februari":2,"Maret":3,"April":4,"Mei":5,"Juni":6,
                "Juli":7,"Agustus":8,"September":9,"Oktober":10,"November":11,"Desember":12
            }
            bulan_filter = st.selectbox("Bulan", list(bulan_map.keys()))
            df_filtered = df_cashflow[
                (df_cashflow["Tahun"] == tahun_filter) &
                (df_cashflow["Bulan"] == bulan_map[bulan_filter])
            ]
        
        elif filter_mode == "📅 Tahunan":
            tahun_filter = st.selectbox("Tahun", sorted(df_cashflow["Tahun"].unique()))
            df_filtered = df_cashflow[df_cashflow["Tahun"] == tahun_filter]
        
        # -----------------------------
        # 3️⃣ Filter Tipe Transaksi & Kategori
        # -----------------------------
        colf1, colf2 = st.columns(2)
        
        # Tipe transaksi
        tipe_filter = colf1.selectbox(
            "Jenis Transaksi",
            ["Semua", "Masuk", "Keluar"]
        )
        
        # Kategori (otomatis menyesuaikan tipe)
        if tipe_filter == "Masuk":
            kategori_list = df_cashflow[df_cashflow["Tipe"]=="Masuk"]["Kategori"].unique()
        elif tipe_filter == "Keluar":
            kategori_list = df_cashflow[df_cashflow["Tipe"]=="Keluar"]["Kategori"].unique()
        else:
            kategori_list = df_cashflow["Kategori"].unique()
        
        kategori_filter = colf2.selectbox("Kategori", ["Semua"] + list(kategori_list))
        
        if tipe_filter != "Semua":
            df_filtered = df_filtered[df_filtered["Tipe"] == tipe_filter]
        if kategori_filter != "Semua":
            df_filtered = df_filtered[df_filtered["Kategori"] == kategori_filter]
        
        # -----------------------------
        # 4️⃣ Filter Nama Pemesan (otomatis deteksi kolom)
        # -----------------------------
        possible_name_cols = ["Pemesan", "Nama Pemesan", "Nama", "Customer", "Pemesanan", "Atas Nama"]
        col_pemesan = next((c for c in possible_name_cols if c in df_cashflow.columns), None)
        
        if col_pemesan:
            pemesan_list = df_cashflow[col_pemesan].dropna().unique()
            pemesan_filter = st.selectbox("Nama Pemesan", ["Semua"] + list(pemesan_list))
            if pemesan_filter != "Semua":
                df_filtered = df_filtered[df_filtered[col_pemesan] == pemesan_filter]
        
        # -----------------------------
        # 5️⃣ Total Masuk & Keluar hasil filter
        # -----------------------------
        col_total1, col_total2 = st.columns(2)
        total_masuk_filtered = df_filtered[df_filtered["Tipe"]=="Masuk"]["Jumlah"].sum()
        total_keluar_filtered = df_filtered[df_filtered["Tipe"]=="Keluar"]["Jumlah"].sum()
        
        with col_total1:
            metric_card("💰 Total Masuk (Filtered)", format_rp(total_masuk_filtered))
        
        with col_total2:
            metric_card("📤 Total Keluar (Filtered)", format_rp(total_keluar_filtered))
        
        
        # -----------------------------
        # 6️⃣ Tabel Detail Transaksi
        # -----------------------------
        st.markdown("## 📋 Detail Transaksi Cashflow (Sudah Difilter)")
        
        df_show = df_filtered.copy()
        df_show["Jumlah"] = df_show["Jumlah"].apply(format_rp)
        
        st.dataframe(
            df_show.sort_values("Tanggal", ascending=False),
            use_container_width=True,
            height=500
        )
        # =====================================================
        # 📘 LAPORAN LABA RUGI (INCOME STATEMENT)
        # =====================================================
    with st.expander("📘 Laporan Laba/Rugi - Neraca - Aging Report"):    
    
        # ===========================
        # 1️⃣ Laporan Laba/Rugi
        # ===========================
        required_cols = ["Tipe", "Jumlah", "Kategori"]
        df_ok = ('df_filtered' in locals() or 'df_filtered' in globals()) and all(col in df_filtered.columns for col in required_cols)
    
        if df_ok:
            st.markdown("## 📘 Laporan Laba Rugi")
    
            # Pendapatan (Masuk)
            pendapatan_filtered = df_filtered[df_filtered["Tipe"]=="Masuk"]["Jumlah"].sum()
    
            # HPP / Modal
            hpp_filtered = df_filtered[df_filtered["Kategori"].str.contains("Penjualan", na=False)]["Jumlah"].sum()
    
            # Beban Operasional
            operasional_filtered = df_filtered[
                (df_filtered["Tipe"]=="Keluar") & (~df_filtered["Kategori"].str.contains("Penjualan", na=False))
            ]["Jumlah"].sum()
    
            laba_kotor = pendapatan_filtered - hpp_filtered
            laba_bersih = laba_kotor - operasional_filtered
    
            # Tampilkan metric
            col_laba1, col_laba2 = st.columns(2)
            with col_laba1: metric_card("📈 Pendapatan", format_rp(pendapatan_filtered))
            with col_laba2: metric_card("📉 HPP / Modal", format_rp(hpp_filtered))
            col_laba3, col_laba4 = st.columns(2)
            with col_laba3: metric_card("💼 Beban Operasional", format_rp(operasional_filtered))
            with col_laba4: metric_card("💰 Laba Bersih", format_rp(laba_bersih))
        else:
            st.warning("Laporan Laba Rugi tidak dapat ditampilkan — data belum lengkap.")
            laba_bersih = 0
    
        # Interpretasi otomatis Laba/Rugi
        total_piutang = piutang_total if 'piutang_total' in locals() else 0.0
        if laba_bersih > 0:
            st.success(f"Bisnis **untung**, karena laba bersih = {format_rp(laba_bersih)}.")
        elif laba_bersih == 0:
            st.info("Bisnis berada di titik impas (break even). Tidak untung, tidak rugi.")
        elif laba_bersih < 0 and total_piutang > abs(laba_bersih):
            st.info(
                f"Laba bersih periode ini negatif karena sebagian pendapatan masih dalam piutang "
                f"sebesar {format_rp(total_piutang)}. Setelah dibayar, laba bisa positif."
            )
        else:
            st.error(f"Bisnis **rugi**, karena laba bersih = {format_rp(laba_bersih)}.")
    
        # Markdown penjelasan
        st.markdown("""
        **Laporan Laba Rugi** menunjukkan apakah bisnis *untung atau rugi* dalam periode tertentu.
    
        **🔹 Pendapatan** — semua uang masuk dari pelanggan  
        **🔹 HPP / Modal** — biaya pembelian barang/jasa yang dijual  
        **🔹 Beban Operasional** — biaya operasional seperti gaji, marketing, pajak, kerugian order  
        **🔹 Laba Bersih = Pendapatan – HPP – Operasional**
        """)
    
        # ===========================
        # 2️⃣ Neraca Sederhana
        # ===========================
        st.markdown("## 📗 Neraca Sederhana")
    
        aset_kas = saldo if 'saldo' in locals() else 0.0
        aset_piutang = piutang_total if 'piutang_total' in locals() else 0.0
        aset_total = aset_kas + aset_piutang
    
        # Hutang
        if 'df_cashflow' in locals() and not df_cashflow.empty:
            hutang_kategori = ["Pembayaran Pinjaman (Hutang/Credit Card)", "Penjualan (Credit Card)"]
            hutang_total = df_cashflow[df_cashflow["Kategori"].isin(hutang_kategori)]["Jumlah"].sum()
        else:
            hutang_total = 0.0
    
        modal = aset_total - hutang_total
    
        # Styling
        balance_style = """
        <style>
        .bs-card { background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 15px; border:1px solid #e6e6e6; }
        .bs-title { font-size:20px; font-weight:700; margin-bottom:12px; color:#333; }
        .bs-item { font-size:16px; margin:6px 0; color:#444; }
        .bs-total { margin-top:12px; font-size:18px; font-weight:700; color:#111; }
        </style>
        """
        st.markdown(balance_style, unsafe_allow_html=True)
    
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            st.markdown(
                f"<div class='bs-card'><div class='bs-title'>📦 Aset</div>"
                f"<div class='bs-item'>Kas: {format_rp(aset_kas)}</div>"
                f"<div class='bs-item'>Piutang: {format_rp(aset_piutang)}</div>"
                f"<div class='bs-total'>Total Aset: {format_rp(aset_total)}</div></div>",
                unsafe_allow_html=True
            )
        with col_n2:
            st.markdown(
                f"<div class='bs-card'><div class='bs-title'>🏛️ Kewajiban & Modal</div>"
                f"<div class='bs-item'>Total Hutang: {format_rp(hutang_total)}</div>"
                f"<div class='bs-item'>Modal: {format_rp(modal)}</div>"
                f"<div class='bs-total'>Total Pasiva: {format_rp(hutang_total + modal)}</div></div>",
                unsafe_allow_html=True
            )
    
        # Interpretasi Neraca
        if hutang_total > aset_kas:
            if total_piutang > (hutang_total - aset_kas):
                st.info(f"Kas kurang dari hutang, tapi piutang {format_rp(total_piutang)} akan menutupi.")
            else:
                st.error("Kas < hutang & piutang tidak cukup. Hati-hati dalam manajemen kas.")
        else:
            st.success("Kas cukup untuk menutup hutang jangka pendek.")
    
        # ===========================
        # 3️⃣ Cashflow Statement
        # ===========================
        st.markdown("## 📙 Cashflow Statement")
    
        # Kategori
        operasional_kat = ["Pembayaran Customer","Penjualan (Cash/Tunai)","Penjualan (Credit Card)",
                           "Penjualan (Redeem Points)","Gaji Karyawan","Operasional Kantor",
                           "Marketing & Promosi","Pajak dan Biaya Lainnya","Kerugian Salah Order",
                           "Kerugian Pembatalan","Kerugian Kerusakan / Rusak","Kerugian Lainnya"]
        investasi_kat = ["Pembelian Aset","Peralatan","Inventaris"]
        pendanaan_kat = ["Pembayaran Pinjaman (Hutang/Credit Card)","Penambahan Modal","Pinjaman Masuk"]
    
        def cf_sum(df, tipe, categories):
            if 'df_filtered' not in locals() or df_filtered.empty: return 0
            return df_filtered[(df_filtered["Kategori"].isin(categories)) & (df_filtered["Tipe"] == tipe)]["Jumlah"].sum()
    
        cf_operasional = cf_sum(df_filtered, "Masuk", operasional_kat) - cf_sum(df_filtered, "Keluar", operasional_kat)
        cf_investasi = cf_sum(df_filtered, "Masuk", investasi_kat) - cf_sum(df_filtered, "Keluar", investasi_kat)
        cf_pendanaan = cf_sum(df_filtered, "Masuk", pendanaan_kat) - cf_sum(df_filtered, "Keluar", pendanaan_kat)
        cf_total = cf_operasional + cf_investasi + cf_pendanaan
    
        col_cf1, col_cf2 = st.columns(2)
        with col_cf1: metric_card("💼 Cashflow Operasional", format_rp(cf_operasional))
        with col_cf2: metric_card("🏗️ Cashflow Investasi", format_rp(cf_investasi))
        col_cf3, col_cf4 = st.columns(2)
        with col_cf3: metric_card("🏦 Cashflow Pendanaan", format_rp(cf_pendanaan))
        with col_cf4: metric_card("📊 Total Cashflow", format_rp(cf_total))
    
        # Interpretasi Cashflow
        if cf_operasional < 0:
            if total_piutang > abs(cf_operasional):
                st.info(f"Cashflow operasional negatif karena pembayaran belum diterima, piutang {format_rp(total_piutang)} akan memperbaiki.")
            else:
                st.error("Cashflow operasional negatif & piutang tidak cukup. Evaluasi pengeluaran & pemasukan.")
        else:
            st.success("Cashflow operasional positif — aktivitas bisnis menghasilkan kas bersih.")
    
    
    
        st.markdown("""
        **Cashflow Statement** menjelaskan dari mana uang datang dan ke mana uang pergi.
    
        **Cashflow Operasional**
        Uang dari aktivitas utama bisnis:  
        - Penjualan  
        - Pembayaran customer  
        - Pengeluaran operasional  
    
        Jika angkanya **positif**, bisnis menghasilkan uang dari aktivitas rutin.  
        Jika **negatif**, operasional menyedot kas.
    
        **Cashflow Investasi**
        Terkait pembelian aset (inventaris, peralatan).  
        Biasanya NEGATIF (karena beli aset).
    
        **Cashflow Pendanaan**  
        Terkait hutang & tambahan modal.  
        Contoh: bayar cicilan kartu kredit.
    
        **Total Cashflow**  
        Perubahan kas dalam periode tersebut.
        """)
    
        
        # =============================
        # 🔍 Insight Keuangan Tambahan
        # =============================
        st.markdown("## Kesimpulan")
        
        # 1️⃣ Laba Bersih
        if laba_bersih < 0:
            if total_piutang > abs(laba_bersih):
                st.info(
                    f"Laba bersih periode ini terlihat negatif karena sebagian besar pendapatan "
                    f"masih dalam bentuk piutang sebesar {format_rp(total_piutang)}. "
                    "Jika piutang diterima, laba akan berbalik positif."
                )
            else:
                st.warning(
                    "⚠️ Laba bersih negatif. Perlu mengevaluasi harga jual, biaya modal, atau biaya operasional."
                )
        
        # 2️⃣ Cashflow Operasional
        if cf_operasional < 0:
            if total_piutang > abs(cf_operasional):
                st.info(
                    f"Cashflow operasional saat ini negatif sebesar {format_rp(cf_operasional)}, "
                    f"namun sebagian besar pendapatan masih piutang ({format_rp(total_piutang)}). "
                    "Setelah piutang diterima, cashflow bisa menjadi positif."
                )
            else:
                st.error(
                    f"🔥 Cashflow operasional negatif ({format_rp(cf_operasional)}). "
                    "Bisnis tidak menghasilkan uang dari kegiatan utama saat ini."
                )
        else:
            st.success(f"💰 Cashflow operasional positif ({format_rp(cf_operasional)}). Arus kas sehat.")
        
        # 3️⃣ Piutang vs Kas
        if aset_piutang > aset_kas:
            st.info(
                f"🟡 Piutang ({format_rp(aset_piutang)}) lebih besar dari kas ({format_rp(aset_kas)}). "
                "Perlu perencanaan penerimaan pembayaran agar kas tetap lancar."
            )
        
        # 4️⃣ Hutang vs Kas
        if hutang_total > aset_kas:
            if total_piutang > (hutang_total - aset_kas):
                st.info(
                    f"Kas saat ini ({format_rp(aset_kas)}) lebih kecil dari total hutang ({format_rp(hutang_total)}), "
                    f"namun sebagian pendapatan masih piutang ({format_rp(total_piutang)}). "
                    "Setelah piutang diterima, kas akan cukup untuk menutupi kewajiban."
                )
            else:
                st.error(
                    f"⚠️ Kas ({format_rp(aset_kas)}) lebih kecil dari hutang ({format_rp(hutang_total)}). "
                    "Perlu strategi pembayaran hutang untuk menghindari masalah arus kas."
                )
        else:
            st.success(
                f"✅ Struktur keuangan aman: kas ({format_rp(aset_kas)}) cukup untuk menutup hutang jangka pendek ({format_rp(hutang_total)})."
            )
        
        # 5️⃣ Efisiensi Operasional
        if operasional_filtered > pendapatan_filtered * 0.7:
            st.warning(
                f"📉 Beban operasional ({format_rp(operasional_filtered)}) >70% dari pendapatan ({format_rp(pendapatan_filtered)}). "
                "Perlu evaluasi efisiensi biaya."
            )
    
    
    
        
        #st.markdown("### 🔍 Data Cashflow Realtime")
        #if "Tanggal" in df_cashflow.columns:
         #   df_cashflow["Tanggal"] = pd.to_datetime(df_cashflow["Tanggal"], errors='coerce')
          #  df_cashflow["Tanggal"].fillna(pd.Timestamp.today(), inplace=True)
        
        #st.dataframe(df_cashflow.sort_values(by="Tanggal", ascending=False), use_container_width=True)
    
        # ---------------------------
        # Fungsi Aging Report
        # ---------------------------
        
        
    
        
    with st.expander("⏳ Aging Report / Invoice Belum Lunas"):
        if not df_cashflow_combined.empty and not df_data.empty:
    
            # --- Normalisasi Invoice_Key
            df_data["Invoice_Key"] = df_data["Invoice_Key"].astype(str)
            df_cashflow_combined["Invoice_Key"] = df_cashflow_combined["Invoice_Key"].astype(str)
    
            # --- Total pembayaran per invoice
            df_cashflow_combined["Jumlah"] = pd.to_numeric(df_cashflow_combined["Jumlah"], errors="coerce").fillna(0)
            df_payments = (
                df_cashflow_combined[df_cashflow_combined["Tipe"]=="Masuk"]
                .groupby("Invoice_Key")["Jumlah"]
                .sum()
                .reset_index()
                .rename(columns={"Jumlah":"Jumlah Masuk"})
            )
    
            # --- Gabungkan dengan data penjualan
            df_invoice = df_data[["Invoice_Key","Nama Pemesan","No Invoice","Harga Jual","Tgl Pemesanan"]].copy()
            df_invoice = df_invoice.merge(df_payments, on="Invoice_Key", how="left")
            df_invoice["Jumlah Masuk"] = df_invoice["Jumlah Masuk"].fillna(0)
    
            # --- Hitung Piutang
            df_invoice["Piutang"] = df_invoice["Harga Jual"] - df_invoice["Jumlah Masuk"]
    
            # --- Filter yang belum lunas
            df_unpaid = df_invoice[df_invoice["Piutang"] > 1000].copy()
    
            if not df_unpaid.empty:
    
                # --- AGGREGATE PER INVOICE ---
                df_agg = df_unpaid.groupby(
                    ["Invoice_Key","Nama Pemesan","No Invoice"], as_index=False
                ).agg({
                    "Piutang":"sum",
                    "Tgl Pemesanan":"min"
                })
    
                # --- Hitung Aging ---
                df_agg["Tanggal Pemesanan"] = df_agg["Tgl Pemesanan"].fillna(pd.Timestamp.today())
                df_agg["Aging (hari)"] = (pd.Timestamp.today().normalize() - pd.to_datetime(df_agg["Tanggal Pemesanan"]).dt.normalize()).dt.days
                df_agg["Overdue"] = df_agg["Aging (hari)"] > 30
    
                # --- Format Rupiah ---
                df_agg["Piutang"] = df_agg["Piutang"].apply(lambda x: f"Rp {int(x):,}".replace(",", "."))
    
                # --- Tampilkan ---
                df_display = df_agg[[
                    "Nama Pemesan","No Invoice","Tanggal Pemesanan","Piutang","Aging (hari)","Overdue"
                ]]
    
                def highlight_overdue(row):
                    return ["background-color: #FF9999" if row.Overdue else "" for _ in row]
    
                st.dataframe(df_display.style.apply(highlight_overdue, axis=1), use_container_width=True)
    
            else:
                st.info("🎉 Semua invoice sudah lunas!")
        else:
            st.info("Belum ada data cashflow atau data penjualan untuk Aging Report.")
    
    
    
    
    #=================================================================================================================================================================
    from prophet import Prophet
    from prophet.plot import plot_plotly
    import plotly.graph_objects as go
    
    with st.expander("📘 Laporan Transaksi Penjualan"):
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
    
            def metric_card(title, value):
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-title">{title}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            # Baris 1
            col1, col2 = st.columns(2)
            with col1:
                metric_card("💰 Total Penjualan", f"Rp {int(total_jual):,}".replace(",", "."))
            with col2:
                metric_card("💸 Total Pembelian", f"Rp {int(total_beli):,}".replace(",", "."))
            
            # Baris 2 (full width)
            metric_card("📈 Profit", f"Rp {int(total_profit):,}".replace(",", "."))
    
    
                
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
                df_prophet = (
                    df_prophet
                    .groupby("Tgl Pemesanan")[["Harga Jual (Num)", "Harga Beli (Num)"]]
                    .sum()
                    .reset_index()
                )
            
                df_prophet["ds"] = pd.to_datetime(df_prophet["Tgl Pemesanan"])
                df_prophet["y"] = df_prophet["Harga Jual (Num)"] - df_prophet["Harga Beli (Num)"]
                df_prophet = df_prophet[["ds", "y"]].dropna()
            
                # 🚦 VALIDASI DATA (EXIT UI, BUKAN EXIT SCRIPT)
                if len(df_prophet) < 2:
                    st.info("📭 **Data belum cukup untuk membuat prediksi.**")
                else:
                    # ===============================
                    # SEMUA KODE DI BAWAH INI HANYA
                    # AKAN JALAN JIKA DATA CUKUP
                    # ===============================
            
                    # (opsional) batasi 3 bulan terakhir
                    if (df_prophet["ds"].max() - df_prophet["ds"].min()).days > 90:
                        df_prophet = df_prophet[
                            df_prophet["ds"] >= df_prophet["ds"].max() - pd.DateOffset(months=3)
                        ]
            
                    model = Prophet()
                    model.fit(df_prophet)
            
                    future = model.make_future_dataframe(periods=90)
                    forecast = model.predict(future)
            
                    # 🎛️ Input UI
                    all_months = [f"{i:02d}" for i in range(1, 13)]
                    month_map = {
                        "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
                        "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
                        "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
                    }
            
                    month_select = st.selectbox(
                        "📅 Pilih Bulan",
                        options=all_months,
                        format_func=lambda x: month_map[x]
                    )
            
                    year_select = st.selectbox(
                        "🗓️ Pilih Tahun",
                        options=sorted(forecast["ds"].dt.year.unique())
                    )
            
                    # 🧠 Filter forecast
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
                        delta_trend = (
                            forecast_selected["trend"].iloc[-1]
                            - forecast_selected["trend"].iloc[0]
                        )
            
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=forecast_selected["ds"],
                            y=forecast_selected["yhat"],
                            name="Prediksi Laba"
                        ))
                        fig.update_layout(
                            title=f"📈 Prediksi Laba - {month_map[month_select]} {year_select}"
                        )
                        st.plotly_chart(fig, use_container_width=True)
            
                        st.markdown("### 📊 Ringkasan Prediksi Bulanan:")
                        st.markdown(f"""
                        - 🗓️ Bulan dipilih: **{month_map[month_select]} {year_select}**
                        - 📈 **Total laba diprediksi**: Rp {int(total_yhat):,}
                        - 🔼 **Hari terbaik (estimasi)**: Rp {int(max_yhat):,}
                        - 🔽 **Hari terendah (estimasi)**: Rp {int(min_yhat):,}
                        - 📊 **Tren bulan ini**: {'meningkat' if delta_trend > 0 else 'menurun' if delta_trend < 0 else 'stabil'} (Δ Rp {int(delta_trend):,})
                        """)

    
    
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

#======================================================================================================================================
#from streamlit_option_menu import option_menu
#import streamlit as st

# Sidebar Menu
#with st.sidebar:
 #   selected = option_menu(
  #      menu_title="Menu Utama",  # required
   #     options=["Dashboard", "Cashflow", "Invoice", "Transaksi", "Settings"],  # required
    #    icons=["bar-chart", "currency-dollar", "file-earmark-text", "truck", "gear"],  # optional
     #   menu_icon="cast",  # optional
      #  default_index=0,  # optional
    #)

# Konten berdasarkan menu
#if selected == "Dashboard":
 #   st.title("📊 Ringkasan Dashboard")
    
#elif selected == "Cashflow":
 #   st.title("💸 Laporan Arus Kas")
    # tampilkan kode cashflow Anda di sini

#elif selected == "Invoice":
 #   st.title("🧾 Manajemen Invoice")
    # tampilkan invoice belum lunas, reminder, dll

#elif selected == "Transaksi":
 #   st.title("📦 Transaksi Pemesanan")
    # tampilkan semua transaksi

#elif selected == "Settings":
 #   st.title("⚙️ Pengaturan Sistem")
    # form setting admin, kategori, dll
#=============================================================================================================================================================
# '''
# import streamlit as st
# import pandas as pd
# from sheets_utils import connect_to_gsheet
# from datetime import datetime

# if 'reset_counter' not in st.session_state:
#     st.session_state.reset_counter = 0

# if 'transactions_df' not in st.session_state:
#     st.session_state['transactions_df'] = pd.DataFrame()  # nanti akan di-load dari Sheet

# # ======================
# # Helper Functions
# # ======================
# def parse_currency(x):
#     if pd.isna(x) or x == "":
#         return 0.0
#     if isinstance(x, (int, float)):
#         return float(x)
#     x = str(x).replace("Rp", "").replace(".", "").replace(",", ".").strip()
#     return float(x)

# def parse_lunas_date(keterangan):
#     """Extract date from 'Lunas dd/mm/yy' or 'Lunas dd/mm/yyyy'"""
#     import re
#     if pd.isna(keterangan):
#         return None
#     match = re.search(r"Lunas (\d{1,2}/\d{1,2}/\d{2,4})", keterangan)
#     if match:
#         date_str = match.group(1)
#         for fmt in ("%d/%m/%Y", "%d/%m/%y"):
#             try:
#                 return datetime.strptime(date_str, fmt).date()
#             except:
#                 continue
#     return None

# def hitung_saldo(accounts, tx):
#     saldo = {
#         row['account_name'].strip(): parse_currency(row['balance'])
#         for _, row in accounts.iterrows()
#     }

#     for _, row in tx.iterrows():
#         jumlah = row['jumlah']  # ❗ JANGAN parse lagi
#         sumber = row['rekening_sumber']
#         tujuan = row['rekening_tujuan']

#         if sumber and sumber in saldo:
#             saldo[sumber] -= jumlah

#         if tujuan and tujuan in saldo:
#             saldo[tujuan] += jumlah

#     return saldo


# def generate_tx_id(existing_tx, tanggal, prefix=""):
#     """Buat ID unik YYYYMMDDXXXX sesuai transaksi sebelumnya"""
#     date_str = tanggal.strftime("%Y%m%d")
#     if existing_tx is None or existing_tx.empty:
#         counter = 1
#     else:
#         if 'tanggal' not in existing_tx.columns or 'tx_id' not in existing_tx.columns:
#             raise ValueError("existing_tx harus memiliki kolom 'tanggal' dan 'tx_id'")
#         mask = existing_tx['tanggal'] == tanggal.strftime("%Y-%m-%d")
#         if prefix:
#             mask &= existing_tx['tx_id'].astype(str).str.startswith(prefix + date_str)
#         counter = mask.sum() + 1
#     return f"{prefix}{date_str}{counter:04d}"

# # ======================
# # Load Sheet & Data
# # ======================
# SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# tx_ws  = connect_to_gsheet(SHEET_ID, "TRANSACTIONS")
# acc_ws = connect_to_gsheet(SHEET_ID, "ACCOUNTS")
# data_ws = connect_to_gsheet(SHEET_ID, "Data")

# accounts = pd.DataFrame(acc_ws.get_all_records())
# accounts['account_name'] = accounts['account_name'].str.strip()

# transactions = pd.DataFrame(tx_ws.get_all_records())
# if not transactions.empty:
#     transactions['jumlah'] = transactions['jumlah'].apply(parse_currency)

# st.session_state['transactions_df'] = transactions.copy()
# saldo_map = hitung_saldo(accounts, st.session_state['transactions_df'])

# data = pd.DataFrame(data_ws.get_all_records())
# data['Tgl Pemesanan'] = pd.to_datetime(data['Tgl Pemesanan'], dayfirst=True)
# data_filtered = data[data['Tgl Pemesanan'] >= pd.to_datetime("2026-02-01")]


# # ======================
# # Mapping Rekening → Kategori Berdasarkan Jenis Transaksi
# # ======================
# rekening_to_categories = {
#     "Rumah Tangga": {
#         "Pemasukan": [
#             "Pendapatan / Pemasukan"
#         ],
#         "Pengeluaran": [
#             "Makanan & Minuman",
#             "Perumahan",
#             "Transportasi",
#             "Kesehatan",
#             "Pendidikan",
#             "Komunikasi & Internet",
#             "Pakaian & Perlengkapan",
#             "Hiburan & Rekreasi",
#             "Cicilan",
#             "Lain-lain",
#             "Tabungan & Investasi",
#             "Dana Cadangan / Darurat"
#         ]
#     },
#     "Bisnis Operasional": {
#         "Pemasukan": ["Pendapatan / Revenue"],
#         "Pengeluaran": ["Operasional", "Finansial", "Dana Cadangan / Investasi Bisnis", "Lain-lain"]
#     },
#     "Cadangan Bisnis": {
#         "Pemasukan": [],
#         "Pengeluaran": ["Dana Cadangan / Investasi"]
#     },
#     "Tabungan / Investasi": {
#         "Pemasukan": ["Pendapatan / Return"],
#         "Pengeluaran": ["Tabungan & Investasi", "Dana Cadangan / Darurat"]
#     }
# }

# # ======================
# # Mapping Kategori → Subkategori
# # ======================
# subcategories = {
#     # ==== Rumah Tangga ====
#     "Pendapatan / Pemasukan": [
#         "Gaji / Upah",
#         "Bonus / Insentif",
#         "Usaha / Bisnis sampingan",
#         "Investasi / Dividen",
#         "Hadiah / Lain-lain"
#     ],
#     "Makanan & Minuman": ["Belanja bahan makanan", "Makan di luar / restoran", "Minuman & cemilan"],
#     "Perumahan": ["Sewa rumah", "Listrik, air, gas", "Perawatan rumah & kebun", "PDAM", "Internet rumah"],
#     "Transportasi": ["BBM / listrik kendaraan listrik", "Transportasi umum / ojek online", "Servis kendaraan & asuransi"],
#     "Kesehatan": ["Periksa Dokter", "Obat-obatan", "Asuransi kesehatan", "Dokter / klinik"],
#     "Pendidikan": ["Sekolah / kuliah", "Buku & alat tulis", "Kursus / les tambahan"],
#     "Komunikasi & Internet": ["Pulsa & paket data", "TV kabel / streaming"],
#     "Pakaian & Perlengkapan": ["Pakaian & sepatu", "Perawatan diri / kosmetik"],
#     "Hiburan & Rekreasi": ["Liburan / jalan-jalan", "Hobi & olahraga", "Bioskop / konser"],
#     "Cicilan": ["KPR", "KLK", "Mobil"],
#     "Lain-lain": ["Hadiah", "Donasi / sedekah", "Keperluan mendadak"],
#     "Tabungan & Investasi": ["Tabungan darurat", "Dana pendidikan anak", "Dana pensiun", "Investasi saham / obligasi / reksa dana", "Properti / emas"],
#     "Dana Cadangan / Darurat": ["Perbaikan rumah / kendaraan mendadak", "Kesehatan mendadak", "Kehilangan pekerjaan atau penghasilan"],

#     # ==== Bisnis Operasional ====
#     "Pendapatan / Revenue": [
#         "Penjualan tiket pesawat",
#         "Penjualan tiket kereta api",
#         "Pemesanan hotel / akomodasi",
#         "Biaya layanan / service fee",
#         "Komisi dari pihak ketiga (maskapai, hotel, OTA)",
#         "Promo / cashback / insentif dari partner"
#     ],
#     "Operasional": [
#         "Gaji & Tunjangan",
#         "Gaji karyawan front office / customer service",
#         "Gaji marketing / sales",
#         "Bonus dan tunjangan karyawan",
#         "Sewa & Utilitas",
#         "Sewa kantor / ruang kerja",
#         "Listrik, air, internet, telepon",
#         "Maintenance kantor",
#         "Teknologi & Sistem",
#         "Biaya software booking / sistem reservasi",
#         "Hosting website / domain",
#         "Aplikasi / API maskapai, kereta, hotel",
#         "Maintenance & upgrade sistem",
#         "Pemasaran & Promosi",
#         "Iklan online (Google, Facebook, Instagram)",
#         "Promo / diskon untuk pelanggan",
#         "Sponsorship / kerjasama dengan partner",
#         "Transportasi & Perjalanan",
#         "Transportasi karyawan",
#         "Perjalanan dinas / meeting partner",
#         "Administrasi & Kantor",
#         "Alat tulis & perlengkapan kantor",
#         "Perlengkapan kebersihan",
#         "Biaya pos & courier"
#     ],
#     "Finansial": ["Pajak penghasilan / PPN", "Biaya bank (transfer, administrasi)", "Biaya kartu kredit / pinjaman modal", "Asuransi bisnis / aset"],
#     "Dana Cadangan / Investasi Bisnis": ["Dana darurat untuk operasional", "Investasi sistem / teknologi baru", "Upgrade kantor / ruang kerja", "Pelatihan & pengembangan SDM"],
#     "Lain-lain": ["Denda atau penalti tiket", "Refund / komplain pelanggan", "Hadiah / apresiasi pelanggan", "Biaya legal / konsultasi hukum"],

#     # ==== Cadangan Bisnis ====
#     "Dana Cadangan / Investasi": ["Investasi jangka panjang", "Modal ekspansi bisnis", "Dana keamanan / likuiditas"],

#     # ==== Tabungan / Investasi ====
#     "Pendapatan / Return": ["Dividen saham", "Bunga deposito", "Keuntungan reksa dana", "Keuntungan properti / emas"],
#     "Tabungan & Investasi": ["Tabungan darurat", "Dana pendidikan", "Dana pensiun", "Investasi saham / obligasi / reksa dana", "Properti / emas"],
#     "Dana Cadangan / Darurat": ["Dana tak terduga", "Perbaikan aset mendadak", "Kehilangan penghasilan"]
# }

# # ======================
# # UI Streamlit
# # ======================
# with st.expander("💰 Pencatatan Keuangan Profesional"):

#     # ----------------------
#     # Trigger generate otomatis
#     # ----------------------
#     if "generate_triggered" not in st.session_state:
#         st.session_state["generate_triggered"] = False
    
#     if st.button("Generate Transaksi Otomatis"):
#         st.session_state["generate_triggered"] = True
    
#     if st.session_state["generate_triggered"]:
#         new_tx_rows = []

#         # ----------------------
#         # Buat set key unik dari transaksi yang sudah ada
#         # ----------------------
#         existing_tx_keys = set()
#         for _, row_tx in st.session_state['transactions_df'].iterrows():
#             catatan = str(row_tx.get('catatan', ''))
#             if "key:" in catatan:
#                 key = catatan.split("key:")[1].strip()
#                 existing_tx_keys.add(key)

#         # ----------------------
#         # Loop data referensi
#         # ----------------------
#         for idx, row in data_filtered.iterrows():
#             sumber_dana = str(row.get("Sumber Dana", "")).strip().lower()
#             if sumber_dana not in ["cash", "tunai", "dana tunai/cash"]:
#                 continue  # Abaikan Credit Card

#             # Buat unique key dari 4 field mandatory
#             unique_key = (
#                 f"{row['Tgl Berangkat']}|{row['Kode Booking']}|"
#                 f"{row['No Penerbangan / Hotel / Kereta']}|{row['Nama Customer']}"
#             )

#             if unique_key in existing_tx_keys:
#                 continue  # Sudah tercatat, skip

#             # ----------------------
#             # Pengeluaran
#             # ----------------------
#             tgl_pengeluaran = pd.to_datetime(row['Tgl Pemesanan']).date()
#             harga_beli = parse_currency(row['Harga Beli'])
#             tipe = row['Tipe']

#             tx_id_out = generate_tx_id(st.session_state['transactions_df'], tgl_pengeluaran, prefix="OUT")
#             catatan = f"Generated from Sales System / Cash Transaction | key:{unique_key}"

#             new_tx_rows.append([
#                 tx_id_out,
#                 tgl_pengeluaran,
#                 "Pengeluaran",
#                 "Bisnis Operasional",
#                 "",
#                 harga_beli,
#                 "Pembelian",
#                 tipe,
#                 catatan
#             ])

#             # Tandai key sudah tercatat agar tidak digenerate lagi
#             existing_tx_keys.add(unique_key)

#         # ----------------------
#         # Preview hasil generate
#         # ----------------------
#         if new_tx_rows:
#             st.session_state['new_tx_rows'] = new_tx_rows
#             st.success(f"{len(new_tx_rows)} transaksi cash siap disimpan ✅")
#             df_new_tx = pd.DataFrame(
#                 new_tx_rows,
#                 columns=['tx_id', 'tanggal', 'jenis', 'rekening_sumber', 'rekening_tujuan',
#                          'jumlah', 'kategori', 'subkategori', 'catatan']
#             )
#             st.dataframe(df_new_tx)
#         else:
#             st.info("Tidak ada transaksi cash baru yang perlu digenerate.")

#     # ----------------------
#     # Trigger save ke TRANSACTIONS
#     # ----------------------
#     if 'new_tx_rows' in st.session_state and st.session_state['new_tx_rows']:
#         if st.button("Simpan ke TRANSACTIONS"):
#             for row in st.session_state['new_tx_rows']:
#                 row_to_save = [
#                     str(row[0]),
#                     row[1].strftime("%Y-%m-%d") if hasattr(row[1], 'strftime') else str(row[1]),
#                     str(row[2]),
#                     str(row[3]),
#                     str(row[4]),
#                     float(row[5]),
#                     str(row[6]),
#                     str(row[7]),
#                     str(row[8])
#                 ]
#                 try:
#                     tx_ws.append_row(row_to_save, value_input_option="USER_ENTERED")
#                 except Exception as e:
#                     st.error(f"Gagal menyimpan {row_to_save[0]}: {e}")
#                     continue

#                 # Update local dataframe
#                 st.session_state['transactions_df'] = pd.concat([
#                     st.session_state['transactions_df'],
#                     pd.DataFrame([row_to_save], columns=st.session_state['transactions_df'].columns)
#                 ], ignore_index=True)

#             # Update saldo
#             saldo_map = hitung_saldo(accounts, st.session_state['transactions_df'])
#             st.session_state['new_tx_rows'] = []
#             st.success("Transaksi berhasil disimpan ✅")




#     # =========================
#     # Input Manual
#     # =========================
#     with st.expander("Input Transaksi"):

#         jenis = st.selectbox(
#             "Jenis Transaksi",
#             ["Pengeluaran", "Pemasukan", "Transfer Antar Rekening"]
#         )
#         tanggal = st.date_input("Tanggal", datetime.today())

#         # ----------------------
#         # Pengeluaran
#         # ----------------------
#         if jenis == "Pengeluaran":
#             rekening = st.selectbox("Rekening Sumber", accounts['account_name'])

#             kategori_list = rekening_to_categories.get(rekening, {}).get("Pengeluaran", ["Pilih Kategori"])
#             kategori = st.selectbox("Kategori", kategori_list)

#             sub_list = subcategories.get(kategori, ["Pilih Subkategori"])
#             sub = st.selectbox("Sub Kategori", sub_list)

#             jumlah = st.number_input(
#                 "Jumlah (Rp)",
#                 min_value=1,
#                 step=1000,
#                 key=f"jumlah_{st.session_state.reset_counter}"
#             )
#             catatan = st.text_input(
#                 "Catatan",
#                 key=f"catatan_{st.session_state.reset_counter}"
#             )

#             st.markdown("#### 🧾 Preview Transaksi (cek dulu sebelum simpan)")
#             st.info(f"""
# **Jenis**     : Pengeluaran  
# **Tanggal**  : {tanggal.strftime('%d %B %Y')}  
# **Rekening** : {rekening}  
# **Kategori** : {kategori}  
# **Sub**      : {sub}  
# **Jumlah**   : Rp {jumlah:,.0f}
# """)

#             if st.button("Simpan Pengeluaran"):
#                 if saldo_map.get(rekening, 0) < jumlah:
#                     st.error("Saldo tidak mencukupi.")
#                 else:
#                     tx_id = generate_tx_id(transactions, tanggal, prefix="OUT")
#                     tx_ws.append_row([
#                         tx_id,
#                         tanggal.strftime("%Y-%m-%d"),
#                         "Pengeluaran",
#                         rekening,
#                         "",
#                         float(jumlah),
#                         kategori,
#                         sub,
#                         catatan
#                     ], value_input_option="USER_ENTERED")

#                     saldo_map[rekening] -= jumlah
#                     st.session_state.reset_counter += 1
#                     st.success("Pengeluaran tersimpan ✅")
#                     st.rerun()

#         # ----------------------
#         # Pemasukan
#         # ----------------------
#         elif jenis == "Pemasukan":
#             rekening = st.selectbox("Rekening Tujuan", accounts['account_name'])

#             kategori_list = rekening_to_categories.get(rekening, {}).get("Pemasukan", ["Pilih Kategori"])
#             kategori = st.selectbox("Kategori", kategori_list)

#             sub_list = subcategories.get(kategori, ["Pilih Subkategori"])
#             sub = st.selectbox("Sub Kategori", sub_list)

#             jumlah = st.number_input(
#                 "Jumlah (Rp)",
#                 min_value=1,
#                 step=1000,
#                 key=f"jumlah_{st.session_state.reset_counter}"
#             )
#             catatan = st.text_input(
#                 "Catatan",
#                 key=f"catatan_{st.session_state.reset_counter}"
#             )

#             st.markdown("#### 🧾 Preview Transaksi (cek dulu sebelum simpan)")
#             st.info(f"""
# **Jenis**     : Pemasukan  
# **Tanggal**  : {tanggal.strftime('%d %B %Y')}  
# **Rekening** : {rekening}  
# **Kategori** : {kategori}  
# **Sub**      : {sub}  
# **Jumlah**   : Rp {jumlah:,.0f}
# """)

#             if st.button("Simpan Pemasukan"):
#                 tx_id = generate_tx_id(transactions, tanggal, prefix="IN")
#                 tx_ws.append_row([
#                     tx_id,
#                     tanggal.strftime("%Y-%m-%d"),
#                     "Pemasukan",
#                     "",
#                     rekening,
#                     float(jumlah),
#                     kategori,
#                     sub,
#                     catatan
#                 ], value_input_option="USER_ENTERED")

#                 saldo_map[rekening] += jumlah
#                 st.session_state.reset_counter += 1
#                 st.success("Pemasukan tersimpan ✅")
#                 st.rerun()

#         # ----------------------
#         # Transfer Antar Rekening
#         # ----------------------
#         else:
#             asal = st.selectbox("Rekening Asal", accounts['account_name'])
#             tujuan = st.selectbox("Rekening Tujuan", [a for a in accounts['account_name'] if a != asal])
#             jumlah = st.number_input(
#                 "Jumlah (Rp)",
#                 min_value=1,
#                 step=1000,
#                 key=f"jumlah_{st.session_state.reset_counter}"
#             )
#             catatan = st.text_input(
#                 "Catatan",
#                 key=f"catatan_{st.session_state.reset_counter}"
#             )

#             st.caption(
#                 "ℹ️ Transfer antar rekening tidak memerlukan kategori "
#                 "karena tidak memengaruhi laporan pemasukan atau pengeluaran."
#             )

#             st.markdown("#### 🧾 Preview Transaksi (cek dulu sebelum transfer)")
#             st.info(f"""
# **Jenis**        : Transfer Antar Rekening  
# **Tanggal**     : {tanggal.strftime('%d %B %Y')}  
# **Dari Rekening** : {asal}  
# **Ke Rekening**   : {tujuan}  
# **Jumlah**      : Rp {jumlah:,.0f}  
# """)

#             if st.button("Simpan Transfer"):
#                 if saldo_map.get(asal, 0) < jumlah:
#                     st.error("Saldo tidak mencukupi.")
#                 else:
#                     tx_id = generate_tx_id(transactions, tanggal, prefix="TRF")
#                     tx_ws.append_row([
#                         tx_id,
#                         tanggal.strftime("%Y-%m-%d"),
#                         "Transfer",
#                         asal,
#                         tujuan,
#                         float(jumlah),
#                         "Transfer Antar Rekening",
#                         "",
#                         catatan
#                     ], value_input_option="USER_ENTERED")

#                     saldo_map[asal] -= jumlah
#                     saldo_map[tujuan] += jumlah
#                     st.session_state.reset_counter += 1
#                     st.success("Transfer tersimpan ✅")
#                     st.rerun()


#     #st.write("SALDO_MAP FULL:", saldo_map)

#     # ======================
#     # LAPORAN SALDO
#     # ======================
#     with st.expander("Jumlah Saldo Rekening", expanded=True):
#         st.subheader("📊 Saldo Rekening Terkini")
    
    
#         icons = {
#             "Kas Pribadi": "🏦",
#             "BCA Bisnis Operasional": "🏢",
#             "Rekening Investasi": "💰",
#             "Rekening Tabungan": "💳",
#         }
        
#         # Ambil saldo_map yang sudah dihitung dari hitung_saldo()
#         saldo_items = list(saldo_map.items())

#         # Buat kolom 2 kartu per baris
#         for i in range(0, len(saldo_items), 2):
#             cols = st.columns(2)
#             for j, col in enumerate(cols):
#                 idx = i + j
#                 if idx < len(saldo_items):
#                     rekening, saldo = saldo_items[idx]
#                     #st.write(f"DEBUG {rekening}: {saldo}")
#                     icon = icons.get(rekening, "")
#                     with col:
#                         metric_card(f"{icon} {rekening}", f"Rp {saldo:,.0f}")

#     with st.expander("📄 Detail Transaksi"):
#         # Pilih jenis filter
#         filter_type = st.radio(
#             "Filter Transaksi Berdasarkan",
#             ["Semua", "Rentang Tanggal", "Bulan", "Tahun"],
#             key="filter_type"
#         )
    
#         # Pilih rekening (opsional)
#         rekening_filter = st.selectbox(
#             "Pilih Rekening",
#             ["Semua"] + list(accounts['account_name']),
#             key="filter_rekening"
#         )
    
#         # Inisialisasi filter tanggal / bulan / tahun
#         tanggal_awal, tanggal_akhir, bulan_filter, tahun_filter = None, None, None, None
    
#         if filter_type == "Rentang Tanggal":
#             col1, col2 = st.columns(2)
#             with col1:
#                 tanggal_awal = st.date_input(
#                     "Tanggal Awal",
#                     value=datetime.today(),
#                     key="tanggal_awal_filter"
#                 )
#             with col2:
#                 tanggal_akhir = st.date_input(
#                     "Tanggal Akhir",
#                     value=datetime.today(),
#                     key="tanggal_akhir_filter"
#                 )
    
#         elif filter_type == "Bulan":
#             bulan_filter = st.selectbox(
#                 "Bulan",
#                 [f"{i:02d}" for i in range(1, 13)],
#                 key="filter_bulan"
#             )
    
#         elif filter_type == "Tahun":
#             tahun_filter = st.selectbox(
#                 "Tahun",
#                 sorted(transactions['tanggal'].apply(lambda x: pd.to_datetime(x).year).unique(), reverse=True),
#                 key="filter_tahun"
#             )
    
#         # =========================
#         # Terapkan Filter ke Dataframe
#         # =========================
#         df_display = transactions.copy()
    
#         # Filter rekening
#         if rekening_filter != "Semua":
#             df_display = df_display[
#                 (df_display['rekening_sumber'] == rekening_filter) |
#                 (df_display['rekening_tujuan'] == rekening_filter)
#             ]
    
#         # Filter berdasarkan jenis filter
#         if filter_type == "Rentang Tanggal" and tanggal_awal and tanggal_akhir:
#             df_display = df_display[
#                 (pd.to_datetime(df_display['tanggal']) >= pd.to_datetime(tanggal_awal)) &
#                 (pd.to_datetime(df_display['tanggal']) <= pd.to_datetime(tanggal_akhir))
#             ]
#         elif filter_type == "Bulan" and bulan_filter:
#             df_display = df_display[
#                 pd.to_datetime(df_display['tanggal']).dt.month == int(bulan_filter)
#             ]
#         elif filter_type == "Tahun" and tahun_filter:
#             df_display = df_display[
#                 pd.to_datetime(df_display['tanggal']).dt.year == int(tahun_filter)
#             ]
    
#         # Tampilkan dataframe hasil filter
#         st.markdown(f"#### Hasil Transaksi ({len(df_display)} baris)")
#         st.dataframe(df_display.reset_index(drop=True))
# '''

