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

def parse_input_dynamic(text):
    # --- Kode Booking ---
    kode_booking = 'N/A'
    kb_match = re.search(r'Kode booking\s*:\s*(\w+)', text, re.IGNORECASE)
    if kb_match:
        kode_booking = kb_match.group(1).strip()

    # --- Tanggal & Jam Berangkat ---
    tanggal_berangkat = 'Tidak Diketahui'
    jam_berangkat = 'Tidak Diketahui'
    berangkat_match = re.search(r'(\w{3}),\s*(\d{2} \w{3} \d{4}) - (\d{2}:\d{2}|\d{4})', text)
    if berangkat_match:
        try:
            dt = datetime.strptime(berangkat_match.group(2), '%d %b %Y')
            tanggal_berangkat = dt.strftime('%d %b %Y')
        except:
            tanggal_berangkat = berangkat_match.group(2)
        jam_berangkat_raw = berangkat_match.group(3)
        jam_berangkat = jam_berangkat_raw if ':' in jam_berangkat_raw else jam_berangkat_raw[:2] + ':' + jam_berangkat_raw[2:]

    # --- Tanggal & Jam Tiba ---
    tanggal_tiba = 'Tidak Diketahui'
    jam_tiba = 'Tidak Diketahui'
    if berangkat_match:
        tiba_match = re.search(r'(\w{3}),\s*(\d{2} \w{3} \d{4}) - (\d{2}:\d{2}|\d{4})', text[berangkat_match.end():])
        if tiba_match:
            try:
                dt = datetime.strptime(tiba_match.group(2), '%d %b %Y')
                tanggal_tiba = dt.strftime('%d %b %Y')
            except:
                tanggal_tiba = tiba_match.group(2)
            jam_tiba_raw = tiba_match.group(3)
            jam_tiba = jam_tiba_raw if ':' in jam_tiba_raw else jam_tiba_raw[:2] + ':' + jam_tiba_raw[2:]

    # --- Asal, Tujuan & Kode Stasiun ---
    asal, tujuan = 'Tidak Diketahui', 'Tidak Diketahui'
    kode_stasiun_asal, kode_stasiun_tujuan = '', ''
    rute_full = re.findall(r'([A-Za-z ]+)\s*\(([A-Z]{2,3})\)', text)
    if len(rute_full) >= 2:
        asal = string.capwords(rute_full[0][0].strip().lower())
        kode_stasiun_asal = rute_full[0][1]
        tujuan = string.capwords(rute_full[1][0].strip().lower())
        kode_stasiun_tujuan = rute_full[1][1]

    # --- Nama Kereta ---
    nama_kereta = 'Tidak Diketahui'
    kereta_match = re.search(r'\n([A-Za-z ]+)\n\nEksekutif', text)
    if kereta_match:
        nama_kereta = kereta_match.group(1).strip()
    else:
        kereta_lines = re.findall(r'\n([A-Za-z ]+Ekspres)\n', text, re.IGNORECASE)
        if kereta_lines:
            nama_kereta = kereta_lines[0]
    nama_kereta = string.capwords(nama_kereta.lower())

    # --- Penumpang ---
    penumpang = []
    penumpang_section = re.search(r'Penumpang & Fasilitas(.*)', text, re.DOTALL | re.IGNORECASE)
    if penumpang_section:
        block = penumpang_section.group(1).strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        i = 0
        while i < len(lines):
            if re.match(r'^\d+\.\s+', lines[i]):
                nama = re.sub(r'^\d+\.\s+', '', lines[i])
                tipe_penumpang = lines[i+1] if i+1 < len(lines) else 'Dewasa'
                ktp_match = re.search(r'Nomor Identitas:\s*(\d+)', lines[i+2]) if i+2 < len(lines) else None
                ktp = ktp_match.group(1) if ktp_match else 'N/A'
                kursi = lines[i+4] if i+4 < len(lines) else 'N/A'
                kursi = kursi.replace("Kursi", "").strip()
                penumpang.append({
                    "nama": string.capwords(nama.lower()),
                    "tipe": tipe_penumpang,
                    "ktp": ktp,
                    "kursi": kursi
                })
                i += 5
            else:
                i += 1

    return {
        "kode_booking": kode_booking,
        "tanggal": tanggal_berangkat,
        "tanggal_berangkat": tanggal_berangkat,
        "jam_berangkat": jam_berangkat,
        "tanggal_tiba": tanggal_tiba,
        "jam_tiba": jam_tiba,
        "asal": asal,
        "kode_stasiun_asal": kode_stasiun_asal,
        "tujuan": tujuan,
        "kode_stasiun_tujuan": kode_stasiun_tujuan,
        "nama_kereta": nama_kereta,
        "penumpang": penumpang
    }

def generate_eticket(data):
    penumpang_rows = "\n".join([
        f"""
        <tr>
          <td style="text-align: left;">{p['nama']}</td>
          <td style="text-align: center;">{p['tipe']}</td>
          <td style="text-align: center;">{p['ktp']}</td>
          <td style="text-align: center;">{p['kursi']}</td>
        </tr>
        """ for p in data['penumpang']
    ])

    html = f"""
    <div style="font-family: 'Segoe UI'; max-width: 720px; margin: 30px auto; background: #fff; border-radius: 14px; box-shadow: 0 8px 25px rgba(0,0,0,0.12); padding: 30px; color: #333;">
      <div style="text-align: center; margin-bottom: 20px;">
        <img src="https://pilihanhidup.com/wp-content/uploads/2024/04/logo-KAI.png" style="width: 120px;"/>
      </div>

      <h1 style="color:#0047b3;">🎫 E-Tiket Kereta Api</h1>
      <p><strong>Kode Booking:</strong> {data.get('kode_booking', 'N/A')}<br>
         <strong>Tanggal Berangkat:</strong> {data.get('tanggal_berangkat', 'Tidak Diketahui')}<br>
         <strong>Tanggal Tiba:</strong> {data.get('tanggal_tiba', 'Tidak Diketahui')}<br>
         <strong>Nama Kereta:</strong> {data.get('nama_kereta', 'Tidak Diketahui')}</p>

      <p><strong>Rute:</strong><br>
      {data['asal']} <strong>{data['jam_berangkat']}</strong> → {data['tujuan']} <strong>{data['jam_tiba']}</strong></p>

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
        <img src="https://barcode.tec-it.com/barcode.ashx?data={data['kode_booking']}&code=PDF417"
             style="width: 250px; height: 80px;" />
        <p><strong>Kode Booking:</strong> {data['kode_booking']}</p>
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
