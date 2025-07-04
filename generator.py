import streamlit as st
import re

# =======================
# FUNGSI PARSER DINAMIS
# =======================

def parse_input_dynamic(text):
    booking_match = re.search(r'Kode(?:\s|_)Booking\s*:\s*(\w+)', text, re.IGNORECASE)
    kode_booking = booking_match.group(1) if booking_match else 'N/A'

    tanggal_match = re.search(r'\b(?:Jum|Kam|Sen|Sel|Rab|Sab|Min)[a-z]*,\s*\d{1,2}\s*\w+\s*\d{4}', text, re.IGNORECASE)
    tanggal = tanggal_match.group(0) if tanggal_match else 'Tidak Diketahui'

    kereta_match = re.search(r'([A-Z ]+)\s*\(\d+\)', text)
    nama_kereta = kereta_match.group(1).title() if kereta_match else 'Tidak Diketahui'

    rute_match = re.search(r'([A-Z ]+)\s*→\s*([A-Z ]+)\s*\n(\d{2}:\d{2})\s*(\d{2}:\d{2})', text)
    if rute_match:
        asal = rute_match.group(1).strip().title()
        tujuan = rute_match.group(2).strip().title()
        jam_berangkat = rute_match.group(3)
        jam_tiba = rute_match.group(4)
    else:
        asal = tujuan = jam_berangkat = jam_tiba = 'Tidak Diketahui'

    penumpang = []
    penumpang_lines = re.findall(r'(\d+)\s+(.+?)\s+\((Dewasa|Anak|Bayi)\)\s+KTP\s+(\d+)\s+([A-Z]+\s*/\s*\d+[A-Z]?)', text)
    for p in penumpang_lines:
        penumpang.append({
            "nama": p[1],
            "tipe": p[2],
            "ktp": p[3],
            "kursi": p[4].replace(" ", "")
        })

    if not penumpang:
        fallback_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)Rp\.\s*\d+', text)
        if fallback_match:
            penumpang = [{
                "nama": fallback_match.group(1),
                "tipe": "Dewasa",
                "ktp": "Tidak Diketahui",
                "kursi": "Tidak Diketahui"
            }]

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
