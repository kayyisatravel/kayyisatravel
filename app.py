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

#refresh
# --- PAGE CONFIG ---
st.set_page_config(page_title="OCR & Dashboard Tiket", layout="centered")

# --- CACHE RESOURCES ---
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['en', 'id'], gpu=False)

@st.cache_data
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
    Kirim DataFrame ke Google Sheets pada worksheet 'Data'.
    """
    if df is None or df.empty:
        st.warning('Data kosong atau invalid')
        return
    ws = connect_to_gsheet(SHEET_ID, 'Data')
    append_dataframe_to_sheet(df, ws)
    st.success('✅ Berhasil simpan ke Google Sheets')

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
    st.markdown('<div class="main-header">Dashboard Tiket | <span class="highlight">Kayyisa Tour & Travel</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Input & Simpan Data Pesanan</div>', unsafe_allow_html=True)

with col2:
    st.image("https://borneoshops.com/image/marketplace/storeicon.png", width=200)

st.markdown("""<hr style="border-top: 1px solid #7f8c8d;">""", unsafe_allow_html=True)

# --- SECTION 1: UPLOAD & OCR ---
#st.markdown('---')
with st.expander("Upload Gambar atau PDF untuk OCR"):
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
                    edited_df = st.data_editor(df_ocr, num_rows="dynamic", use_container_width=True)
    
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
with st.expander('Bulk Manual Input'):
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
    if "bulk_entries_raw" in st.session_state and st.session_state.bulk_entries_raw:
        st.markdown("#### 📝 Edit Data per Entri (Opsional)")
        
        selected_index = st.selectbox(
            "Pilih entri untuk diedit",
            range(len(st.session_state.bulk_entries_raw)),
            format_func=lambda x: st.session_state.bulk_labels[x]
        )
    
        selected_df = st.session_state.bulk_entries_raw[selected_index]
        edited_df = st.data_editor(
            selected_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_bulk_{selected_index}"
        )
    
        # Simpan hasil edit ke entri yang dipilih
        st.session_state.bulk_entries_raw[selected_index] = edited_df
    
        # Gabungkan ulang semua data setelah edit
        st.session_state.bulk_parsed = pd.concat(st.session_state.bulk_entries_raw, ignore_index=True)
    
        st.markdown("#### 📊 Preview Gabungan Semua Entri Setelah Diedit")
        st.dataframe(st.session_state.bulk_parsed, use_container_width=True)
    
    # Bulk save button
    if st.session_state.get("bulk_parsed") is not None and st.button("📤 Simpan Bulk ke GSheet"):
        save_gsheet(st.session_state.bulk_parsed)
        for k in ["bulk_parsed", "bulk_input", "file_uploader"]:
            st.session_state.pop(k, None)
        st.rerun()

# --- SECTION 3: SAVE TO GOOGLE SHEETS ---
st.markdown('---')
#st.subheader('3. Simpan ke Google Sheets')
if st.session_state.parsed_entries_ocr is not None and st.button('📤 Simpan OCR ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_ocr)
    for k in [
        'parsed_entries_ocr', 'parsed_entries_manual', 'manual_input_area', 'bulk_input', 'file_uploader'
    ]:
        st.session_state.pop(k, None)
    st.rerun()

if st.session_state.parsed_entries_manual is not None and st.button('📤 Simpan Manual ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_manual)
    for k in ['parsed_entries_manual', 'manual_input_area', 'file_uploader']:
        st.session_state.pop(k, None)
    st.rerun()
