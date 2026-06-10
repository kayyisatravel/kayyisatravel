import json
import re
import string
from io import BytesIO
from datetime import datetime
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import pdf417gen

# =====================================================================
# 1. SKEMA DATA STRUKTUR UTAMA PYDANTIC UNTUK GEMINI 3.1
# =====================================================================
class PenumpangTiket(BaseModel):
    nama: str = Field(description="""
        Wajib ubah nama menjadi format Title Case / Huruf Kapital di Awal Kata (EYD Baku). 
        Hapus total gelar sapaan maskapai/OTA seperti 'Tuan', 'Nyonya', 'Nona', 'Tn', 'Ny', 'Mr', 'Mrs', 'Ms'.
        Contoh: 'Tuan Novan Wibowo' -> 'Novan Wibowo'.
        Contoh: 'NYONYA EVA NATALIA' -> 'Eva Natalia'.
    """)
    tipe: str = Field(description="Tipe kategori penumpang: 'Dewasa' atau 'Anak'")
    ktp: str = Field(description="Nomor NIK/KTP/Paspor penumpang. Jika tidak ditemukan, isi 'N/A'")
    kursi: str = Field(description="Nomor kursi spesifik. Contoh KAI: 'EKS 5 / 10D', Contoh Whoosh: 'Kereta 6 / Kursi 8F'")
    qr_placeholder_key: str = Field(description="String tegas penanda urutan: 'qr_penumpang_1', 'qr_penumpang_2', 'qr_penumpang_3', dst.")

class AIKayyisaMasterSchema(BaseModel):
    platform: str = Field(description="Sumber OTA asal, cth: 'Tiket.com', 'Traveloka', 'Access by KAI'")
    tipe_dokumen: str = Field(description="Wajib deteksi jenis dokumen secara tegas: 'Kereta', 'Whoosh', atau 'Hotel'")
    kode_booking: str = Field(description="Kode booking, PNR, atau ID Pesanan utama vendor. Jika tidak ada isi 'N/A'")
    
    # Atribut Transportasi (KAI & Whoosh)
    nama_armada: Optional[str] = Field(default="Tidak Diketahui", description="Format EYD baku. Cth: 'Ambarawa Ekspres', 'Serayu', atau 'Whoosh G1031'")
    kelas_armada: Optional[str] = Field(default="Tidak Diketahui", description="Cth: 'Ekonomi Premium', 'Eksekutif'")
    tanggal_berangkat: Optional[str] = Field(default="-", description="Format tanggal indah dibaca, cth: 'Kam, 12 Feb 2026'")
    jam_berangkat: Optional[str] = Field(default="", description="Format jam HH:MM")
    tanggal_tiba: Optional[str] = Field(default="-", description="Format tanggal indah dibaca, cth: 'Kam, 12 Feb 2026'")
    jam_tiba: Optional[str] = Field(default="", description="Format jam HH:MM")
    stasiun_asal: Optional[str] = Field(default="-", description="Nama stasiun asal + kode, cth: 'Semarang Tawang (SMT)' atau 'Halim'")
    stasiun_tujuan: Optional[str] = Field(default="-", description="Nama stasiun tujuan + kode, cth: 'Surabaya Pasarturi (SBI)' atau 'Tegalluar Summarecon'")
    daftar_penumpang: List[PenumpangTiket] = Field(default=[])

    # Atribut Akomodasi (Voucher Hotel)
    hotel_name: Optional[str] = Field(default="-", description="Format EYD baku. Cth: 'Paus Homestay Syariah' atau 'Hotel Ambun Suri'")
    location: Optional[str] = Field(default="-", description="Alamat lengkap akomodasi")
    jumlah_kamar: Optional[int] = Field(default=1)
    total_malam: Optional[int] = Field(default=1, description="AI wajib menghitung selisih hari check-in & check-out secara presisi sebagai integer murni")
    harga_per_malam: Optional[float] = Field(default=0.0, description="Angka nominal murni tanpa Rp atau tanda titik")
    tamu_hotel: List[str] = Field(default=[], description="Daftar nama tamu kamar berformat EYD baku tanpa gelar sapaan")
    tipe_kamar: Optional[str] = Field(default="-")
    fasilitas_catatan: Optional[str] = Field(default="-", description="Info sarapan, non-smoking room, dll")

# =====================================================================
# 2. ENGINE PARSER UTAMA BERBASIS AI GEMINI 3.1 FLASH LITE
# =====================================================================
def panggil_ai_ticket_parser(text_block: str, tipe_tiket_pilihan: str) -> dict:
    """Membaca teks manifes OTA berantakan menjadi data berstruktur EYD baku via Gemini 3.1 Flash Lite"""
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        prompt = f"""
        Kamu adalah sistem AI Parser Dokumen Keuangan milik Kayyisa Tour & Travel.
        Kategori Dokumen Target: {tipe_tiket_pilihan.upper()}.
        
        Tugasmu adalah membedah teks input kasar hasil salinan OTA berikut menjadi format JSON terstruktur yang mematuhi skema Pydantic secara mutlak.
        Pastikan pembersihan gelar sapaan dan konversi ejaan EYD baku (Title Case) dijalankan langsung di internal core kamu.
        
        Teks Input Kasar:
        {text_block}
        """
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIKayyisaMasterSchema,
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gagal memproses data melalui AI Gemini 3.1: {e}")
        return {}

# =====================================================================
# 3. LOGIKA RENDER PDF DENGAN LOGIKA MULTI-QR DYNAMIC (REPORTLAB)
# =====================================================================
def generate_pdf417_barcode(data_str):
    codes = pdf417gen.encode(data_str, columns=6, security_level=2)
    return pdf417gen.render_image(codes, scale=3, ratio=3)

def generate_eticket_pdf_new(data):
    """Fungsi Canvas pembuat PDF E-Tiket Kereta Api / Whoosh versi AI terbaru"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Banner Navy Blue Atas
    c.setFillColorRGB(0, 0.25, 0.5)
    c.rect(40, height - 70, width - 80, 40, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 13)
    
    label_title = "E-TIKET WHOOSH" if data.get('tipe_dokumen') == "Whoosh" else "E-TIKET KERETA API"
    c.drawString(55, height - 53, f"KAYYISA TOUR & TRAVEL  |  {label_title}")

    # Data Utama Manifes Perjalanan
    y = height - 105
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, f"Kode Booking: {data.get('kode_booking', 'N/A')}")
    
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(50, y, f"Nama Armada: {data.get('nama_armada', '-')} ({data.get('kelas_armada', '-')})")
    y -= 14
    c.drawString(50, y, f"Rute Perjalanan: {data.get('stasiun_asal', '-')} ➔ {data.get('stasiun_tujuan', '-')}")
    y -= 14
    c.drawString(50, y, f"Waktu Berangkat: {data.get('tanggal_berangkat', '-')} pukul {data.get('jam_berangkat', '-')}")
    y -= 14
    c.drawString(50, y, f"Estimasi Tiba: {data.get('tanggal_tiba', '-')} pukul {data.get('jam_tiba', '-')}")
    
    # Garis Pembatas
    y -= 15
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(50, y, width - 50, y)
    
    # Judul Tabel Penumpang
    y -= 25
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detail Penumpang & Posisi Kursi:")
    
    # Header Tabel Visual
    y -= 20
    c.setStrokeColorRGB(0, 0.25, 0.5)
    c.setFillColorRGB(0.88, 0.93, 1.0) 
    c.rect(50, y - 22, width - 100, 22, fill=1, stroke=0)
    
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(60, y - 14, "Nama Penumpang (Sesuai EYD)")
    c.drawString(240, y - 14, "Tipe")
    c.drawString(310, y - 14, "No. Identitas")
    c.drawString(420, y - 14, "Kursi")
    if data.get('tipe_dokumen') == "Whoosh":
        c.drawString(505, y - 14, "QR Code Gate")
        
    y -= 22
    c.setFont("Helvetica", 9)
    
    # LOOPING DINAMIS: Mendukung berapapun jumlah penumpang (Multi-Baris)
    for p in data.get("daftar_penumpang", []):
        if y < 130:
            c.showPage()
            y = height - 80
            c.setFont("Helvetica", 9)
            
        c.drawString(60, y - 16, str(p.get('nama', '-')))
        c.drawString(240, y - 16, str(p.get('tipe', '-')))
        c.drawString(310, y - 16, str(p.get('ktp', '-')))
        c.drawString(420, y - 16, str(p.get('kursi', '-')))
        
        # Penanganan khusus penempelan gambar QR Code asli Whoosh
        if data.get('tipe_dokumen') == "Whoosh":
            key_qr = p.get('qr_placeholder_key')
            file_gambar_qr = st.session_state.get(key_qr)
            if file_gambar_qr:
                rl_image = ImageReader(file_gambar_qr)
                c.drawImage(rl_image, 505, y - 45, width=45, height=45)
                c.setStrokeColorRGB(0.85, 0.85, 0.85)
                c.line(50, y - 50, width - 50, y - 50)
                y -= 50
            else:
                c.drawString(505, y - 16, "[Belum Diupload]")
                c.setStrokeColorRGB(0.85, 0.85, 0.85)
                c.line(50, y - 25, width - 50, y - 25)
                y -= 25
        else:
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.line(50, y - 25, width - 50, y - 25)
            y -= 25

    # Cetak Barcode PDF417 Global untuk KAI biasa
    if data.get('tipe_dokumen') == "Kereta":
        y -= 40
        if y < 120:
            c.showPage()
            y = height - 100
        kode_b = data.get('kode_booking', 'KAYYISA')
        barcode_img = generate_pdf417_barcode(kode_b)
        pil_buf = BytesIO()
        barcode_img.save(pil_buf, format='PNG')
        pil_buf.seek(0)
        c.drawImage(ImageReader(pil_buf), 50, y - 60, width=200, height=60)
        y -= 75
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, f"Kode Booking Boarding: {kode_b}")

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(50, 45, "*Mohon siapkan dokumen identitas fisik asli yang sesuai saat boarding di stasiun.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_evoucher_pdf_new(data):
    """Fungsi pembuat berkas PDF E-Voucher Hotel versi AI terbaru"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    c.setFillColorRGB(0, 0.25, 0.5)
    c.rect(40, height - 70, width - 80, 40, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(55, height - 54, "| Kayyisa Tour & Travel")
    c.setFont("Helvetica", 11)
    c.drawRightString(width - 55, height - 53, "HOTEL RESERVATION VOUCHER")
    
    y = height - 105c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Order & Itinerary")
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(50, y, f"Platform Asal: {data.get('platform', 'Lainnya')}  |  ID Pesanan: {data.get('kode_booking', '-')}")
    y -= 25c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Akomodasi & Lokasi")y -= 18c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0.25, 0.5)
    c.drawString(50, y, f"🏨 {data.get('hotel_name', '-')}")
    y -= 14c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, f"Alamat: {data.get('location', '-')}")
    y -= 25c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detail Jadwal Menginap")
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(50, y, f"Check-in  : {data.get('tanggal_masuk', '-')} (Jam {data.get('jam_masuk', '-')})")
    y -= 14c.drawString(50, y, f"Check-out : {data.get('tanggal_keluar', '-')} (Jam {data.get('jam_keluar', '-')})")
    y -= 30c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Rincian Pembiayaan Kamar")
    y -= 18c.setStrokeColorRGB(0.7, 0.8, 0.9)c.setFillColorRGB(0.9, 0.94, 1.0)
    c.rect(50, y - 25, width - 100, 25, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(120, y - 16, "Rate per Malam")
    c.drawCentredString(230, y - 16, "Durasi")
    c.drawCentredString(340, y - 16, "Jumlah Kamar")
    c.drawCentredString(460, y - 16, "Total Harga")
    y -= 25c.setFillColorRGB(1, 1, 1)
    c.rect(50, y - 25, width - 100, 25, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    hrg_malam = data.get('harga_per_malam', 0.0)
    tot_malam = data.get('total_malam', 1)
    jml_kamar = data.get('jumlah_kamar', 1)
    total_gross = hrg_malam * tot_malam * jml_kamar
    c.drawCentredString(110, y - 17, f"Rp {hrg_malam:,.0f}".replace(',', '.'))
    c.drawCentredString(230, y - 17, f"{tot_malam} Malam")
    c.drawCentredString(340, y - 17, f"{jml_kamar} Kamar")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(460, y - 17, f"Rp {total_gross:,.0f}".replace(',', '.'))
    y -= 45c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detail Tamu Menginap & Tipe Kamar")
    c.setFont("Helvetica", 10)
    y -= 18c.drawString(50, y, f"Kategori Bed : {data.get('tipe_kamar', '-')}")
    y -= 14c.drawString(50, y, "Daftar Tamu  :")
    y -= 14
    for t_idx, nama_tamu in enumerate(data.get('tamu_hotel', []), start=1):
        c.drawString(65, y, f"{t_idx}. {nama_tamu} (EYD Baku)")
        y -= 14y -= 15
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Fasilitas & Kebijakan Kamar")
        c.setFont("Helvetica", 10)
        y -= 18c.drawString(50, y, f"Fasilitas Utama    : {data.get('fasilitas_catatan', '-')}")
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.line(50, 70, width - 50, 70)
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawCentredString(width / 2.0, 52, "Jika ada kendala saat check-in, silakan hubungi layanan darurat 24/7 kami di: (62813 3671 6677 / kayyisatour@gmail.com)")
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer
