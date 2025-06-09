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

# --- PAGE CONFIG ---
st.set_page_config(page_title="OCR & Dashboard Tiket", layout="centered")

# --- CACHE RESOURCES ---
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['en', 'id'], gpu=False)

@st.cache_data
def extract_text_from_pdf(pdf_bytes):
    reader = get_ocr_reader()
    texts = []
    pages = convert_from_bytes(pdf_bytes.read(), dpi=300)  # Naikkan dpi

    for page in pages[:5]:
        img = page.convert('RGB')
        img = resize_image(img, max_dim=1600)  # Jangan terlalu kecil
        result = reader.readtext(np.array(img), detail=0)  # Bisa ubah ke detail=1 untuk uji keakuratan
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
    'manual_text': '',
    'parsed_entries_manual': None,
    'parsed_entries_ocr': None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# --- INJECT CSS: MODERN ELEGANT STYLE ---
st.markdown("""
<style>
/* Container */
.block-container {
    max-width: 900px;
    margin: auto;
    padding: 2rem 3rem;
    background-color: #97a0ad;
    color: #2d3748;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

/* Header */
h1, h2, h3 {
    font-family: 'Segoe UI', sans-serif;
    color: #1f2937;
}

/* File uploader and buttons */
.stFileUploader, button[kind="primary"] {
    border-radius: 8px;
    padding: 10px 18px !important;
    font-weight: 600;
}

/* Manual input area: softer background */
textarea {
    background: #eef1f5 !important;
    border: 1px solid #cbd5e1 !important;
    color: #1f2937 !important;
}

/* Data editor container */
section[data-testid="stDataFrameContainer"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
}

/* Image styling */
img {
    border-radius: 8px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(
    """
    <div style='display:flex; align-items:center; gap:12px;'>
      <img src='https://cdn-icons-png.flaticon.com/512/201/201623.png' width='40'/>
      <div>
        <h1 style="margin: 0; font-size: 1.8rem; color: #2d3748;">Dashboard Tiket | Kayyisa Tour</h1>
        <p style="margin: 0; color: #2d3748; font-size: 0.9rem;">Input & Simpan Data Pesanan</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

# --- SECTION: UPLOAD & OCR ---
st.markdown("---")
st.subheader("1. Upload Gambar atau PDF untuk OCR")

file = st.file_uploader("Pilih file gambar (.jpg/.png) atau PDF", type=['jpg','jpeg','png','pdf'])
ocr_text = ''

if file:
    if file.type == 'application/pdf':
        with st.spinner('Mengonversi PDF ke gambar dan menjalankan OCR...'):
            ocr_text = extract_text_from_pdf(file)
    else:
        img = Image.open(file).convert('RGB')
        img = resize_image(img)
        st.image(img, caption='Gambar Terupload', use_column_width=True)
        with st.spinner('Menjalankan OCR...'):
            reader = get_ocr_reader()
            result = reader.readtext(np.array(img), detail=0)
            ocr_text = "\n".join(result)

    # Konfirmasi: file uploader kamera juga menghasilkan tipe image
    st.info('Jika Anda memilih opsi Kamera di daftar Browse File pada HP, file akan diproses di sini.')

    if ocr_text:
        st.text_area('Hasil OCR', ocr_text, height=200)
        if st.button('➡️ Proses Data OCR'):
            try:
                data = process_ocr_unified(ocr_text)
                #for e in data:
                    #e.setdefault('no_invoice','')
                    #e.setdefault('keterangan','')
                    #e.setdefault('pemesan','')
                    #e.setdefault('admin','')
                df_ocr = pd.DataFrame(data)
                st.session_state.parsed_entries_ocr = st.data_editor(df_ocr, use_container_width=True)
            except Exception as ex:
                st.error(f'OCR Processing Error: {ex}')

# --- SECTION: MANUAL INPUT ---
st.markdown("---")
st.subheader("2. Input Data Manual")
manual = st.text_area('Masukkan Teks Manual', value=st.session_state.manual_text, height=200)

col1, col2 = st.columns([1, 1])
with col1:
    if st.button('🔍 Proses Manual'):
        st.session_state.manual_text = manual
        try:
            entries = process_ocr_unified(manual)
            df_man = pd.DataFrame(entries)
            st.session_state.parsed_entries_manual = df_man  # simpan DataFrame saja
        except Exception as err:
            st.error(f'Manual Processing Error: {err}')

with col2:
    if st.button("🧹 Clear Manual"):
        st.session_state.manual_text = ''
        st.session_state.parsed_entries_manual = None
        st.experimental_rerun()

# Tampilkan hanya satu kali dengan key unik
if st.session_state.parsed_entries_manual is not None:
    st.session_state.parsed_entries_manual = st.data_editor(
        st.session_state.parsed_entries_manual,
        use_container_width=True,
        key="parsed_entries_manual_editor"
    )



# --- SECTION: SAVE TO GOOGLE SHEETS ---
st.markdown("---")
st.subheader('3. Simpan ke Google Sheets')

def save_gsheet(df):
    ws = connect_to_gsheet(SHEET_ID, 'Data')
    append_dataframe_to_sheet(df, ws)
    st.success('✅ Berhasil simpan ke Google Sheets')

if st.session_state.parsed_entries_ocr is not None and st.button('📤 Simpan OCR ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_ocr)

if st.session_state.parsed_entries_manual is not None and st.button('📤 Simpan Manual ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_manual)
