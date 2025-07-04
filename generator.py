import streamlit as st
import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
import pdf417gen
from PIL import Image

# =======================
# FUNGSI PARSER DINAMIS
# =======================

def parse_input_dynamic(text):
    # Kode Booking
    booking_match = re.search(r'Kode(?:\s|_)Booking\s*:?\s*(\w+)', text, re.IGNORECASE)
    if not booking_match:
        booking_match = re.search(r'Kode\s*Pemesanan\s*:?\s*(\w+)', text, re.IGNORECASE)
    kode_booking = booking_match.group(1).strip() if booking_match else 'N/A'

    # Tanggal: cari format hari, tanggal bulan tahun
    tanggal_match = re.search(r'\b(?:Sen|Sel|Rab|Kam|Jum|Sab|Min)[a-z]*,\s*\d{1,2}\s*\w+\s*\d{4}', text, re.IGNORECASE)
    if not tanggal_match:
        # Alternatif: tanggal pesan yyyy-mm-dd
        tanggal_match = re.search(r'Tanggal\s*(?:Pesan)?\s*:?\s*([\d\-]+)', text, re.IGNORECASE)
    tanggal = tanggal_match.group(1).strip() if tanggal_match else 'Tidak Diketahui'

    # Nama Kereta: coba cari di blok Nomor KA / Nama KA atau baris awal besar
    kereta_match = re.search(r'Nomor KA\s*\n([A-Z\s]+)', text, re.IGNORECASE)
    if kereta_match:
        nama_kereta = kereta_match.group(1).strip().title()
    else:
        # fallback ambil baris pertama kapital
        kereta_match = re.search(r'^([A-Z ]+\d*[A-Z]*)', text.strip(), re.MULTILINE)
        nama_kereta = kereta_match.group(1).strip().title() if kereta_match else 'Tidak Diketahui'

    # Asal & Tujuan: dari blok keberangkatan dan tujuan format:
    # SURABAYA GUBENG (SGU) 2025-07-06, 2250
    # BANYUWANGI KOTA (BWI) 2025-07-07, 0425
    rute_match = re.findall(r'([A-Z][A-Za-z\s]+)\s+\([A-Z]{2,4}\)\s+\d{4}-\d{2}-\d{2},\s*\d{4}', text)
    if len(rute_match) >= 2:
        asal = rute_match[0].strip().title()
        tujuan = rute_match[1].strip().title()
    else:
        asal = tujuan = 'Tidak Diketahui'

    # Jam berangkat & tiba dari format waktu 4 digit setelah tanggal (misal 2250 -> 22:50)
    jam_berangkat = jam_tiba = 'Tidak Diketahui'
    jam_match = re.findall(r'\d{4}', text)
    if len(jam_match) >= 2:
        def format_jam(j):
            return f"{j[:2]}:{j[2:]}"
        jam_berangkat = format_jam(jam_match[0])
        jam_tiba = format_jam(jam_match[1])

    # Parsing penumpang dari blok Detail Penumpang:
    penumpang = []
    detail_pos = text.find("Detail Penumpang")
    if detail_pos >= 0:
        block = text[detail_pos:]
        # Cari pola: Nama, Kursi, No Identitas (angka panjang)
        # Contoh: AMILIYA DUWI SETIYOWATI\nEKS-5 10D\n3522096901030005
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        i = 1
        while i + 2 < len(lines):
            nama = lines[i]
            kursi = lines[i+1].replace(" ", "")
            ktp = lines[i+2]
            if re.match(r'^\d{10,}$', ktp):
                penumpang.append({
                    "nama": nama,
                    "tipe": "Dewasa",  # default
                    "ktp": ktp,
                    "kursi": kursi
                })
                i += 3
            else:
                i += 1

    # Jika penumpang kosong fallback ke regex lama
    if not penumpang:
        penumpang_lines = re.findall(
            r'\d+\s+(.+?)\s+\((Dewasa|Anak|Bayi)\)\s+KTP\s+(\d+)\s+([A-Z]+\s*\d+\s*/\s*\d+[A-Z]?)',
            text
        )
        for p in penumpang_lines:
            penumpang.append({
                "nama": p[0],
                "tipe": p[1],
                "ktp": p[2],
                "kursi": p[3].replace(" ", "")
            })

    return {
        "kode_booking": kode_booking,
        "tanggal": tanggal,
        "nama_kereta": nama_kereta,
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
