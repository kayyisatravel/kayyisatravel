import streamlit as st
from PIL import Image
import easyocr
import numpy as np
#import pytesseract
import pandas as pd
from process_ocr import process_ocr_unified
from sheets_utils import connect_to_gsheet, append_dataframe_to_sheet

# --- SETUP TESSERACT ---
#pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
reader = easyocr.Reader(['en', 'id'])

SHEET_ID = "1idBV7qmL7KzEMUZB6Fl31ZeH5h7iurhy3QeO4aWYON8"

# --- PAGE SETTINGS ---
st.set_page_config(page_title="OCR & Input Tiket", layout="centered")
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

# --- SESSION STATE INIT ---
if "manual_text" not in st.session_state:
    st.session_state.manual_text = ""

if "parsed_entries_manual" not in st.session_state:
    st.session_state.parsed_entries_manual = None

if "parsed_entries_ocr" not in st.session_state:
    st.session_state.parsed_entries_ocr = None

# ---------------------------
# 📷 UPLOAD DAN OCR GAMBAR
# ---------------------------
#st.markdown('<h3 style="margin-top:2rem; font-size:1.2rem; color:#1f2937;">📷 Upload Gambar Tiket</h3>', unsafe_allow_html=True)

st.markdown('<label style="font-size: 1rem; color: #1f2937; font-weight: 500;">📎 Upload Gambar Tiket (.jpg, .jpeg, .png)</label>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], label_visibility="collapsed")


if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="📸 Gambar Terupload", use_column_width=True)

    with st.spinner("🔍 Menjalankan OCR..."):
        # Convert ke numpy array
        img_array = np.array(image.convert("RGB"))
        # Jalankan EasyOCR
        result = reader.readtext(img_array, detail=0)
        ocr_text = "\n".join(result)

    st.text_area("📄 Hasil OCR", ocr_text, height=200)

    if st.button("➡️ Proses Data dari OCR"):
        data_entries = process_ocr_unified(ocr_text)
        for entry in data_entries:
            entry.setdefault("no_invoice", "")
            entry.setdefault("keterangan", "")
            entry.setdefault("pemesan", "")
            entry.setdefault("admin", "")
        df_ocr = pd.DataFrame(data_entries)
        st.session_state.parsed_entries_ocr = st.data_editor(df_ocr, use_container_width=True, num_rows="dynamic")

# ---------------------------
# ✏️ INPUT MANUAL
# ---------------------------
st.markdown("---")
st.markdown('<h3 style="margin-top:2rem; font-size:1.2rem; color:#1f2937;">✏️ Input Manual (Copy-Paste Email)</h3>', unsafe_allow_html=True)

if "manual_text" not in st.session_state:
    st.session_state.manual_text = ""

if "reset_input_manual" not in st.session_state:
    st.session_state.reset_input_manual = False

col1, col2 = st.columns([3, 1])
with col1:
    key_textarea = "input_manual_reset" if st.session_state.reset_input_manual else "input_manual"
    manual_input = st.text_area(
        "Masukkan Teks",
        value="" if st.session_state.reset_input_manual else st.session_state.manual_text,
        key=key_textarea,
        height=200
    )
    st.session_state.reset_input_manual = False  # reset flag setelah render
with col2:
    if st.button("🧹 Clear"):
        st.session_state.manual_text = ""
        st.session_state.reset_input_manual = True
        st.rerun()


# Tombol "Enter"
if st.button("🔎 Proses (Enter)"):
    st.session_state.manual_text = manual_input  # simpan agar bisa dipanggil ulang
    entries = process_ocr_unified(manual_input)
    for entry in entries:
        entry.setdefault("no_invoice", "")
        entry.setdefault("keterangan", "")
        entry.setdefault("pemesan", "")
        entry.setdefault("admin", "")
    df_manual = pd.DataFrame(entries)
    st.session_state.parsed_entries_manual = st.data_editor(df_manual, use_container_width=True, num_rows="dynamic")

# ---------------------------
# 💾 SIMPAN KE CSV & GSheets
# ---------------------------
st.markdown("---")
st.markdown('<h3 style="margin-top:2rem; font-size:1.2rem; color:#1f2937;">💾 Simpan Data</h3>', unsafe_allow_html=True)

def save_to_gsheet(df):
    try:
        ws = connect_to_gsheet(SHEET_ID, "Data")
        append_dataframe_to_sheet(df, ws)
        st.success("✅ Berhasil simpan ke Google Sheets")
    except Exception as e:
        st.error(f"❌ Gagal simpan ke Google Sheets: {e}")

# Tombol untuk OCR
if st.session_state.parsed_entries_ocr is not None:
    if st.button("📤 Simpan OCR ke GSheet"):
        save_to_gsheet(st.session_state.parsed_entries_ocr)

# Tombol untuk Manual
if st.session_state.parsed_entries_manual is not None:
    if st.button("📤 Simpan Manual ke GSheet"):
        save_to_gsheet(st.session_state.parsed_entries_manual)


