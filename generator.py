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
    # Debug print seluruh teks
    # print("=== INPUT TEXT ===\n", text)

    # --- Kode Booking ---
    kode_booking = 'N/A'
    booking_match = re.search(r'Kode(?:\s|_)Booking\s*:?\s*(\w+)', text, re.IGNORECASE)
    if booking_match:
        kode_booking = booking_match.group(1).strip()

    # --- Tanggal ---
    tanggal = 'Tidak Diketahui'
    tanggal_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
    if tanggal_match:
        try:
            dt = datetime.strptime(tanggal_match.group(0), '%Y-%m-%d')
            tanggal = dt.strftime('%d %b %Y')
        except:
            tanggal = tanggal_match.group(0)
    else:
        tanggal_match2 = re.search(r'\b(?:Sen|Sel|Rab|Kam|Jum|Sab|Min)[a-z]*,\s*\d{1,2}\s*\w+\s*\d{4}', text, re.IGNORECASE)
        if tanggal_match2:
            tanggal = tanggal_match2.group(0).strip()

    # --- Nama Kereta ---
    nama_kereta = 'Tidak Diketahui'
    # Cari Nomor KA dan nama kereta di bawahnya
    kereta_match = re.search(r'Nomor KA\s*\n([A-Z\s]+)', text, re.IGNORECASE)
    if kereta_match:
        nama_kereta = string.capwords(kereta_match.group(1).strip().lower())
    else:
        # fallback: baris pertama yang ada angka (misal HARINA 99)
        kereta_match2 = re.search(r'^([A-Z ]+\d+)', text.strip(), re.MULTILINE)
        if kereta_match2:
            nama_kereta = string.capwords(kereta_match2.group(1).strip().lower())

    # --- Rute Asal dan Tujuan ---
    asal = 'Tidak Diketahui'
    tujuan = 'Tidak Diketahui'

    keberangkatan_match = re.search(r'Keberangkatan\s*\n\s*([A-Z\s]+)\s*\([A-Z]+\)', text, re.IGNORECASE)
    if keberangkatan_match:
        asal = string.capwords(keberangkatan_match.group(1).strip().lower())

    tujuan_match = re.search(r'Tujuan\s*\n\s*([A-Z\s]+)\s*\([A-Z]+\)', text, re.IGNORECASE)
    if tujuan_match:
        tujuan = string.capwords(tujuan_match.group(1).strip().lower())

    # --- Jam Berangkat & Tiba ---
    jam_berangkat = 'Tidak Diketahui'
    jam_tiba = 'Tidak Diketahui'

    jam_berangkat_match = re.search(r'Keberangkatan.*?(\d{4})', text, re.DOTALL)
    if jam_berangkat_match:
        jam_berangkat = jam_berangkat_match.group(1)
        jam_berangkat = jam_berangkat[:2] + ':' + jam_berangkat[2:]

    jam_tiba_match = re.search(r'Tujuan.*?(\d{4})', text, re.DOTALL)
    if jam_tiba_match:
        jam_tiba = jam_tiba_match.group(1)
        jam_tiba = jam_tiba[:2] + ':' + jam_tiba[2:]

    # --- Penumpang ---
    penumpang = []
    detail_penumpang_match = re.search(r'Detail Penumpang(.*?)(?:\n\n|$)', text, re.DOTALL | re.IGNORECASE)
    if detail_penumpang_match:
        block = detail_penumpang_match.group(1).strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        # Filter baris header
        header_keywords = ['Penumpang', 'Kursi', 'Kelas', 'No Identitas', 'Tipe', 'Identitas', 'Nomor']
        filtered_lines = [line for line in lines if not any(hk.lower() in line.lower() for hk in header_keywords)]

        for line in filtered_lines:
            # Pisahkan berdasarkan spasi, cari nomor identitas yang berupa 15+ digit
            parts = line.split()
            ktp_index = None
            for i, p in enumerate(parts):
                if re.fullmatch(r'\d{15,}', p):
                    ktp_index = i
                    break
            if ktp_index is not None:
                nama = " ".join(parts[:ktp_index])
                ktp = parts[ktp_index]
                kursi = parts[ktp_index + 1] if len(parts) > ktp_index + 1 else "N/A"
                penumpang.append({
                    "nama": string.capwords(nama.lower()),
                    "tipe": "Dewasa",
                    "ktp": ktp,
                    "kursi": kursi.replace(" ", "")
                })

    # fallback format lama
    if not penumpang:
        penumpang_lines = re.findall(
            r'\d+\s+(.+?)\s+\((Dewasa|Anak|Bayi)\)\s+KTP\s+(\d+)\s+([A-Z]+\s*\d+\s*/\s*\d+[A-Z]?)',
            text
        )
        for p in penumpang_lines:
            penumpang.append({
                "nama": string.capwords(p[0].lower()),
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
