import streamlit as st
from PIL import Image
import easyocr
import numpy as np
import pandas as pd
import PyPDF2
from process_ocr import process_ocr_unified
from sheets_utils import connect_to_gsheet, append_dataframe_to_sheet

# --- SETTINGS ---
st.set_page_config(page_title="OCR & Input Tiket", layout="centered")

# --- CACHING RESOURCES ---
@st.cache_resource
def get_ocr_reader():
    # Initialize EasyOCR reader once
    return easyocr.Reader(['en', 'id'], gpu=False)

@st.cache_data
def extract_text_from_pdf(pdf_bytes):
    # Extract text from uploaded PDF
    text = []
    reader = PyPDF2.PdfReader(pdf_bytes)
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text.append(page_text)
    return "\n".join(text)

# --- UTILITIES ---
def resize_image(image: Image.Image, max_dim=1024) -> Image.Image:
    # Resize image to max dimension for lighter processing
    w, h = image.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_size = (int(w * scale), int(h * scale))
        return image.resize(new_size, Image.ANTIALIAS)
    return image

# --- SESSION STATE INIT ---
for key, default in {
    'manual_text': '',
    'parsed_entries_manual': None,
    'parsed_entries_ocr': None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# --- PAGE STYLING ---
st.markdown("""
<style>
.block-container { max-width: 900px; margin: auto; padding: 2rem; background: #97a0ad; }
button[kind="primary"] { border-radius: 6px; padding: 10px 20px; }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(
    """
    <div style='display:flex; align-items:center; gap:10px;'>
      <img src='https://cdn-icons-png.flaticon.com/512/201/201623.png' width='40'/>
      <h1 style='margin:0;'>Dashboard Tiket | Kayyisa Tour</h1>
    </div>
    """, unsafe_allow_html=True)

# --- INPUT SECTION ---
st.markdown("---")
st.subheader("1. Upload / Camera / PDF Input")

# File uploader (image/pdf) or camera
col1, col2 = st.columns(2)
with col1:
    file = st.file_uploader("Upload Gambar (.jpg,.jpeg,.png) atau PDF", type=['jpg','jpeg','png','pdf'])
with col2:
    camera_img = st.camera_input("Atau ambil foto langsung")

ocr_text = ''

if file is not None:
    if file.type == 'application/pdf':
        with st.spinner("Membaca PDF..."):
            ocr_text = extract_text_from_pdf(file)
    else:
        image = Image.open(file).convert("RGB")
        image = resize_image(image)
        st.image(image, caption="Gambar Terupload", use_column_width=True)
        with st.spinner("Menjalankan OCR pada gambar..."):
            reader = get_ocr_reader()
            result = reader.readtext(np.array(image), detail=0)
            ocr_text = "\n".join(result)

elif camera_img is not None:
    image = Image.open(camera_img).convert("RGB")
    image = resize_image(image)
    st.image(image, caption="Foto Kamera", use_column_width=True)
    with st.spinner("Menjalankan OCR pada foto..."):
        reader = get_ocr_reader()
        result = reader.readtext(np.array(image), detail=0)
        ocr_text = "\n".join(result)

# Show OCR result
if ocr_text:
    st.text_area("Hasil OCR", ocr_text, height=200)
    if st.button("Proses Data dari OCR"):
        try:
            data_entries = process_ocr_unified(ocr_text)
            for entry in data_entries:
                entry.setdefault('no_invoice','')
                entry.setdefault('keterangan','')
                entry.setdefault('pemesan','')
                entry.setdefault('admin','')
            df_ocr = pd.DataFrame(data_entries)
            st.session_state.parsed_entries_ocr = st.data_editor(df_ocr, use_container_width=True)
        except Exception as e:
            st.error(f"OCR Processing Error: {e}")

# --- MANUAL INPUT ---
st.markdown("---")
st.subheader("2. Input Manual")
manual_input = st.text_area("Masukkan Teks Manual (Email/Tiket)", value=st.session_state.manual_text, height=200)
if st.button("Proses Manual"):
    st.session_state.manual_text = manual_input
    try:
        entries = process_ocr_unified(manual_input)
        for entry in entries:
            entry.setdefault('no_invoice','')
            entry.setdefault('keterangan','')
            entry.setdefault('pemesan','')
            entry.setdefault('admin','')
        df_manual = pd.DataFrame(entries)
        st.session_state.parsed_entries_manual = st.data_editor(df_manual, use_container_width=True)
    except Exception as e:
        st.error(f"Manual Processing Error: {e}")

# --- SAVE SECTION ---
st.markdown("---")
st.subheader("3. Simpan ke Google Sheets")
def save_to_gsheet(df):
    ws = connect_to_gsheet(SHEET_ID, 'Data')
    append_dataframe_to_sheet(df, ws)
    st.success("Berhasil simpan ke Google Sheets")

if st.session_state.parsed_entries_ocr is not None:
    if st.button("Simpan OCR ke GSheet"):
        save_to_gsheet(st.session_state.parsed_entries_ocr)

if st.session_state.parsed_entries_manual is not None:
    if st.button("Simpan Manual ke GSheet"):
        save_to_gsheet(st.session_state.parsed_entries_manual)
