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
        Nomor posisi kursi spesifik. Wajib lakukan penyingkatan format secara ketat jika mendeteksi tiket Whoosh.
        Aturan Penyingkatan Whoosh:
        - Teks format 'Ekonomi Premium / Kereta [X] / Kursi [Y]' WAJIB dikonversi menjadi 'Eko Pre [X]/[Y]'.
        - Contoh input: 'Ekonomi Premium / Kereta 6 / Kursi 8F' -> Hasil output wajib: 'Eko Pre 6/8F'.
        - Contoh input: 'Ekonomi Premium / Kereta 6 / Kursi 9F' -> Hasil output wajib: 'Eko Pre 6/9F'.
        Aturan Penyingkatan KAI Biasa:
        - Contoh teks: 'EKO-3/ 19-E' -> Hasil output wajib: 'EKO 3/19E'.
        - Contoh teks: 'Eksekutif 2 / 5A' -> Hasil output wajib: 'EKS 2/5A'.
    """)
    qr_placeholder_key: str = Field(description="Penanda urutan gambar khusus Whoosh: 'qr_penumpang_1', 'qr_penumpang_2', dst.")


class AIKeretaMasterSchema(BaseModel):
    kode_booking: str = Field(description="Kode booking / PNR / ID Pesanan utama dari vendor")
    tanggal: str = Field(description="Tanggal keberangkatan format indah dibaca manusia, contoh: '12 Feb 2026' atau '19 Mei 2026'")
    tanggal_berangkat: str = Field(description="Samakan nilainya dengan field 'tanggal'")
    jam_berangkat: str = Field(description="Jam keberangkatan format HH:MM atau HH.MM")
    tanggal_tiba: str = Field(description="Tanggal tiba di stasiun tujuan format indah dibaca manusia, contoh: '12 Feb 2026'")
    jam_tiba: str = Field(description="Jam tiba di stasiun tujuan format HH:MM atau HH.MM")
    asal: str = Field(description="""
        Nama stasiun asal lengkap beserta kode stasiunnya di dalam kurung, contoh: 'Semarang Tawang (SMT)' atau 'Halim'")
        Kode stasiun wajib sesuai aturan resmi KAI dan KCIC.
        Jika tidak ada data sama sekali, ambil 3 digit terdepan nama stasiun. Contoh: 'Buduran (BUD)' atau Gedangan (GED)'
        """)
    tujuan: str = Field(description="""
        Nama stasiun tujuan lengkap beserta kode stasiunnya di dalam kurung, contoh: 'Surabaya Pasarturi (SBI)' atau 'Tegalluar'")
        Kode stasiun wajib sesuai aturan resmi KAI dan KCIC.
        Jika tidak ada data sama sekali, ambil 3 digit terdepan nama stasiun. Contoh: 'Sedati (SED)' atau Wonoayu (WON)'
        """)
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
    permintaan_khusus: str = Field(description="Catatan permintaan khusus tamu, contoh: 'Non Smoking room, King Bed'")
    
    # 1. FIX: Struktur Fasilitas Gabungan Ber-bilingual Aman
    fasilitas: str = Field(description="""
        Fasilitas makan atau utama internal hotel. Contoh: 'Sarapan (2 Pax) per kamar' atau 'Wifi'.
        Ekstrak fasilitas hotel utama. Tuliskan dalam format bilingual (Indonesia / English) jika memungkinkan.
        Contoh: 'Sarapan Gratis / Free Breakfast, WiFi Gratis / Free WiFi'.
    """)
    
    # 2. FIX: Struktur Kontak Pelacakan Otomatis
    hotel_phone: Optional[str] = Field(default="-", description="""
        Gunakan fitur pencarian internet (Google Search) untuk melacak nomor telepon resmi, 
        nomor HP layanan, atau kontak resepsionis aktif dari properti hotel ini berdasarkan nama hotel 
        dan alamat lokasi di atas. Kembalikan hasilnya dalam format string bersih, contoh: '+6285265575009'. 
        Jika setelah dicari di internet tetap tidak ditemukan, isi dengan tanda strip '-'.
    """)
    
    # 3. FIX: Variabel Kamar Dikunci Tunggal (Tanpa Ganda) & Menghapus Kata "Kamar" Otomatis
    kamar: str = Field(description="""
        PENTING: Salin Nama Kamar atau Tipe Kamar secara UTUH dan LENGKAP persis seperti teks yang tertera pada manifes vendor/OTA.
        JANGAN memotong kata imbuhan di belakangnya seperti '- Free Breakfast', 'with Fan', atau 'Room Only'.
        JANGAN sertakan kuantitas angka atau kata pembuka 'Kamar'/'Room' ke dalam field ini.
        Contoh teks: '1 Standard - Free Breakfast' -> Hasil wajib: 'Standard - Free Breakfast'.
        Contoh teks: 'KAMAR SUPERIOR KING BED' -> Hasil wajib: 'SUPERIOR KING BED'.
        Jika di teks asli terdapat versi Bahasa Inggris dan Indonesia, tulis keduanya dipisahkan tanda garis miring (/). 
        Contoh: 'Standard - Breakfast / Standard - Termasuk Sarapan'.
    """)
    
    # 4. FIX: Struktur Deteksi Dinamis Paket Wisata / Tiket Atraksi Tambahan
    paket_wisata_tambahan: Optional[str] = Field(default="-", description="""
        Analisis teks manifest dengan teliti. Jika ditemukan adanya bonus bundle kado/paket tiket masuk wisata, 
        wahana, atau atraksi di luar hotel (seperti Aquaria KLCC, Dufan, Ancol, Jatim Park, Bali Zoo, dll) 
        beserta rincian jumlah tiketnya (cth: 2 Dewasa dan 3 Anak-anak), ekstrak teks tersebut ke dalam field ini.
        Contoh isi field: 'Voucher Package Ticket Aquaria KLCC (Turis Internasional) - 2 Dewasa dan 3 Anak-anak / 2 Adults & 3 Children'.
        Pastikan rincian jumlah tiket ditulis dalam format bilingual (Indonesia / English) agar lolos loket luar negeri.
        Jika tidak ditemukan paket wisata tambahan sama sekali, wajib isi dengan tanda strip '-'.
    """)
    harga_paket_wisata_total: Optional[float] = Field(default=0.0, description="""
        Analisis seluruh instruksi teks input di bagian bawah manifest dengan teliti untuk mencari nominal harga tiket masuk wisata tambahan.
        Hitung total harga paket wisata tersebut dengan rumus matematika internal kamu:
        Total = (Jumlah Pax Dewasa x Harga per Dewasa) + (Jumlah Pax Anak x Harga per Anak).
        
        Contoh instruksi teks: 'Harga Dewasa Rp 259.270/pax. Harga Anak-anak Rp 218.340/pax' dengan jumlah '2 Dewasa dan 3 Anak-anak'.
        Maka kamu WAJIB menghitung di dalam otakmu: (2 x 259270) + (3 x 218340) = 518540 + 655020 = 1173560.
        Kembalikan hasilnya murni berupa angka numerik Integer/Float tanpa tanda titik atau Rp: 1173560.
        Jika tidak ada instruksi nominal harga paket wisata tambahan di teks masukan, wajib berikan nilai: 0.0
    """)
    
class DetailKamarDinamis(BaseModel):
    nomor_urutan_kamar: int = Field(description="Nomor urut kamar, contoh: 1 atau 2")
    nama_tamu_kamar: str = Field(description="Nama tamu spesifik di kamar ini (Title Case), hapus gelar")
    tipe_kamar_nama: str = Field(description="Nama tipe kamar, contoh: 'Deluxe Non View Double'")
    harga_kamar_per_malam: float = Field(description="Harga per malam untuk kamar ini saja, contoh: 750000 atau 500000")
    fasilitas_kamar: str = Field(description="Fasilitas spesifik kamar ini, contoh: 'Sarapan (2 Pax)' atau 'Room Only'")
    permintaan_khusus_kamar: str = Field(description="Permintaan khusus kamar ini, contoh: 'Twin Bed' atau '1 Large Bed'")

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
        PENTING UNTUK TEKS MULTI-KAMAR:
        ⚠️ ATURAN MUTLAK MULTI-KAMAR (WAJIB DIPATUHI):
        1. Analisis teks manifest dengan teliti. Jika tertulis kata 'Tipe Kamar 1', 'Tipe Kamar 2', dst., kamu WAJIB memecah data tersebut menjadi objek terpisah di dalam array 'daftar_detail_kamar'. Jangan pernah menggabungkannya menjadi 1 kamar saja!
        2. Untuk field 'nama_tamu_kamar', ambil nama tamu spesifik yang berada di bawah blok 'Tipe Kamar' tersebut (Contoh: Kamar 1 = Yellena Bunga Casimira, Kamar 2 = Nabila Meinisya Sahira).
        3. Kolom 'kamar' pada objek utama diisi dengan nama tipe kamar global.
        
        💰 ATURAN KALKULASI HARGA FALLBACK:
        - Cari teks harga manual di bagian paling bawah teks seperti 'Harga Kamar 1 750.000/mlm'. Jika ada, gunakan angka tersebut untuk 'harga_kamar_per_malam' di masing-masing kamar.
        - Jika teks harga per kamar tidak tertulis secara eksplisit, cari total harga 'IDR ...' di dalam teks (cth: IDR 769.448). Bagi nominal total tersebut dengan jumlah kamar keseluruhan, lalu masukkan hasilnya sebagai 'harga_kamar_per_malam'. Jangan biarkan nilainya 0 atau kosong!
        
        
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
    """
    Fungsi render HTML E-Tiket Kereta Api & Whoosh bawaan Anda.
    Sudah disesuaikan dinamis: Mengubah Logo KCIC, Judul Whoosh, dan menyalin data kursi utuh.
    """
    # 1. Deteksi Otomatis Jenis Armada secara presisi dari output AI
    nama_kereta_raw = str(data.get('nama_kereta', '')).lower()
    stasiun_asal_raw = str(data.get('asal', '')).lower()
    is_whoosh = "whoosh" in nama_kereta_raw or "halim" in stasiun_asal_raw

    # Penentuan Logo, Judul, dan Tema Warna secara dinamis berbasis armada
    if is_whoosh:
        logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/WHOOSH_Logo.svg/3840px-WHOOSH_Logo.svg.png"
        judul_tiket = ""  # DIHAPUS: Judul dikosongkan agar minimalis & tidak mengganggu sesuai ide Anda
        color_primary = "#b3001b"  # Merah Crimson Whoosh
        color_table_header = "#ffebeb"  # Latar header tabel merah pastel lembut
        color_table_border = "#ffccd3"  # Garis tepi tabel rose/peach lembut
    else:
        logo_url = "https://pilihanhidup.com/wp-content/uploads/2024/04/logo-KAI.png" # Logo KAI asli Anda
        judul_tiket = ""
        color_primary = "#0047b3"  # Biru KAI asli
        color_table_header = "#cce0ff"  # Biru muda pastel
        color_table_border = "#bbb"

    # 2. Iterasi Baris Penumpang Manifes
    penumpang_rows = []
    for idx, p in enumerate(data.get('penumpang', []), start=1):
        qr_html_cell = ""
        
        # Khusus Armada Whoosh: Sediakan penempelan biner QR Code Gate boarding asli
        if is_whoosh:
            key_qr = p.get('qr_placeholder_key', f"qr_penumpang_{idx}")
            file_qr = st.session_state.get(key_qr)
            
            if file_qr:
                import base64
                encoded_img = base64.b64encode(file_qr.getvalue()).decode()
                qr_html_cell = f'<br><img src="data:image/png;base64,{encoded_img}" style="width:90px; height:90px; margin-top:5px; border:1px solid {color_table_border}; padding:2px;"/>'
            else:
                qr_html_cell = '<br><span style="color:#e67e22; font-size:11px; font-weight:bold;">[QR Belum Diupload]</span>'

        row_html = f"""
        <tr>
          <td style="text-align: left; padding:12px 10px; border: 1px solid {color_table_border}; font-size: 14px; color:#222;">{p.get('nama', '-')}</td>
          <td style="text-align: center; padding:12px 10px; border: 1px solid {color_table_border}; font-size: 14px; color:#444;">{p.get('tipe', '-')}</td>
          <td style="text-align: center; padding:12px 10px; border: 1px solid {color_table_border}; font-size: 14px; color:#444;">{p.get('ktp', '-')}</td>
          <td style="text-align: center; padding:12px 10px; border: 1px solid {color_table_border}; font-size: 14px; font-weight: 500; color:#111;">
             {p.get('kursi', '-')}
             {qr_html_cell}
          </td>
        </tr>
        """
        penumpang_rows.append(row_html)

    penumpang_rows_joined = "\n".join(penumpang_rows)

    # =====================================================================
    #3. Tatanan Template HTML Visual Utama Anda (Premium Professional Style)
    # =====================================================================
    html = f"""
    <style>
      /* FIX: Alamat impor Google Fonts diperbaiki secara valid agar font Montserrat aktif */
      @import url('https://googleapis.com');

      @media print {{
        .no-print {{
          display: none !important;
        }}
        thead {{
          background-color: {color_table_header} !important;
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }}
      }}
    </style>

    <div style="font-family: 'Segoe UI', sans-serif; max-width: 720px; margin: 30px auto; background: #fff; border-radius: 14px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.06); padding: 35px; color: #333; border: 1px solid #f0f2f5;">

      <!-- SINKRONISASI UKURAN LOGO: Tinggi dikunci rata 45px agar seimbang -->
      <div style="text-align: center; margin-bottom: 25px; height: 45px; display: flex; align-items: center; justify-content: center;">
        <img src="{logo_url}" style="height: 45px; width: auto; object-fit: contain;"/>
      </div>

      <!-- REVISI: Judul ditarik ke tengah menggunakan font Montserrat Bold premium -->
      {f'''<h1 style="font-family: 'Montserrat', sans-serif; color:{color_primary}; font-size: 26px; font-weight: 700; text-align: center; margin-bottom: 25px; letter-spacing: -0.5px;">{judul_tiket}</h1>''' if not is_whoosh else "<div style='margin-top:10px;'></div>"}
      
      <div style="display: flex; justify-content: space-between; flex-wrap: wrap; margin-bottom: 15px; font-size: 14px; line-height: 1.6;">
        <div style="flex: 1; min-width: 250px;">
          <strong>Kode Booking:</strong> <span style="font-size: 16px; color: #e65c00; font-weight: bold;">{data.get('kode_booking', 'N/A')}</span><br>
          <strong>Nama Kereta:</strong> {data.get('nama_kereta', 'Tidak Diketahui')}<br>
          <strong>Kelas:</strong> {data.get('kelas', 'Tidak Diketahui')}
        </div>
        <div style="flex: 1; min-width: 250px; text-align: right;">
          <strong>Tanggal Berangkat:</strong> {data.get('tanggal_berangkat', 'Tidak Diketahui')}<br>
          <strong>Tanggal Tiba:</strong> {data.get('tanggal_tiba', 'Tidak Diketahui')}
        </div>
      </div>

      <!-- REVISI: Transformasi wadah rute menjadi bentuk kontainer melengkung minimalis modern -->
      <div style="font-size: 14px; line-height: 1.6; background: transparent; padding: 14px 18px; border-radius: 8px; margin-bottom: 25px; text-align: center; border: 2px solid {color_primary}; -webkit-print-color-adjust: exact; print-color-adjust: exact;">
         <strong style="color: {color_primary}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Rute Perjalanan:</strong><br>
         <span style="font-size: 15px; color:#222;">{data.get('asal', 'Tidak Diketahui')} <strong>{data.get('jam_berangkat', '')}</strong> ➔ {data.get('tujuan', 'Tidak Diketahui')} <strong>{data.get('jam_tiba', '')}</strong></span>
      </div>

      <h2 style="font-family: 'Montserrat', sans-serif; font-size: 16px; color: {color_primary}; border-bottom: 2px solid {color_primary}; padding-bottom: 6px; margin-top: 25px;">
         Detail Penumpang
      </h2>
      <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
        <!-- FIX: Background header tabel menggunakan warna pastel lembut -->
        <thead style="background: {color_table_header};">
          <tr>
            <!-- FIX: Garis tepi header tabel disamakan menggunakan variabel color_table_border -->
            <th style="padding: 12px 8px; border: 1px solid {color_table_border}; font-size: 13px; color: #333; font-weight: 700;">Nama</th>
            <th style="padding: 12px 8px; border: 1px solid {color_table_border}; font-size: 13px; color: #333; font-weight: 700;">Tipe</th>
            <th style="padding: 12px 8px; border: 1px solid {color_table_border}; font-size: 13px; color: #333; font-weight: 700;">No Identitas</th>
            <th style="padding: 12px 8px; border: 1px solid {color_table_border}; font-size: 13px; color: #333; font-weight: 700;">Kursi {'/ QR Gate' if is_whoosh else ''}</th>
          </tr>
        </thead>
        <tbody>
          {penumpang_rows_joined}
        </tbody>
      </table>

      <!-- INFO TAMBAHAN PETUNJUK NAIK JIKA ARMADA ADALAH WHOOSH -->
      {f'''<div style="margin-top: 25px; background: #fff8ee; padding: 15px; border-radius: 8px; border-left: 4px solid #e67e22; font-size:13px; color:#c0392b; line-height:1.6;">
        <strong>Panduan Perjalanan Whoosh:</strong><br>
        1. Tiba di stasiun setidaknya 30 menit sebelum keberangkatan.<br>
        2. Scan kode QR di gerbang keberangkatan.<br>
        3. Gerbang keberangkatan ditutup 5 menit sebelum keberangkatan.
      </div>''' if is_whoosh else ""}

      <!-- BARCODE KAI GLOBAL OTOMATIS DISAPA SAAT BUKAN WHOOSH -->
      {f'''<div style="margin-top: 30px; text-align: center;">
        <img src="https://barcode.tec-it.com/barcode.ashx?data={data.get('kode_booking', '')}&code=PDF417" style="width: 250px; height: 80px;" />
        <p style="font-size: 12px; font-weight: bold; margin-top: 6px; color: #666; letter-spacing: 0.5px;">Kode Booking: {data.get('kode_booking', '')}</p>
      </div>''' if not is_whoosh else ""}

      <div style="text-align: center; margin-top: 35px;">
        <!-- MODIFIKASI TIPOGRAFI TOMBOL: Menggunakan Montserrat Bold dan Background Tema Dinamis -->
        <button class="no-print" onclick="window.print()"
                style="padding: 11px 24px; background-color: {color_primary}; color: white; border: none;
                       border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; font-family: 'Montserrat', sans-serif; box-shadow: 0 4px 12px rgba(0,0,0,0.12); letter-spacing: 0.2px;">
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
    # =====================================================================
    # FIX TOTAL: KALKULATOR MULTI-BARIS & SINKRONISASI BILINGUAL LABEL
    # =====================================================================
    try:
        hrg_per_malam = float(data.get('harga_per_malam', 0))
        tot_malam = int(data.get('total_malam', 1))
        jml_kamar = int(data.get('jumlah_kamar', 1))
        # Mengambil angka hitungan murni dari internal otak AI Gemini
        hrg_paket_wisata = float(data.get('harga_paket_wisata_total', 0))
    except (ValueError, TypeError):
        hrg_per_malam = 0.0
        tot_malam = 1
        jml_kamar = 1
        hrg_paket_wisata = 0.0

    # Rumus Hitungan Subtotal & Gabungan Grand Total Akhir
    total_harga_hotel = hrg_per_malam * tot_malam * jml_kamar
    total_harga_gabungan = total_harga_hotel + hrg_paket_wisata

    # Transformasi String Pecahan Mata Uang Rupiah yang Indah
    rate_hotel_str = f"Rp {hrg_per_malam:,.0f}".replace(',', '.')
    total_hotel_str = f"Rp {total_harga_hotel:,.0f}".replace(',', '.')
    total_paket_str = f"Rp {hrg_paket_wisata:,.0f}".replace(',', '.')
    grand_total_str = f"Rp {total_harga_gabungan:,.0f}".replace(',', '.')

    # FIX LOGIKA STRING: Pembersihan nama paket wisata secara aman tanpa split crash
    nama_paket_raw = str(data.get('paket_wisata_tambahan', '-'))
    if nama_paket_raw and nama_paket_raw != '-':
        # Bersihkan kata imbuhan pembuka agar manis ditaruh di dalam sel tabel kecil
        label_paket_wisata = nama_paket_raw.replace('Voucher Package Ticket', '').replace('Include Paket Wisata:', '').strip()
    else:
        label_paket_wisata = "Extra Ticket / Tiket Atraksi Tambahan"



    # =====================================================================
    # 2. PERBAIKAN: Menggabungkan jumlah kamar dan nama kamar secara lengkap
    # =====================================================================
    nama_kamar_raw = get('kamar')
    teks_kamar_final = f"{jml_kamar} x Kamar {nama_kamar_raw}"
    
    teks_paket_ai = get('paket_wisata_tambahan')
    # Kotak emas hanya akan merender jika teks hasil AI bukan strip '-'
    is_ada_paket_wisata = teks_paket_ai != '-' and teks_paket_ai != ''
    
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
        <h3>Property & Location / Properti & Lokasi</h3>
        <p><strong>{get('hotel_name')}</strong><br>
           {get('location')}<br>
           <strong>📞 Kontak Hotel:</strong> {get('hotel_phone')}
        </p>
      </div>

      <div class="section">
        <h3>Reservation Details / Detail Reservasi</h3>
        <p>Jumlah Kamar (Room Count): {get('jumlah_kamar')}<br>
           Check-in: {get('tanggal_masuk')} – {get('jam_masuk')}<br>
           Check-out: {get('tanggal_keluar')} – {get('jam_keluar')}</p>
      </div>
      
      <!-- =====================================================================
           VISUALISASI TABEL DETAIL RINCIAN KOMPONEN BILINGUAL MULTI-BARIS
           ===================================================================== -->
      <div class="section">
        <h3>Pricing Details <span>/ Rincian Harga</span></h3>
        <table class="price-table" style="width: 100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="background-color: #c6d6ff;">
              <th style="text-align: left; padding: 10px 12px; width: 55%;">Description / <span class="lang-en">Deskripsi Komponen</span></th>
              <th style="text-align: center; padding: 10px 12px; width: 15%;">Qty / <span class="lang-en">Jumlah</span></th>
              <th style="text-align: right; padding: 10px 12px; width: 30%;">Total / <span class="lang-en">Subtotal</span></th>
            </tr>
          </thead>
          <tbody>
            <!-- BARIS 1: AKOMODASI KAMAR HOTEL -->
            <tr>
              <td style="text-align: left; padding: 10px 12px; font-size: 13.5px; color: #333; line-height: 1.4;">
                <strong>Room Reservation / Akseptasi Kamar Hotel</strong><br>
                <span style="font-size: 11.5px; color: #666;">({rate_hotel_str} x {tot_malam} malam / night(s))</span>
              </td>
              <td style="text-align: center; padding: 10px 12px; font-size: 13.5px; color: #333;">{jml_kamar} Kamar</td>
              <td style="text-align: right; padding: 10px 12px; font-size: 13.5px; font-weight: 500; color: #333;">{total_hotel_str}</td>
            </tr>
            
            <!-- BARIS 2: BONUS TIKET ATRAKSI WISATA (OTOMATIS AKAN MERENDER JIKA INPUT ADADA DATA HARGANYA) -->
            {f'''<tr>
              <td style="text-align: left; padding: 10px 12px; font-size: 13.5px; color: #333; line-height: 1.4;">
                <strong>Extra Attraction Package / Paket Tiket Wisata</strong><br>
                <span style="font-size: 11.5px; color: #666;">({label_paket_wisata})</span>
              </td>
              <td style="text-align: center; padding: 10px 12px; font-size: 13.5px; color: #333;">1 Paket</td>
              <td style="text-align: right; padding: 10px 12px; font-size: 13.5px; font-weight: 500; color: #333;">{total_paket_str}</td>
            </tr>''' if hrg_paket_wisata > 0.0 or is_ada_paket_wisata else ""}
            
            <!-- BARIS 3: RINGKASAN GRAND TOTAL AKUMULASI GABUNGAN (HOTEL + WISATA) -->
            <tr style="background-color: #f0f4ff; font-weight: 700; border-top: 2px solid #004080;">
              <td colspan="2" style="text-align: right; padding: 12px; font-size: 14px; color: #004080; text-transform: uppercase; letter-spacing: 0.3px;">
                GRAND TOTAL PRICE / <span style="font-size: 11.5px; font-weight:400; font-style:italic; text-transform: none;">Total Bayar</span> :
              </td>
              <td style="text-align: right; padding: 12px; font-size: 15.5px; color: #b30000;">
                {grand_total_str}
              </td>
            </tr>
          </tbody>
        </table>
      </div>


      <!-- =====================================================================
           [BARU] PREMIUM HIGHLIGHT BADGE: KHUSUS BONUS TIKET COMPLEMENTARY
           Mencolok, Berwarna Emas Teduh, dan Dijamin Langsung Terbaca Loket Wisata
           ===================================================================== -->
      {f'''<div class="badge-package" style="margin-top: 25px; background-color: #fff9e6; border: 2px solid #d4af37; border-radius: 8px; padding: 15px 18px; color: #856404; -webkit-print-color-adjust: exact; print-color-adjust: exact;">
        <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #2c3e50;">
          <strong>Include Paket Wisata:</strong> <span style="font-weight: 700; color: #b30000; font-size: 14.5px;">{teks_paket_ai}</span><br>
          <span style="font-size: 12px; font-style: italic; color: #555; display: block; margin-top: 6px;">*Petugas Loket Wisata: Mohon lakukan validasi penukaran tiket fisik menggunakan nomor Itinerary ID atau Order ID resmi yang tertera di atas lembar voucher ini.</span>
        </p>
      </div>''' if is_ada_paket_wisata else ""}
        
      <div class="section">
        <h3>Guest & Room Details / Detail Tamu & Kamar</h3>
        <strong>{tamu_html}</strong><br>
        <p>{teks_kamar_final}</p>
      </div>

      <div class="section">
        <h3>Amenities & Requests / Fasilitas & Permintaan</h3>
        <p><strong>Fasilitas:</strong> {get('fasilitas')}<br>
           <strong>Permintaan Khusus:</strong> {get('permintaan_khusus')}</p>
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
