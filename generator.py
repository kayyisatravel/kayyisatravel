import streamlit as st
import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
import pdf417gen
from PIL import Image
from datetime import datetime
import string


# =======================
# FUNGSI PARSER DINAMIS
# =======================

import re
import string
from datetime import datetime

def parse_input_dynamic(text):
    # --- Kode Booking ---
    kode_booking = 'N/A'
    kb_match = re.search(r'Kode booking\s*[:\-]?\s*(\w+)', text, re.IGNORECASE)
    if kb_match:
        kode_booking = kb_match.group(1).strip()

    # --- Tanggal & Jam Berangkat ---
    tanggal_berangkat = 'Tidak Diketahui'
    jam_berangkat = 'Tidak Diketahui'
    berangkat_match = re.search(
        r'\b(?:Min|Sen|Sel|Rab|Kam|Jum|Sab),\s*(\d{2} \w{3} \d{4})\s*[-–]\s*(\d{2}:\d{2}|\d{4})',
        text
    )
    if berangkat_match:
        try:
            dt = datetime.strptime(berangkat_match.group(1), '%d %b %Y')
            tanggal_berangkat = dt.strftime('%d %b %Y')
        except:
            tanggal_berangkat = berangkat_match.group(1)
        jam_raw = berangkat_match.group(2)
        jam_berangkat = jam_raw if ':' in jam_raw else jam_raw[:2] + ':' + jam_raw[2:]

    # --- Tanggal & Jam Tiba ---
    tanggal_tiba = 'Tidak Diketahui'
    jam_tiba = 'Tidak Diketahui'
    if berangkat_match:
        tiba_match = re.search(
            r'\b(?:Min|Sen|Sel|Rab|Kam|Jum|Sab),\s*(\d{2} \w{3} \d{4})\s*[-–]\s*(\d{2}:\d{2}|\d{4})',
            text[berangkat_match.end():]
        )
        if tiba_match:
            try:
                dt = datetime.strptime(tiba_match.group(1), '%d %b %Y')
                tanggal_tiba = dt.strftime('%d %b %Y')
            except:
                tanggal_tiba = tiba_match.group(1)
            jam_raw = tiba_match.group(2)
            jam_tiba = jam_raw if ':' in jam_raw else jam_raw[:2] + ':' + jam_raw[2:]

    # --- Asal, Tujuan & Kode Stasiun ---
    asal, tujuan = 'Tidak Diketahui', 'Tidak Diketahui'
    kode_stasiun_asal, kode_stasiun_tujuan = '', ''
    stasiun_match = re.findall(r'([A-Za-z .]+)\s*\(([A-Z]{2,3})\)', text)
    kelas_kategori = ['eksekutif', 'ekonomi', 'premium', 'bisnis', 'panoramic', 'priority', 'suite']
    valid_stasiun = []
    for nama, kode in stasiun_match:
        if not any(kelas in nama.lower() for kelas in kelas_kategori):
            valid_stasiun.append((nama, kode))
    
    if len(valid_stasiun) >= 2:
        asal, kode_stasiun_asal = valid_stasiun[0]
        tujuan, kode_stasiun_tujuan = valid_stasiun[1]
        asal = string.capwords(asal.strip().lower())
        tujuan = string.capwords(tujuan.strip().lower())

    # --- Nama Kereta ---
    nama_kereta = 'Tidak Diketahui'
    kereta_match = re.search(r'Nama Kereta:\s*(.+)', text)
    if kereta_match:
        nama_kereta = kereta_match.group(1).strip()
    else:
        kereta_match = re.search(r'\n([A-Za-z ]+)\n\n(Eksekutif|Ekonomi|Premium|Bisnis|Panoramic|Priority|Suite)', text)
        if kereta_match:
            nama_kereta = kereta_match.group(1).strip()
        else:
            kereta_lines = re.findall(r'\n([A-Za-z ]+Ekspres)\n', text, re.IGNORECASE)
            if kereta_lines:
                nama_kereta = kereta_lines[0]
    nama_kereta = string.capwords(nama_kereta.lower())
    
    # --- Kelas Kategori ---
    kelas_kategori_terdeteksi = 'Tidak Diketahui'
    kelas_pattern = r'\b(Eksekutif|Ekonomi|Premium|Bisnis|Panoramic|Priority|Suite)\b'
    kelas_match = re.search(kelas_pattern, text, re.IGNORECASE)
    if kelas_match:
        kelas_kategori_terdeteksi = string.capwords(kelas_match.group(1).lower())

    # --- Penumpang ---
    penumpang = []

    # Format tabel horizontal
    tabel_match = re.search(r'Detail Penumpang\s+Nama\s+Tipe\s+No Identitas\s+Kursi\s+(.*?)(?:\n\n|\Z)', text, re.DOTALL)
    if tabel_match:
        rows = tabel_match.group(1).strip().split('\n')
        for row in rows:
            parts = re.split(r'\t+', row.strip())  # gunakan tab atau spasi lebih dari 1
            if len(parts) >= 4:
                nama = string.capwords(parts[0].strip().lower())
                tipe = parts[1].strip()
                ktp = parts[2].strip()
                kursi_raw = parts[3].strip()
                if re.match(r'^\d+\.\s+', kursi_raw):
                    kursi = 'N/A'
                else:
                    kursi = kursi_raw
                penumpang.append({
                    "nama": nama,
                    "tipe": tipe,
                    "ktp": ktp,
                    "kursi": kursi
                })
    else:
        # Format blok (penumpang & fasilitas)
        penumpang_section = re.search(r'Penumpang & Fasilitas(.*)', text, re.DOTALL | re.IGNORECASE)
        if penumpang_section:
            block = penumpang_section.group(1).strip()
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            i = 0
            while i < len(lines):
                if re.match(r'^\d+\.\s+', lines[i]):
                    nama = re.sub(r'^\d+\.\s+', '', lines[i])
                    tipe = 'Dewasa'
                    ktp = 'N/A'
                    kursi = 'N/A'
                    j = i + 1
                    while j < len(lines) and not re.match(r'^\d+\.\s+', lines[j]):
                        if 'dewasa' in lines[j].lower():
                            tipe = lines[j]
                        elif 'Nomor Identitas' in lines[j]:
                            ktp_match = re.search(r'Nomor Identitas:\s*(\d+)', lines[j])
                            if ktp_match:
                                ktp = ktp_match.group(1)
                        elif 'kursi' in lines[j].lower():
                            kursi = lines[j].replace("Kursi", "").strip()
                        j += 1
                    penumpang.append({
                        "nama": string.capwords(nama.lower()),
                        "tipe": tipe,
                        "ktp": ktp,
                        "kursi": kursi
                    })
                    i = j
                else:
                    i += 1

    return {
        "kode_booking": kode_booking,
        "tanggal": tanggal_berangkat,
        "tanggal_berangkat": tanggal_berangkat,
        "jam_berangkat": jam_berangkat,
        "tanggal_tiba": tanggal_tiba,
        "jam_tiba": jam_tiba,
        "asal": f"{asal} ({kode_stasiun_asal})" if kode_stasiun_asal else asal,
        "tujuan": f"{tujuan} ({kode_stasiun_tujuan})" if kode_stasiun_tujuan else tujuan,
        "nama_kereta": nama_kereta,
        "kelas": kelas_kategori_terdeteksi,
        "penumpang": penumpang
    }

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

def parse_evoucher_text(text):
    # Bersihkan dan split per baris
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    data = {
        'order_id': '-',
        'itinerary_id': '-',
        'hotel_name': '-',
        'location': '-',
        'jumlah_kamar': '-',
        'tanggal_masuk': '-',
        'jam_masuk': '-',
        'tanggal_keluar': '-',
        'jam_keluar': '-',
        'tamu': [],
        'kamar': '-',
        'jumlah_tamu': '-',
        'fasilitas': '-',
        'permintaan_khusus': '-',
        'harga_per_malam': '-',
        'total_malam': '-',
        'total_harga': '-'
    }

    # Cari Order ID dan Itinerary ID
    for line in lines:
        if line.lower().startswith('order id:'):
            data['order_id'] = line.split(':',1)[1].strip()
        elif line.lower().startswith('itinerary id:'):
            data['itinerary_id'] = line.split(':',1)[1].strip()

    # Hotel name & location (dianggap setelah line kosong kedua)
    # Cari posisi kata kunci
    try:
        idx_detail_reservasi = next((i for i, l in enumerate(lines) if l.lower() == 'detail reservasi'), -1)
    except ValueError:
        idx_detail_reservasi = -1

    # Ambil hotel name dan lokasi sebelum Detail Reservasi
    if idx_detail_reservasi > 1:
        data['hotel_name'] = lines[idx_detail_reservasi - 3] if idx_detail_reservasi-3 >=0 else '-'
        data['location'] = lines[idx_detail_reservasi - 2] if idx_detail_reservasi-2 >=0 else '-'

    # Detail Reservasi - kamar
    if idx_detail_reservasi != -1 and idx_detail_reservasi+1 < len(lines):
        data['jumlah_kamar'] = lines[idx_detail_reservasi + 1]

    # Cari tanggal masuk, keluar dan jam
    def find_next_after(keyword):
        try:
            i = lines.index(keyword)
            return i
        except ValueError:
            return -1

    idx_tgl_keluar = find_next_after('Tanggal keluar')
    idx_tgl_masuk = find_next_after('Tanggal masuk')

    if idx_tgl_keluar != -1 and idx_tgl_keluar+2 < len(lines):
        data['tanggal_keluar'] = lines[idx_tgl_keluar + 1]
        data['jam_keluar'] = lines[idx_tgl_keluar + 2]

    if idx_tgl_masuk != -1 and idx_tgl_masuk+2 < len(lines):
        data['tanggal_masuk'] = lines[idx_tgl_masuk + 1]
        data['jam_masuk'] = lines[idx_tgl_masuk + 2]

    # Detail tamu dan kamar
    try:
        idx_detail_tamu = lines.index('Detail Tamu')
    except ValueError:
        idx_detail_tamu = -1

    if idx_detail_tamu != -1:
        # Ambil tamu (asumsi baris setelah Detail Tamu dan sebelum "Kamar")
        tamu_list = []
        for i in range(idx_detail_tamu+1, len(lines)):
            if lines[i].lower() == 'kamar':
                break
            tamu_list.append(lines[i])
        data['tamu'] = tamu_list

        # Ambil kamar, jumlah tamu di baris setelah "Kamar"
        try:
            idx_kamar = lines.index('Kamar')
            if idx_kamar + 1 < len(lines):
                data['kamar'] = lines[idx_kamar + 1]
            if idx_kamar + 2 < len(lines):
                data['jumlah_tamu'] = lines[idx_kamar + 2]
        except ValueError:
            pass

    # Fasilitas
    try:
        idx_fasilitas = lines.index('Fasilitas')
        if idx_fasilitas + 1 < len(lines):
            data['fasilitas'] = lines[idx_fasilitas + 1]
    except ValueError:
        pass

    # Permintaan Khusus
    try:
        idx_permintaan = lines.index('Permintaan Khusus')
        if idx_permintaan + 1 < len(lines):
            data['permintaan_khusus'] = lines[idx_permintaan + 1].replace('Others:', '').strip()
    except ValueError:
        pass

    # Harga per malam, total malam, total harga
    def extract_price(label):
        try:
            idx = lines.index(label)
            if idx+1 < len(lines):
                return lines[idx+1]
        except ValueError:
            return '-'
        return '-'

    data['harga_per_malam'] = extract_price('Harga per malam')
    data['total_malam'] = extract_price('Total malam')
    data['total_harga'] = extract_price('Total harga')

    return data
def generate_evoucher_html(data):
    # Pastikan data sudah lengkap, kalau ada key hilang kasih default '-'
    get = lambda k: data.get(k, '-') if data.get(k, '-') else '-'

    # Format tamu menjadi list <p>
    tamu_html = "".join(f"<p>{tamu}</p>" for tamu in get('tamu')) if get('tamu') != '-' else "<p>-</p>"

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
        padding: 15px 25px;
        border-radius: 8px;
        border-bottom: 3px solid #004080;
        margin-bottom: 25px;
      }}
      .header-left {{
        display: flex;
        align-items: center;
        gap: 15px;
      }}
      .header-left img {{
        height: 60px;
        border-radius: 5px;
        border: 1px solid #004080;
        background: white;
      }}
      .header-left h1 {{
        margin: 0;
        font-weight: 700;
        font-size: 26px;
        letter-spacing: 2px;
      }}
      .header-right {{
        font-weight: 700;
        font-size: 22px;
        letter-spacing: 3px;
        text-transform: uppercase;
        align-self: center;
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
        text-align: left;
        font-size: 15px;
        color: #003366;
      }}
      .price-table th {{
        background-color: #c6d6ff;
        font-weight: 700;
      }}
    </style>

    <div class="voucher">
      <div class="header">
        <div class="header-left">
          <img src="URL_LOGO" alt="Logo Kayyisa Tour & Travel">
          <h1>Kayyisa Tour & Travel</h1>
        </div>
        <div class="header-right">
          Hotel Reservation
        </div>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M3 3h18v2H3V3zm0 4h18v14H3V7zm2 2v10h14V9H5z"/></svg>
          Order & Itinerary
        </h3>
        <p>Order ID: {get('order_id')}<br>
           Itinerary ID: {get('itinerary_id')}</p>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 2l2 7h7l-5.5 4.5L17 21l-5-3.5L7 21l1.5-7.5L3 9h7z"/></svg>
          Properti & Lokasi
        </h3>
        <p>{get('hotel_name')}<br>
           {get('location')}</p>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M7 13h10v2H7v-2zm0-4h10v2H7V9zm0-4h10v2H7V5z"/></svg>
          Detail Reservasi
        </h3>
        <p>Jumlah Kamar: {get('jumlah_kamar')}<br>
           Tanggal Masuk: {get('tanggal_masuk')} – {get('jam_masuk')}<br>
           Tanggal Keluar: {get('tanggal_keluar')} – {get('jam_keluar')}</p>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 21c4.97 0 9-4.03 9-9s-4.03-9-9-9-9 4.03-9 9 4.03 9 9 9zM7 11h2v2H7v-2zm4 0h2v2h-2v-2zm4 0h2v2h-2v-2z"/></svg>
          Harga & Pembayaran
        </h3>
        <table class="price-table">
          <tr>
            <th>Rate per Malam</th>
            <th>Total Malam</th>
            <th>Total Harga</th>
          </tr>
          <tr>
            <td>{get('harga_per_malam')}</td>
            <td>{get('total_malam')} malam</td>
            <td><strong>{get('total_harga')}</strong></td>
          </tr>
        </table>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 12c2.67 0 8 1.34 8 4v4H4v-4c0-2.66 5.33-4 8-4zm0-2a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/></svg>
          Detail Tamu & Kamar
        </h3>
        {tamu_html}
        <p>{get('kamar')} – {get('jumlah_tamu')}</p>
      </div>

      <div class="section">
        <h3>
          <svg class="icon" viewBox="0 0 24 24"><path d="M10 17l5-5-5-5v10z"/></svg>
          Fasilitas & Permintaan
        </h3>
        <p>Fasilitas: {get('fasilitas')}<br>
           Permintaan Khusus: {get('permintaan_khusus')}</p>
      </div>

      <div class="footer">
        Jika ada kendala saat check‑in, silakan hubungi kami di: (nomor/email customer service)
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
