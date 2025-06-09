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
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# Inject CSS: Gaya modern yang kontras, bersih dan responsif
st.markdown("""
    <style>
    /* Layout utama */
    .block-container {
        max-width: 900px;
        margin: auto;
        padding: 2rem;
        background-color: #97a0ad;
        color: #2d3748;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Judul halaman */
    h1, h2, h3 {
        color: #2d3748 !important;
    }

    /* Text Area */
    textarea {
        color: #2d3748 !important;
        background-color: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        font-size: 0.95rem;
        padding: 10px;
    }

    /* Data Editor */
    section[data-testid="stDataFrameContainer"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px;
    }

    /* Tombol */
    button[kind="primary"] {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 600;
        margin-top: 10px;
    }

    /* Divider garis */
    hr {
        border: none;
        height: 1px;
        background-color: #e5e7eb;
        margin: 2rem 0;
    }

    /* Image border */
    img {
        border-radius: 8px;
        margin-bottom: 10px;
    }

    /* Responsiveness dan jarak elemen */
    .element-container {
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 1rem;">
        <img src="https://cdn-icons-png.flaticon.com/512/201/201623.png" width="40">
        <div>
            <h1 style="margin: 0; font-size: 1.8rem; color: #2d3748;">Dashboard Tiket | Kayyisa Tour</h1>
            <p style="margin: 0; color: #2d3748; font-size: 0.9rem;">Input & Simpan Data Pesanan</p>
        </div>
    </div>
""", unsafe_allow_html=True)

#st.title("📤 Input Data Kayyisa Tour & Travel")


# --- SECTION: UPLOAD & OCR ---
st.markdown("---")
st.subheader("1. Upload Gambar atau PDF untuk OCR")
file = st.file_uploader("Pilih file gambar (.jpg/.png) atau PDF", type=['jpg','jpeg','png','pdf'])
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
        st.text_area('Hasil OCR', ocr_text, height=200)
        if st.button('➡️ Proses Data OCR'):
            try:
                df_ocr = pd.DataFrame(process_ocr_unified(ocr_text))
                st.dataframe(df_ocr, use_container_width=True)
                st.session_state.parsed_entries_ocr = df_ocr
            except Exception as e:
                st.error(f'OCR Processing Error: {e}')

# --- SECTION: MANUAL INPUT ---
def manual_input_section():
    st.markdown('---')
    st.subheader('2. Input Data Manual')

    # Text area dengan key manual_input_area untuk menyimpan input
    input_text = st.text_area(
        label='Masukkan Teks Manual',
        value=st.session_state.manual_input_area,
        height=200,
        key='manual_input_area'
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button('🔍 Proses Manual'):
            try:
                df_man = pd.DataFrame(process_ocr_unified(input_text))
                st.dataframe(df_man, use_container_width=True)
                st.session_state.parsed_entries_manual = df_man
            except Exception as e:
                st.error(f'Manual Processing Error: {e}')
    with col2:
        if st.button('🧹 Clear Manual'):
            # Reset hanya input area dan hasil parsing
            st.session_state.manual_input_area = ''
            st.session_state.parsed_entries_manual = None

# Panggil fungsi manual_input_section di entry point
if __name__ == '__main__':
    manual_input_section():
    st.markdown('---')
    st.subheader('2. Input Data Manual')

    # Text area dengan key manual_text untuk menyimpan input
    manual_text = st.text_area(
        label='Masukkan Teks Manual',
        value=st.session_state.manual_text,
        height=200,
        key='manual_text'
    )

    # Kolom untuk tombol proses dan clear
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🔍 Proses Manual'):
            try:
                df_man = pd.DataFrame(process_ocr_unified(manual_text))
                st.dataframe(df_man, use_container_width=True)
                st.session_state.parsed_entries_manual = df_man
            except Exception as e:
                st.error(f'Manual Processing Error: {e}')
    with col2:
        if st.button('🧹 Clear Manual'):
            # Reset hanya manual_text dan hasil parsing
            st.session_state.manual_text = ''
            st.session_state.parsed_entries_manual = None

# Panggil fungsi manual_input_section di entry point
if __name__ == '__main__':
    manual_input_section()

# --- SECTION: SAVE TO GOOGLE SHEETS ---
st.markdown('---')
st.subheader('3. Simpan ke Google Sheets')

def save_gsheet(df):
    if not isinstance(df, pd.DataFrame):
        st.warning('Data kosong atau invalid')
        return
    ws = connect_to_gsheet(SHEET_ID, 'Data')
    append_dataframe_to_sheet(df, ws)
    st.success('✅ Berhasil simpan ke Google Sheets')

if st.session_state.parsed_entries_ocr is not None and st.button('📤 Simpan OCR ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_ocr)
if st.session_state.parsed_entries_manual is not None and st.button('📤 Simpan Manual ke GSheet'):
    save_gsheet(st.session_state.parsed_entries_manual)
