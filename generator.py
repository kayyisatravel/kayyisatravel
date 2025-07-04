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
    booking_match = re.search(r'Kode\s*Pemesanan\s*:?\s*(\w+)', text, re.IGNORECASE)
    if booking_match:
        kode_booking = booking_match.group(1).strip()

    # --- Tanggal ---
    tanggal = 'Tidak Diketahui'
    tanggal_match = re.search(r'Tanggal Pesan\s*:\s*(\d{4}-\d{2}-\d{2})', text)
    if tanggal_match:
        try:
            dt = datetime.strptime(tanggal_match.group(1), '%Y-%m-%d')
            tanggal = dt.strftime('%d %b %Y')
        except:
            tanggal = tanggal_match.group(1)

    # --- Nama Kereta dan Nomor KA ---
    nama_kereta = 'Tidak Diketahui'
    nomor_ka = ''
    # Cari nama kereta dan nomor KA dengan cari baris 'Nomor KA' lalu ambil 2 baris setelahnya
    lines = text.splitlines()
    try:
        idx_ka = next(i for i,v in enumerate(lines) if 'Nomor KA' in v)
        # nama kereta 2 baris setelah
        nama_kereta_raw = lines[idx_ka + 3].strip() if len(lines) > idx_ka + 3 else ''
        nomor_ka_raw = lines[idx_ka + 4].strip() if len(lines) > idx_ka + 4 else ''
        if nama_kereta_raw:
            nama_kereta = string.capwords(nama_kereta_raw.lower())
        if nomor_ka_raw:
            nomor_ka = nomor_ka_raw
    except StopIteration:
        pass

    # --- Rute Asal dan Tujuan + Jam ---
    # Cari keberangkatan dan tujuan sesuai format dua baris
    asal = 'Tidak Diketahui'
    tujuan = 'Tidak Diketahui'
    jam_berangkat = 'Tidak Diketahui'
    jam_tiba = 'Tidak Diketahui'

    # Cari baris stasiun keberangkatan dan jamnya
    keberangkatan_match = re.search(
        r'Keberangkatan\s*\n\s*([A-Z\s]+)\s*\([A-Z]+\)\s*\d{4}-\n(\d{2}-\d{2}),\s*(\d{4})',
        text, re.IGNORECASE)
    if keberangkatan_match:
        asal = string.capwords(keberangkatan_match.group(1).strip().lower())
        jam_berangkat = keberangkatan_match.group(3)
        jam_berangkat = jam_berangkat[:2] + ':' + jam_berangkat[2:]

    # Cari baris stasiun tujuan dan jamnya
    tujuan_match = re.search(
        r'Tujuan\s*\n\s*([A-Z\s]+)\s*\([A-Z]+\)\s*\d{4}-\n(\d{2}-\d{2}),\s*(\d{4})',
        text, re.IGNORECASE)
    if tujuan_match:
        tujuan = string.capwords(tujuan_match.group(1).strip().lower())
        jam_tiba = tujuan_match.group(3)
        jam_tiba = jam_tiba[:2] + ':' + jam_tiba[2:]

    # --- Penumpang ---
    penumpang = []
    # Ambil block Detail Penumpang
    detail_match = re.search(r'Detail Penumpang(.*)', text, re.IGNORECASE|re.DOTALL)
    if detail_match:
        block = detail_match.group(1).strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        # Parsing 3 baris: nama, kursi, ktp
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines):
                nama = lines[i]
                kursi = lines[i+1]
                ktp = lines[i+2]
                if re.fullmatch(r'\d{15,}', ktp):
                    penumpang.append({
                        "nama": string.capwords(nama.lower()),
                        "tipe": "Dewasa",
                        "ktp": ktp,
                        "kursi": kursi.replace(" ", "")
                    })

    return {
        "kode_booking": kode_booking,
        "tanggal": tanggal,
        "nama_kereta": f"{nama_kereta} {nomor_ka}".strip(),
        "asal": asal,
        "tujuan": tujuan,
        "jam_berangkat": jam_berangkat,
        "jam_tiba": jam_tiba,
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
      <p><strong>Kode Booking:</strong> {data['kode_booking']}<br>
         <strong>Tanggal:</strong> {data['tanggal']}<br>
         <strong>Nama Kereta:</strong> {data['nama_kereta']}</p>

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
