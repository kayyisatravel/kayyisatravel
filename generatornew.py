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

def generate_ticket_new(data):
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
    get = lambda k: data.get(k, '-') if data.get(k, '-') else '-'
    tamu_html = "".join(f"<p>{tamu}</p>" for tamu in get('tamu')) if get('tamu') != '-' else "<p>-</p>"

    # Format harga total
    total_harga = "-"
    try:
        total_harga_val = get('harga_per_malam') * get('total_malam') * get('jumlah_kamar')
        total_harga = f"Rp {total_harga_val:,.0f}".replace(',', '.')
    except:
        pass

    html = f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');
      .voucher {{
        width:700px;
        border:2px solid #004080;
        border-radius:10px;
        padding:30px 35px;
        font-family: 'Montserrat', sans-serif;
        background: #f9fbff;
        color: #004080;
        box-shadow: 0 4px 10px rgba(0,64,128,0.1);
      }}
      .header {{
        display:flex;
        align-items:center;
        justify-content: space-between;
        background: linear-gradient(90deg, #e0e8f9, #b3c7f9);
        padding: 10px 20px;
        border-radius: 8px;
        border-bottom: 2px solid #004080;
        margin-bottom: 20px;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
      .header-left {{
        display: flex;
        align-items: center;
        gap: 15px;
      }}
      .header-left img {{
        height: 45px;
        border-radius: 5px;
        border: 1px solid #004080;
        background: white;
      }}
      .header-left h1 {{
        margin: 0;
        font-weight: 700;
        font-size: 25px;
        letter-spacing: 1px;
        white-space: nowrap;
      }}
      .header-right {{
        font-weight: 400;
        font-size: 14px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        align-self: center;
        margin-left: auto;
        text-align: right;
      }}
      .section {{
        margin-top:18px;
      }}
      .section h3 {{
        margin-bottom:10px;
        color:#004080;
        border-bottom: 2px solid #004080;
        padding-bottom: 6px;
        font-weight:700;
        font-size:18px;
        display:flex;
        align-items:center;
        gap:10px;
      }}
      .section p {{
        margin:5px 0;
        font-size: 15px;
      }}
      .footer {{
        margin-top:35px;
        font-size:14px;
        color:#555;
        border-top:1.5px solid #ccc;
        padding-top:15px;
        text-align:center;
        font-style: italic;
      }}
      .icon {{
        width: 20px;
        height: 20px;
        fill: #004080;
      }}
      .price-table {{
        margin-top: 12px;
        border-collapse: collapse;
        width: 100%;
      }}
      .price-table th, .price-table td {{
        border: 1px solid #aac4ff;
        padding: 10px 14px;
        text-align: center;
        vertical-align: middle;
        font-size: 15px;
        color: #003366;
      }}
      .price-table th {{
        background-color: #c6d6ff;
        font-weight: 700;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}

      /* Tambahan untuk cetak */
      @media print {{
        .no-print {{
          display: none !important;
        }}
        .header,
        .price-table th {{
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }}
      }}
    </style>

    <div class="voucher">
      <div class="header">
        <div class="header-left">
          <h1>|Kayyisa Tour & Travel</h1>
        </div>
        <div class="header-right">
          Hotel Reservation
        </div>
      </div>

      <div class="section">
        <h3>Order & Itinerary</h3>
        <p>Order ID: {get('order_id')}<br>
           Itinerary ID: {get('itinerary_id')}</p>
      </div>

      <div class="section">
        <h3>Properti & Lokasi</h3>
        <p>{get('hotel_name')}<br>{get('location')}</p>
      </div>

      <div class="section">
        <h3>Detail Reservasi</h3>
        <p>Jumlah Kamar: {get('jumlah_kamar')}<br>
           Check-in: {get('tanggal_masuk')} – {get('jam_masuk')}<br>
           Check-out: {get('tanggal_keluar')} – {get('jam_keluar')}</p>
      </div>

      <div class="section">
        <h3>Harga</h3>
        <table class="price-table">
          <tr>
            <th>Rate per Malam</th>
            <th>Total Malam</th>
            <th>Jumlah Kamar</th>
            <th>Total Harga</th>
          </tr>
          <tr>
            <td>Rp {get('harga_per_malam'):,.0f}</td>
            <td>{get('total_malam')} malam</td>
            <td>{get('jumlah_kamar')}</td>
            <td><strong>{total_harga}</strong></td>
          </tr>
        </table>
      </div>

      <div class="section">
        <h3>Detail Tamu & Kamar</h3>
        {tamu_html}<br>
        <p>{get('kamar')}</p>
      </div>

      <div class="section">
        <h3>Fasilitas & Permintaan</h3>
        <p>Fasilitas: {get('fasilitas')}<br>
           Permintaan Khusus: {get('permintaan_khusus')}</p>
      </div>

      <div class="footer">
        Jika ada kendala saat check‑in, silakan hubungi kami di: (62813 3671 6677 / kayyisatour@gmail.com)
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

def generate_eticket_pdf(data):
    """
    Fungsi ReportLab Canvas pembuat berkas PDF E-Tiket Kereta Api resmi Kayyisa.
    100% menggunakan arsitektur visual asli Anda, diselaraskan dengan output data AI Gemini 3.1.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Koordinat awal atas kertas
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "E-TIKET KERETA API")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Kode Booking: {data.get('kode_booking', 'N/A')}")
    y -= 20
    # Menyelaraskan key 'tanggal_berangkat' sebagai substitusi 'tanggal' lama agar konsisten
    c.drawString(50, y, f"Tanggal: {data.get('tanggal_berangkat', 'Tidak Diketahui')}")
    y -= 20
    c.drawString(50, y, f"Nama Kereta: {data.get('nama_kereta', 'Tidak Diketahui')}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rute Perjalanan:")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(
        50, 
        y, 
        f"{data.get('asal', 'Tidak Diketahui')} ({data.get('jam_berangkat', '')}) → {data.get('tujuan', 'Tidak Diketahui')} ({data.get('jam_tiba', '')})"
    )
    y -= 40

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Detail Penumpang:")
    y -= 20
    c.setFont("Helvetica", 11)

    # Iterasi daftar array penumpang hasil normalisasi EYD otomatis AI Gemini 3.1
    for p in data.get("penumpang", []):
        c.drawString(60, y, f"- {p.get('nama', '-')} ({p.get('tipe', '-')}), KTP: {p.get('ktp', '-')}, Kursi: {p.get('kursi', '-')}")
        y -= 18
        # Jaring pengaman pendeteksi batas bawah halaman agar tidak menabrak barcode
        if y < 150:  
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 11)

    y -= 30

    # Menghasilkan citra gambar biner barcode PDF417 bawaan sistem Anda dari kode_booking
    barcode_img = generate_pdf417_barcode(data.get('kode_booking', 'KAYYISA'))
    
    # Konversi PIL image hasil generate_pdf417_barcode ke ReportLab ImageReader
    pil_buffer = BytesIO()
    barcode_img.save(pil_buffer, format='PNG')
    pil_buffer.seek(0)
    rl_image = ImageReader(pil_buffer)

    # Menggambar barcode ke canvas PDF secara presisi
    c.drawImage(rl_image, 50, y - 100, width=250, height=80)

    y -= 110
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, "Tunjukkan e-tiket ini dan identitas resmi saat boarding.")

    # Eksekusi tutup canvas halaman dan kembalikan biner objek PDF
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

