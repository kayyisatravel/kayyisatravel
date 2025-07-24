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
                            if col == "Pemesan":
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
                st.success(f"✅ {len(edited_rows)} baris berhasil diperbarui.")
                st.experimental_rerun()

    
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



    # === Filter Tambahan ===
    st.markdown("### 🧍 Filter Tambahan")

    tampilkan_uninvoice_saja = st.checkbox("🔍 Tampilkan hanya yang belum ada Invoice")
    auto_select_25jt = st.checkbox("⚙️ Auto-pilih total penjualan hingga Rp 25 juta")

    nama_filter = st.text_input("Cari Nama Pemesan")
    kode_booking_filter = st.text_input("Cari Kode Booking")
    no_invoice_filter = st.text_input("Cari No Invoice")

    # === Filter Tambahan (lanjutkan dari df_filtered yang sudah disesuaikan di atas) ===
    if nama_filter:
        df_filtered = df_filtered[df_filtered["Nama Pemesan"].str.contains(nama_filter, case=False, na=False)]
    if kode_booking_filter:
        df_filtered = df_filtered[df_filtered["Kode Booking"].astype(str).str.contains(kode_booking_filter, case=False, na=False)]
    
    df_filtered["No Invoice"] = df_filtered["No Invoice"].astype(str).str.strip()
    
    if no_invoice_filter:
        df_filtered = df_filtered[df_filtered["No Invoice"].str.contains(no_invoice_filter.strip(), case=False, na=False)]
    
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
                nama_pemesan_form = st.text_input("Nama Pemesan", row_to_edit.get("Nama Pemesan", ""))
                tgl_pemesanan_form = st.date_input("Tgl Pemesanan", safe_date(row_to_edit.get("Tgl Pemesanan")))
                tgl_berangkat_form = st.date_input("Tgl Berangkat", safe_date(row_to_edit.get("Tgl Berangkat")))
                kode_booking_form = st.text_input("Kode Booking", row_to_edit.get("Kode Booking", ""))
                no_penerbangan_form = st.text_input("No Penerbangan / Hotel / Kereta", row_to_edit.get("No Penerbangan / Hotel / Kereta", ""))
                nama_customer_form = st.text_input("Nama Customer", row_to_edit.get("Nama Customer", ""))
                rute_form = st.text_input("Rute", row_to_edit.get("Rute", ""))
                harga_beli_form = st.number_input("Harga Beli", value=parse_harga(row_to_edit.get("Harga Beli", 0)), format="%.0f")
                harga_jual_form = st.number_input("Harga Jual", value=parse_harga(row_to_edit.get("Harga Jual", 0)), format="%.0f")
                #tipe_form = st.selectbox("Tipe", ["KERETA", "PESAWAT", "HOTEL"], index=["KERETA", "PESAWAT", "HOTEL"].index(str(row_to_edit.get("Tipe", "")).upper()))
                #bf_nbf_form = st.text_input("BF/NBF", row_to_edit.get("BF/NBF", ""))
                no_invoice_form = st.text_input("No Invoice", row_to_edit.get("No Invoice", ""))
                keterangan_form = st.text_input("Keterangan", row_to_edit.get("Keterangan", ""))
                admin_form = st.text_input("Admin", row_to_edit.get("Admin", ""))
            
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
                        tidak_ditemukan = []
            
                        for i, row in selected_norm.iterrows():
                            mask = (
                                (df_all["Nama Pemesan_str"] == row["Nama Pemesan_str"]) &
                                (df_all["Kode Booking_str"] == row["Kode Booking_str"]) &
                                (df_all["Tgl Berangkat_str"] == row["Tgl Berangkat_str"])
                            )
            
                            if mask.any():
                                matching_indices = df_all[mask].index.tolist()
                            
                                for matching_index in matching_indices:
                                    row_number = matching_index + 2  # Baris di GSheets (header + 1)
            
                                    if no_invoice_mass or kosongkan_invoice:
                                        nilai = "" if kosongkan_invoice else no_invoice_mass
                                        worksheet.update_cell(row_number, df_all.columns.get_loc("No Invoice") + 1, nilai)
                                        time.sleep(1)
                                    if keterangan_mass or kosongkan_keterangan:
                                        nilai = "" if kosongkan_keterangan else keterangan_mass
                                        worksheet.update_cell(row_number, df_all.columns.get_loc("Keterangan") + 1, nilai)
                                        time.sleep(1)
                                    if nama_pemesan_mass or kosongkan_nama_pemesan:
                                        nilai = "" if kosongkan_nama_pemesan else nama_pemesan_mass
                                        worksheet.update_cell(row_number, df_all.columns.get_loc("Nama Pemesan") + 1, nilai)
                                        time.sleep(1)    
                                    if admin_mass or kosongkan_admin:
                                        nilai = "" if kosongkan_admin else admin_mass
                                        worksheet.update_cell(row_number, df_all.columns.get_loc("Admin") + 1, nilai)
                                        time.sleep(1)
                                    st.write(f"✅ Update row GSheets: {row_number} untuk: {row['Nama Pemesan_str']} - {row['Kode Booking_str']}")
                                    count += 1
                                else:
                                    gagal += 1
                                    tidak_ditemukan.append({
                                        "Nama Pemesan": row["Nama Pemesan_str"],
                                        "Kode Booking": row["Kode Booking_str"],
                                        "Tgl Berangkat": row["Tgl Berangkat_str"]
                                    })
            
                        # Ringkasan hasil update
                        if count:
                            st.success(f"✅ {count} baris berhasil diperbarui.")
                        if gagal:
                            st.warning(f"⚠️ {gagal} baris tidak ditemukan di GSheets.")
                            with st.expander("🔍 Lihat baris yang gagal dicocokkan"):
                                st.json(tidak_ditemukan)
                        if count == 0 and gagal == 0:
                            st.info("ℹ️ Tidak ada data diproses.")
            
                        st.cache_data.clear()
            
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
            if st.button("📄 Buat Invoice PDF"):
                if not selected_data.empty:
                    records = selected_data.to_dict(orient="records")
                    nama = selected_data["Nama Pemesan"].iloc[0] if not selected_data["Nama Pemesan"].empty else "Pelanggan"
                    tanggal = selected_data["Tgl Pemesanan"].iloc[0]
    
                    # Update nomor invoice unik setiap kali tombol PDF diklik
                    st.session_state.current_unique_invoice_no = now.strftime("%y%m%d%H%M%S")
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

        # Tabel Detail
        with st.expander("📄 Lihat Tabel Detail"):
            st.dataframe(df_filtered, use_container_width=True)


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

with st.expander("🎫 Generator E-Tiket"):
    tipe_tiket = st.radio("Pilih tipe tiket:", ["Kereta", "Hotel"])

    input_text = st.text_area(f"Tempelkan teks tiket {tipe_tiket}", height=300)

    if st.button("Generate Tiket"):
        if input_text.strip():
            data = parsing_ticket(input_text, tipe_tiket)
            st.session_state['last_data'] = data
            st.session_state['tipe_tiket'] = tipe_tiket
        else:
            st.warning("Silakan masukkan data tiket terlebih dahulu.")

    if 'last_data' in st.session_state and st.session_state.get('tipe_tiket') == tipe_tiket:
        data = st.session_state['last_data']
        html = generate_ticket(data, tipe_tiket)
        st.components.v1.html(html, height=800, scrolling=True)

with st.expander("🎫 Generator E-Tiket + Simpan Data"):
    tipe_tiket = st.radio("Pilih tipe tiket:", ["Kereta", "Hotel", "Pesawat"], key="tipe_tiket_radio")
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
