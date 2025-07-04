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
    # Ambil Kode Booking (cari pola "Kode Booking" atau "Kode Pemesanan")
    booking_match = re.search(r'Kode(?:\s|_)Booking\s*:?\s*(\w+)', text, re.IGNORECASE)
    if not booking_match:
        booking_match = re.search(r'Kode\s*Pemesanan\s*:?\s*(\w+)', text, re.IGNORECASE)
    kode_booking = booking_match.group(1).strip() if booking_match else 'N/A'

    # Tanggal (cari format hari, tanggal, bulan, tahun)
    tanggal_match = re.search(r'\b(?:Sen|Sel|Rab|Kam|Jum|Sab|Min)[a-z]*,\s*\d{1,2}\s*\w+\s*\d{4}', text, re.IGNORECASE)
    if not tanggal_match:
        # Alternatif cari tanggal dalam format yyyy-mm-dd (misal Tanggal Pesan: 2025-07-04)
        tanggal_match = re.search(r'Tanggal\s*(?:Pesan)?\s*:?\s*(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
    tanggal = tanggal_match.group(0).strip() if tanggal_match else 'Tidak Diketahui'

    # Nama Kereta (misal HARINA 99 atau BLAMBANGAN EKSPRES)
    kereta_match = re.search(r'^([A-Z ]+\d*[A-Z]*)', text.strip(), re.MULTILINE)
    nama_kereta = kereta_match.group(1).strip().title() if kereta_match else 'Tidak Diketahui'

    # Jam berangkat dan tiba (ambil dua waktu 00:00 paling awal)
    jam_match = re.findall(r'(\d{2}:\d{2})', text)
    if len(jam_match) >= 2:
        jam_berangkat, jam_tiba = jam_match[0], jam_match[1]
    else:
        jam_berangkat = jam_tiba = 'Tidak Diketahui'

    # Stasiun asal dan tujuan (cari pola nama stasiun besar)
    # Coba ambil dari pola "(STASIUN)" atau "STASIUN (KODE)"
    stasiun_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Za-z]+)*?)\s*(?:\([A-Z]{2,4}\))?', text)
    if len(stasiun_matches) >= 2:
        asal, tujuan = stasiun_matches[0].strip(), stasiun_matches[1].strip()
    else:
        asal = tujuan = 'Tidak Diketahui'

    # Parsing Penumpang
    penumpang = []

    # Coba parsing versi baru dulu (blok Detail Penumpang: nama, kursi, nomor identitas)
    detail_pos = text.find("Detail Penumpang")
    if detail_pos >= 0:
        block = text[detail_pos:]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        i = 1  # start setelah "Detail Penumpang"
        while i < len(lines):
            nama = lines[i]
            if not nama:
                break
            # Pastikan ada cukup baris berikutnya untuk kursi dan no identitas
            if i+2 < len(lines):
                kursi = lines[i+1].replace(" ", "")
                no_identitas = lines[i+2]
                # Cek apakah no_identitas berupa angka panjang (ID)
                if re.match(r'^\d{10,}$', no_identitas):
                    penumpang.append({
                        "nama": nama,
                        "tipe": "Dewasa",  # Default asumsi dewasa jika tipe tidak eksplisit
                        "ktp": no_identitas,
                        "kursi": kursi
                    })
                    i += 3
                    continue
            i += 1

    # Jika penumpang masih kosong, fallback regex lama
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


# =========================
# GENERATE HTML E-TIKET
# =========================

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
