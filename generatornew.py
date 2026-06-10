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
# Skema blueprint pendukung di hulu agar otomatis klop dengan fungsi generate_eticket Anda
class PenumpangKeretaSchema(BaseModel):
    nama: str = Field(description="Nama penumpang wajib Title Case (EYD). Bersihkan gelar sapaan.")
    tipe: str = Field(description="Tipe penumpang: Dewasa atau Anak")
    ktp: str = Field(description="Nomor identitas KTP/Paspor. Jika kosong isi 'N/A'")
    kursi: str = Field(description="Nomor kursi spesifik, contoh: 'EKS 5 / 10D' atau 'Kereta 6 / Kursi 8F'")
    qr_placeholder_key: str = Field(description="Penanda urutan gambar: 'qr_penumpang_1', 'qr_penumpang_2', dst.")

class AIKeretaMasterSchema(BaseModel):
    kode_booking: str = Field(description="Kode booking / PNR utama")
    nama_kereta: str = Field(description="Nama kereta api berformat EYD baku. Contoh: 'Serayu' atau 'Ambarawa Ekspres'")
    kelas: str = Field(description="Kelas kereta api, contoh: 'Ekonomi' atau 'Eksekutif'")
    tanggal_berangkat: str = Field(description="Tanggal berangkat indah, cth: 'Selasa, 19 Mei 2026'")
    jam_berangkat: str = Field(description="Jam berangkat format HH.MM atau HH:MM")
    tanggal_tiba: str = Field(description="Tanggal tiba indah, cth: 'Selasa, 19 Mei 2026'")
    jam_tiba: str = Field(description="Jam tiba format HH.MM atau HH:MM")
    asal: str = Field(description="Stasiun asal lengkap + kode, cth: 'Surabaya Gubeng (SGU)' atau 'Halim'")
    tujuan: str = Field(description="Stasiun tujuan lengkap + kode, cth: 'Banyuwangi Kota (BWI)' atau 'Tegalluar'")
    penumpang: List[PenumpangKeretaSchema] = Field(default=[])

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
    """
    Fungsi render HTML E-Tiket Kereta Api bawaan Anda.
    Sudah diselaraskan variabelnya agar membaca data hasil output AI Gemini 3.1.
    """
    # Membaca list 'penumpang' yang dikirim oleh AI
    penumpang_rows = "\n".join([
        f"""
        <tr>
          <td style="text-align: left; padding:8px; border: 1px solid #bbb;">{p.get('nama', '-')}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p.get('tipe', '-')}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p.get('ktp', '-')}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p.get('kursi', '-')}</td>
        </tr>
        """ for p in data.get('penumpang', [])
    ])

    html = f"""
    <style>
      @media print {{
        .no-print {{
          display: none !important;
        }}
        thead {{
          background-color: #cce0ff !important;
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }}
      }}
    </style>

    <div style="font-family: 'Segoe UI'; max-width: 720px; margin: 30px auto; background: #fff; border-radius: 14px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.12); padding: 30px; color: #333;">

      <div style="text-align: center; margin-bottom: 20px;">
        <img src="https://pilihanhidup.com/wp-content/uploads/2024/04/logo-KAI.png" style="width: 120px;"/>
      </div>

      <h1 style="color:#0047b3;">E-Tiket Kereta Api</h1>
      <p><strong>Kode Booking:</strong> {data.get('kode_booking', 'N/A')}<br>
         <strong>Nama Kereta:</strong> {data.get('nama_kereta', 'Tidak Diketahui')}<br>
         <strong>Kelas:</strong> {data.get('kelas', 'Tidak Diketahui')}</p>
         
         <strong>Tanggal Berangkat:</strong> {data.get('tanggal_berangkat', 'Tidak Diketahui')}<br>
         <strong>Tanggal Tiba:</strong> {data.get('tanggal_tiba', 'Tidak Diketahui')}</p>

      <p><strong>Rute:</strong><br>
      {data.get('asal', 'Tidak Diketahui')} <strong>{data.get('jam_berangkat', '')}</strong> → {data.get('tujuan', 'Tidak Diketahui')} <strong>{data.get('jam_tiba', '')}</strong></p>

      <h2 style="border-bottom: 2px solid #0047b3;">Detail Penumpang</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <thead style="background: #cce0ff;">
          <tr>
            <th style="padding: 8px; border: 1px solid #bbb;">Nama</th>
            <th style="padding: 8px; border: 1px solid #bbb;">Tipe</th>
            <th style="padding: 8px; border: 1px solid #bbb;">No Identitas</th>
            <th style="padding: 8px; border: 1px solid #bbb;">Kursi</th>
          </tr>
        </thead>
        <tbody>
          {penumpang_rows}
        </tbody>
      </table>

      <div style="margin-top: 20px; text-align: center;">
        <img src="https://barcode.tec-it.com/barcode.ashx?data={data.get('kode_booking', '')}&code=PDF417"
             style="width: 250px; height: 80px;" />
        <p><strong>Kode Booking:</strong> {data.get('kode_booking', '')}</p>
      </div>

      <div style="text-align: center; margin-top: 30px;">
        <button class="no-print" onclick="window.print()"
                style="padding: 10px 20px; background-color: #0047b3; color: white; border: none;
                       border-radius: 6px; cursor: pointer; font-size: 16px;">
          Cetak Tiket
        </button>
      </div>
    </div>
    """
    return html

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
    
    y = height - 105
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Order & Itinerary")
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(50, y, f"Platform Asal: {data.get('platform', 'Lainnya')}  |  ID Pesanan: {data.get('kode_booking', '-')}")
    
    y -= 25
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Akomodasi & Lokasi")
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0.25, 0.5)
    c.drawString(50, y, f"🏨 {data.get('hotel_name', '-')}")
    
    y -= 14
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, f"Alamat: {data.get('location', '-')}")
    
    y -= 25
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detail Jadwal Menginap")
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(50, y, f"Check-in  : {data.get('tanggal_masuk', '-')} (Jam {data.get('jam_masuk', '-')})")
    
    y -= 14
    c.drawString(50, y, f"Check-out : {data.get('tanggal_keluar', '-')} (Jam {data.get('jam_keluar', '-')})")
    
    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Rincian Pembiayaan Kamar")
    
    y -= 18
    c.setStrokeColorRGB(0.7, 0.8, 0.9)
    c.setFillColorRGB(0.9, 0.94, 1.0)
    c.rect(50, y - 25, width - 100, 25, fill=1, stroke=1)
    
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(120, y - 16, "Rate per Malam")
    c.drawCentredString(230, y - 16, "Durasi")
    c.drawCentredString(340, y - 16, "Jumlah Kamar")
    c.drawCentredString(460, y - 16, "Total Harga")
    
    y -= 25
    c.setFillColorRGB(1, 1, 1)
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
    
    y -= 45
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detail Tamu Menginap & Tipe Kamar")
    c.setFont("Helvetica", 10)
    
    y -= 18
    c.drawString(50, y, f"Kategori Bed : {data.get('tipe_kamar', '-')}")
    
    y -= 14
    c.drawString(50, y, "Daftar Tamu  :")
    
    y -= 14
    for t_idx, nama_tamu in enumerate(data.get('tamu_hotel', []), start=1):
        c.drawString(65, y, f"{t_idx}. {nama_tamu} (EYD Baku)")
        y -= 14
        
    y -= 15
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Fasilitas & Kebijakan Kamar")
    c.setFont("Helvetica", 10)
    
    y -= 18
    c.drawString(50, y, f"Fasilitas Utama    : {data.get('fasilitas_catatan', '-')}")
    
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(50, 70, width - 50, 70)
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(width / 2.0, 52, "Jika ada kendala saat check-in, silakan hubungi layanan darurat 24/7 kami di: (62813 3671 6677 / kayyisatour@gmail.com)")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

