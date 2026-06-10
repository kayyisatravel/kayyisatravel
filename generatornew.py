import json
import re  
import string  
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# =====================================================================
# 1. BLUEPRINT PYDANTIC SCHEMA (DISELARASKAN DENGAN KAMUS DATA LAMA ANDA)
# =====================================================================

class PenumpangKeretaSchema(BaseModel):
    nama: str = Field(description="""
        Nama lengkap penumpang wajib diubah ke format Title Case / Huruf Kapital di Awal Kata (EYD Baku). 
        Wajib hapus total gelar sapaan maskapai atau OTA seperti 'Tuan', 'Nyonya', 'Nona', 'Tn', 'Ny', 'Mr', 'Mrs', 'Ms' jika ada.
        Contoh input: 'NYONYA Amiliya Duwi Setiyowati' -> Hasil: 'Amiliya Duwi Setiyowati'.
        Contoh input: 'Tuan Novan Wibowo' -> Hasil: 'Novan Wibowo'.
    """)
    tipe: str = Field(description="Tipe penumpang, contoh: 'Dewasa' atau 'Anak'")
    ktp: str = Field(description="Nomor identitas / NIK / KTP / Paspor penumpang. Jika tidak ada isi 'N/A'")
    kursi: str = Field(description="""
        Nomor posisi kursi spesifik, contoh: 'EKS 5/10D' atau 'Kereta 6 / Kursi 8F.
        Contoh teks: 'EKO-3/ 19-E' -> Maka isi field kursi wajib: 'EKO 3/19E'.
        Contoh teks: 'Eksekutif 2 / 5A' -> Maka isi field kursi wajib: 'EKS 2/5A'.
    qr_placeholder_key: str = Field(description="Penanda urutan gambar khusus Whoosh: 'qr_penumpang_1', 'qr_penumpang_2', dst.")

class AIKeretaMasterSchema(BaseModel):
    kode_booking: str = Field(description="Kode booking / PNR / ID Pesanan utama dari vendor")
    tanggal: str = Field(description="Tanggal keberangkatan format indah dibaca manusia, contoh: '12 Feb 2026' atau '19 Mei 2026'")
    tanggal_berangkat: str = Field(description="Samakan nilainya dengan field 'tanggal'")
    jam_berangkat: str = Field(description="Jam keberangkatan format HH:MM atau HH.MM")
    tanggal_tiba: str = Field(description="Tanggal tiba di stasiun tujuan format indah dibaca manusia, contoh: '12 Feb 2026'")
    jam_tiba: str = Field(description="Jam tiba di stasiun tujuan format HH:MM atau HH.MM")
    asal: str = Field(description="Nama stasiun asal lengkap beserta kode stasiunnya di dalam kurung, contoh: 'Semarang Tawang (SMT)' atau 'Halim'")
    tujuan: str = Field(description="Nama stasiun tujuan lengkap beserta kode stasiunnya di dalam kurung, contoh: 'Surabaya Pasarturi (SBI)' atau 'Tegalluar'")
    nama_kereta: str = Field(description="Nama armada kereta api berformat EYD baku (Title Case) tanpa nomor seri di belakangnya, contoh: 'Ambarawa Ekspres' atau 'Serayu'")
    kelas: str = Field(description="Kelas kategori kereta api berformat Title Case, contoh: 'Ekonomi' atau 'Eksekutif'")
    penumpang: List[PenumpangKeretaSchema] = Field(default=[], description="Daftar array manifes seluruh penumpang")


class AIHotelMasterSchema(BaseModel):
    order_id: str = Field(description="ID Pesanan / Order ID dari platform OTA")
    itinerary_id: str = Field(description="ID Itinerary, jika tidak ada di teks isi dengan '-'")
    hotel_name: str = Field(description="Nama hotel lengkap berformat EYD baku / Title Case, contoh: 'Hotel Ambun Suri'")
    location: str = Field(description="Alamat lengkap, jalan, kecamatan, kota, dan provinsi lokasi hotel")
    jumlah_kamar: int = Field(description="Jumlah total kamar yang dipesan sebagai Integer murni")
    tanggal_masuk: str = Field(description="Tanggal Check-in format indah dibaca, contoh: 'Sel, 09 Jun 2026'")
    jam_masuk: str = Field(description="Waktu jam check-in akomodasi, contoh: '14:00-23:59'")
    tanggal_keluar: str = Field(description="Tanggal Check-out format indah dibaca, contoh: 'Rab, 10 Jun 2026'")
    jam_keluar: str = Field(description="Waktu jam check-out akomodasi, contoh: '12:00'")
    harga_per_malam: float = Field(description="Tarif harga per malam per kamar sebagai angka murni/Float")
    total_malam: int = Field(description="AI wajib menghitung selisih hari check-in & check-out secara presisi sebagai Integer murni")
    tamu: List[str] = Field(default=[], description="Daftar nama-nama tamu menginap berformat EYD baku / Title Case tanpa gelar sapaan")
    kamar: str = Field(description="Tipe/Kategori kamar hotel lengkap, contoh: 'Kamar Standard Twin dengan Kipas (Standard Room with Fan)'")
    fasilitas: str = Field(description="Fasilitas makan atau utama, contoh: 'Sarapan (2 Pax) per kamar' atau 'Wifi'")
    permintaan_khusus: str = Field(description="Catatan permintaan khusus tamu, contoh: 'Non Smoking room, King Bed'")
    hotel_phone: Optional[str] = Field(default="-", description="""
        Gunakan fitur pencarian internet (Google Search) untuk melacak nomor telepon resmi, 
        nomor HP layanan, atau kontak resepsionis aktif dari properti hotel ini berdasarkan nama hotel 
        dan alamat lokasi di atas. Kembalikan hasilnya dalam format string bersih, contoh: '+6285265575009'. 
        Jika setelah dicari di internet tetap tidak ditemukan, isi dengan tanda strip '-'.
    """)
    kamar: str = Field(description="""
        PENTING: Salin Nama Kamar atau Tipe Kamar secara UTUH dan LENGKAP persis seperti teks yang tertera pada manifes vendor/OTA.
        JANGAN memotong kata imbuhan di belakangnya seperti '- Free Breakfast', 'with Fan', atau 'Room Only'.
        Contoh teks: '1 Standard - Free Breakfast' -> Maka isi field kamar wajib: 'Standard - Free Breakfast'.
        Contoh teks: 'SUPERIOR KING BED - Room Only' -> Maka isi field kamar wajib: 'SUPERIOR KING BED - Room Only'.
        Tidak perlu menambahkan 'Kamar'. 
        Contoh teks: 'KAMAR SUPERIOR KING BED - Room Only' -> Maka isi field kamar wajib: 'SUPERIOR KING BED - Room Only'.
        Contoh teks: '1 Kamar Standard - Free Breakfast' -> Maka isi field kamar wajib: 'Standard - Free Breakfast'.
    """)
    


# =====================================================================
# 2. FUNGSI PARSER KECERDASAN BUATAN GEMINI 3.1 FLASH-LITE
# =====================================================================

def parse_input_dynamic(text):
    """
    JALUR AI TRANSPORTASI: Menggantikan fungsi regex lama Anda.
    Membaca teks manifes Kereta Api & Whoosh secara akurat dengan Gemini 3.1 Flash-Lite.
    """
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        prompt = f"""
        Kamu adalah sistem AI Parser Kereta Api milik Kayyisa Tour & Travel.
        Tugasmu mengekstrak teks input kasar hasil copas OTA menjadi format JSON terstruktur yang mematuhi skema secara mutlak.
        Konversi ejaan nama dan armada ke EYD Baku (Title Case) serta pembersihan gelar wajib dilakukan di internal kamu.
        
        Teks Input Kasar:
        {text}
        """
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIKeretaMasterSchema,
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Kereta Error: {e}")
        return {}


def parse_evoucher_text(text):
    """
    JALUR AI AKOMODASI: Menggantikan fungsi baris lama Anda.
    Membaca teks manifes Voucher Hotel secara akurat dengan Gemini 3.1 Flash-Lite.
    """
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        prompt = f"""
        Kamu adalah sistem AI Parser Hotel milik Kayyisa Tour & Travel.
        Tugasmu mengekstrak teks input kasar hasil copas OTA menjadi format JSON terstruktur yang mematuhi skema secara mutlak.
        Hitung total malam menginap secara matematis dan bersihkan nama tamu sesuai kaidah EYD baku.
        
        Teks Input Kasar:
        {text}
        """
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIHotelMasterSchema,
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Hotel Error: {e}")
        return {}


def generate_eticket(data):
    penumpang_rows = "\n".join([
        f"""
        <tr>
          <td style="text-align: left; padding:8px; border: 1px solid #bbb;">{p['nama']}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p['tipe']}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p['ktp']}</td>
          <td style="text-align: center; padding:8px; border: 1px solid #bbb;">{p['kursi']}</td>
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

    
# Fungsi generate HTML voucher (disesuaikan dari kode kamu)
def generate_evoucher_html(data):
    get = lambda k: data.get(k, '-') if data.get(k, '-') else '-'
    
    # 1. PERBAIKAN: Penomoran angka otomatis pada daftar tamu
    tamu_list = data.get('tamu', [])
    if tamu_list and tamu_list != '-':
        tamu_html = "".join(f"<p>{idx}. {tamu}</p>" for idx, tamu in enumerate(tamu_list, start=1))
    else:
        tamu_html = "<p>-</p>"

    # Format hitungan angka harga total
    try:
        hrg_per_malam = float(data.get('harga_per_malam', 0))
        tot_malam = int(data.get('total_malam', 1))
        jml_kamar = int(data.get('jumlah_kamar', 1))
    except (ValueError, TypeError):
        hrg_per_malam = 0.0
        tot_malam = 1
        jml_kamar = 1

    total_harga = "-"
    try:
        total_harga_val = hrg_per_malam * tot_malam * jml_kamar
        total_harga = f"Rp {total_harga_val:,.0f}".replace(',', '.')
    except:
        pass

    # =====================================================================
    # 2. PERBAIKAN: Menggabungkan jumlah kamar dan nama kamar secara lengkap
    # =====================================================================
    nama_kamar_raw = get('kamar')
    teks_kamar_final = f"{jml_kamar} x Kamar {nama_kamar_raw}"

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
        <p><strong>{get('hotel_name')}</strong><br>
           {get('location')}<br>
           <strong>📞 Kontak Hotel:</strong> {get('hotel_phone')}
        </p>
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
        <strong>{tamu_html}</strong><br>
        <p>{teks_kamar_final}</p>
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



# ===== Contoh pemakaian =====

if __name__ == "__main__":
    contoh_input = """
Kode booking: 75L8DMJ
Min, 06 Jul 2025 - 22:50

Surabaya Gubeng (SGU) - Surabaya

Blambangan Ekspres

Eksekutif (AC) 05j 35m

Sen, 07 Jul 2025 - 04:25

Banyuwangi Kota (BWI) - Banyuwangi

Penumpang & Fasilitas

1. NYONYA Amiliya Duwi Setiyowati

Dewasa

Nomor Identitas: 3522096901030005

SGU - BWI

Kursi EKS 5/10D
"""

    data = parse_input_new_format(contoh_input)
    html = generate_eticket(data)
    print(html)

# =========================
# GENERATE PDF E-TIKET
# =========================

def generate_pdf417_barcode(data):
    codes = pdf417gen.encode(data, columns=6, security_level=2)
    image = pdf417gen.render_image(codes, scale=3, ratio=3)
    return image

def generate_eticket_pdf(data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "E-TIKET KERETA API")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Kode Booking: {data['kode_booking']}")
    y -= 20
    c.drawString(50, y, f"Tanggal: {data['tanggal']}")
    y -= 20
    c.drawString(50, y, f"Nama Kereta: {data['nama_kereta']}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rute Perjalanan:")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"{data['asal']} ({data['jam_berangkat']}) → {data['tujuan']} ({data['jam_tiba']})")
    y -= 40

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Detail Penumpang:")
    y -= 20
    c.setFont("Helvetica", 11)

    for p in data["penumpang"]:
        c.drawString(60, y, f"- {p['nama']} ({p['tipe']}), KTP: {p['ktp']}, Kursi: {p['kursi']}")
        y -= 18
        if y < 150:  # avoid overflow for barcode
            c.showPage()
            y = height - 50

    y -= 30

    # Generate barcode image from kode_booking
    barcode_img = generate_pdf417_barcode(data['kode_booking'])
    
    # Convert PIL image to ReportLab ImageReader
    pil_buffer = BytesIO()
    barcode_img.save(pil_buffer, format='PNG')
    pil_buffer.seek(0)
    rl_image = ImageReader(pil_buffer)

    # Draw barcode image
    c.drawImage(rl_image, 50, y - 100, width=250, height=80)

    y -= 110
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, "Tunjukkan e-tiket ini dan identitas resmi saat boarding.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
