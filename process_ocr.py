import re
from datetime import datetime
#refresh
# =========================
# === UTILITY FUNCTIONS ===
# =========================

def clean_text(text: str) -> str:
    """
    Menghapus baris kosong, memangkas spasi di awal/akhir tiap baris,
    lalu menggabungkan menjadi satu string (per-barang).
    """
    return ' '.join(line.strip() for line in text.splitlines() if line.strip())

def clean_text_keep_lines(text: str) -> str:
    """
    Menghapus baris kosong, memangkas spasi di awal/akhir tiap baris,
    lalu menggabungkan kembali dengan newline per baris yang tersisa.
    """
    return re.sub(r'[^\x20-\x7E\n\r\u00C0-\u024F\u1E00-\u1EFF]', '', text)

def normalize_price(raw_price: str) -> int:
    """
    Menghapus “Rp” atau “IDR”, lalu mengambil hanya digit dan mengembalikan sebagai int.
    Jika string kosong atau tidak ada digit, kembalikan None.
    """
    if not raw_price:
        return None
    raw_price = raw_price.replace("Rp", "").replace("IDR", "").strip()
    # Contoh: "2,730,000.00" ➜ "2730000.00" ➜ ambil integer bagian
    # Ganti koma jadi kosong, hilangkan titik desimal
    cleaned = raw_price.replace(",", "").split(".")[0]
    # Hapus semua karakter kecuali digit
    digits = re.sub(r"[^\d]", "", cleaned)
    return int(digits) if digits else None

def extract_price_info(text: str) -> (int, int):
    """
    Mencari pola harga beli dan harga jual dari satu teks OCR (dalam satu string).
    - Mengembalikan tuple (harga_beli_total, harga_jual_total) dalam bentuk integer.
    - Jika tidak ditemukan, nilai akan None.
    """
    harga_beli = None
    harga_jual = None
    text_joined = text.replace('\n', ' ').replace('\r', ' ')

    beli_patterns = [
        r'\bHarga\s*Beli\s*Total\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bHarga\s*Beli\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bTotal\s*Beli\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bBiaya\s*Beli\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bBeli[\s:]*Rp?\s*([\d.,]+)',
        r'\bBeli[\s:]+([\d.,]+)',
        r'\bBeli\s+([\d.,]+)',
        r'\bHarga\s*Beli\s*Total\s*[:\-]?\s*(?:Rp)?\s*([\d.,]+)',
        r'\bHarga\s*Beli\s*[:\-]?\s*(?:Rp)?\s*([\d.,]+)',
        r'\bBeli\s*[:\-]?\s*Rp[\s.]?([\d.,]+)',
    ]


    jual_patterns = [
        r'\bHarga\s*Jual\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bHarga\s*Jual\s*([\d.,]+)',
        r'\bTotal\s*Harga\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bJual\s*Total\s*([\d.,]+)',
        r'\bJual\s*[:\-]?\s*Rp[\s.]?([\d.,]+)',
        r'\bTotal\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bHarga\s*per\s*(malam|mlm|night)\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'\bTarif\s*(?:IDR|Rp)?\s*([\d.,]+)',
        r'Rp\s*([\d.,]+)\s*/\s*mlm',
        r'Jual\s*([\d.,]+)',
        r'\bHarga\s*Jual\s*Total\s*[:\-]?\s*(?:Rp)?\s*([\d.,]+)',
        r'\bHarga\s*Jual\s*[:\-]?\s*(?:Rp)?\s*([\d.,]+)'
    ]

    # Coba pola harga beli
    for pat in beli_patterns:
        m = re.search(pat, text_joined, re.IGNORECASE)
        if m:
            harga_beli = normalize_price(m.group(1))
            break

    # Coba pola harga jual
    for pat in jual_patterns:
        m = re.search(pat, text_joined, re.IGNORECASE)
        if m:
            harga_jual = normalize_price(m.group(1))
            break

    return harga_beli, harga_jual

import re

def detect_document_type(text: str) -> str:
    """
    Deteksi apakah teks OCR milik 'kereta', 'pesawat', atau 'hotel'.
    Prioritas: kereta → pesawat → hotel. Jika tidak ada kata kunci, 'unknown'.
    """
    tl = text.lower()

    # Kereta
    if re.search(r'\b(kereta|ka\s+[a-z]+|stasiun|eksekutif|kai|kereta\s*api|kode\s*booking\s*[a-z0-9]{3,})', tl):
        return 'KERETA'

    # Pesawat
    if re.search(r'\b(flight|airlines|maskapai|pnr|kode\s*penerbangan|bandara|terminal|air\s*asia|airasia|citilink|garuda\s*Indonesia|jet|nam\s*air|batik\s*air|wings\s*air|susi\s*air|pelita\s*air|sriwijaya\s*air|lion\s*air)\b', tl):
        return 'PESAWAT'

    # Hotel
    if re.search(r'\b(hotel|check[-\s]?in|check[-\s]?out|tipe\s*kamar|nama\s*tamu)\b', tl):
        return 'HOTEL'

    return 'unknown'

# =================================
# === HOTEL PROCESSOR FUNCTIONS ===
# =================================

def load_city_list(filepath="city_list.txt") -> list:
    """
    Memuat daftar nama kota dari file. Tiap baris bisa diawali 'Kota ' atau 'Kabupaten ' (strip).
    Jika file tidak ditemukan, kembalikan list kosong dan cetak peringatan.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            cities = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Hapus prefiks 'Kota ' atau 'Kabupaten ' jika ada
                city_clean = re.sub(r'^(Kota|Kabupaten)\s+', '', line, flags=re.IGNORECASE)
                cities.append(city_clean)
            return cities
    except FileNotFoundError:
        print(f"[WARNING] File {filepath} tidak ditemukan. Daftar kota akan kosong.")
        return []

def extract_booking_code(text: str) -> str:
    """
    Ekstrak kode booking dari teks.
    Contoh pola yang dicari:
    - 'Order ID 123456'
    - 'ID Pesanan: 78910'
    - 'No. Pesanan Traveloka 112233'
    """
    m = re.search(
        r'(?:Order\s*ID|ID\s*Pesanan|Kode\s*Booking|No\.?\s*Pesanan(?:\s*Traveloka)?)\D*(\d+)', 
        text, 
        re.IGNORECASE
    )
    return m.group(1) if m else None


def extract_hotel_name(text_keep_lines: str) -> str:
    """
    Heuristik mengekstrak nama hotel dari blok teks (per baris).
    - Abaikan baris yang mengandung stopwords tertentu (alamat, jl, tipe kamar, dsb).
    - Jika baris sebelumnya mengandung 'Order ID' atau 'Itinerary', maka baris ini dianggap nama hotel.
    - Atau: jika baris berikutnya mengandung 'jl' atau 'jalan', baris ini dianggap nama hotel.
    """
    stopwords = [
        'alamat', 'jl', 'jalan', 'tipe kamar', 'check-in', 'check out',
        'makanan', 'nama tamu', 'jual', 'beli', 'order id', 'itinerary'
    ]
    lines = text_keep_lines.splitlines()
    for idx, line in enumerate(lines):
        lowercase = line.lower()
        if any(sw in lowercase for sw in stopwords):
            continue

        # Jika baris sebelumnya mengandung 'order id' atau 'itinerary'
        if idx > 0 and re.search(r'(order\s*id|itinerary)', lines[idx - 1], re.IGNORECASE):
            return line.strip()

        # Jika baris berikutnya mengandung 'jl' atau 'jalan'
        if idx + 1 < len(lines) and re.search(r'\b(jl|jalan)\b', lines[idx + 1], re.IGNORECASE):
            return line.strip()

    return None

def clean_hotel_name(name: str) -> str:
    """
    Jika perlu, bersihkan trailing karakter seperti ')'.
    """
    if not name:
        return None
    return name.rstrip(' )')

def extract_city(text: str, city_list: list) -> str:
    """
    Mencari kota dari teks dengan dua metode:
    1. Langsung mencari pola 'Kota Xxxx' atau 'Kabupaten Xxxx'
    2. Jika gagal, cari salah satu kota di city_list yang muncul di teks (case-insensitive).
    """
    m = re.search(r'\b(Kota|Kabupaten)\s+([A-Za-z\s]+)', text, re.IGNORECASE)
    if m:
        candidate = m.group(2).strip()
        # Cocokkan dengan daftar kota (case-insensitive)
        for city in city_list:
            if city.lower() == candidate.lower():
                return city
        return candidate

    tl = text.lower()
    for city in city_list:
        if city.lower() in tl:
            return city
    return None

def extract_room_count(text: str) -> int:
    """
    Mencari pola seperti '2 x Kamar' → kembalikan 2.
    Jika tidak ketemu, default 1.
    """
    m = re.search(r'(\d+)\s*[xX]\s*Kamar', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1

def extract_bf(text: str) -> str:
    """
    Menentukan apakah paket termasuk sarapan (BF) atau tidak (NBF).
    - Jika ditemukan keyword 'tidak termasuk sarapan', 'room only', → NBF
    - Jika ditemukan 'termasuk sarapan', 'breakfast included', → BF
    - Jika tidak jelas, return 'N/A'
    """
    tl = text.lower()
    nbf_patterns = [
        r'tidak\s+termasuk\s+sarapan',
        r'tidak.*sarapan',
        r'non[-\s]?breakfast',
        r'room\s+only',
        r'makanan\s*[:\-]?\s*(tidak ada|tidak tersedia|tidak disediakan|-)',
        r'makanan\s*[:\-]?\s*$'
    ]
    for pat in nbf_patterns:
        if re.search(r'makanan\s*[:\-]?\s*$', tl, re.MULTILINE) or 'makanan:' in tl and 'sarapan' not in tl:

            return 'NBF'

    bf_patterns = [
        r'termasuk\s+sarapan',
        r'sarapan\s+termasuk',
        r'free\s+breakfast',
        r'breakfast\s+included',
        r'makanan\s*[:\-]?\s*sarapan'
    ]
    for pat in bf_patterns:
        if re.search(pat, tl, re.MULTILINE):
            return 'BF'

    return 'N/A'

def extract_customer_names(text_keep_lines: str) -> list:
    """
    Mencari blok 'Nama Tamu:' dan mengumpulkan semua nama yang tertera hingga menemukan
    kata kunci selanjutnya (Check-in, Check-out, Permintaan, atau akhir blok).
    Format nama asumsi tiap baris di awal diberi nomor '1. Nama', '2. Nama', dsb.
    """
    m = re.search(
        r'Nama(?:\s+(?:Tamu|Penumpang|Customer))?\s*:?\s*((?:.*\n)+?)(?:Check[-\s]?in|Check[-\s]?out|Permintaan|$)',
        text_keep_lines,
        re.IGNORECASE
    )
    if not m:
        return []

    block = m.group(1).strip()
    names = []
    for line in block.splitlines():
        # Hapus prefix angka “1.” atau “2.”
        nm = re.sub(r'^\d+\.\s*', '', line.strip())
        if nm:
            names.append(nm)
    return names

def extract_dates_hotel(text: str) -> (datetime, datetime):
    """
    Mencari tanggal Check-in & Check-out di korpus teks. 
    Input contoh:
      'Check-in: 28 Mei 2025' (atau variasi spasi/strip).
      'Check-out: 30 Mei 2025'
    Mengembalikan tuple (checkin_datetime, checkout_datetime). 
    Jika salah satu tidak ditemukan, kembalikan None untuk yang tidak ada.
    """
    def parse_date_from_str(s: str) -> datetime:
        """
        Mencari pola tanggal '(\\d{1,2}) <nama_bulan> (\\d{4})' di s, 
        mengembalikan datetime atau None.
        """
        m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', s)
        if not m:
            return None

        day, month_str, year = m.groups()
        month_map = {
            'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2, 'mar': 3, 'maret': 3,
            'apr': 4, 'april': 4, 'may': 5, 'mei': 5, 'jun': 6, 'juni': 6,
            'jul': 7, 'juli': 7, 'aug': 8, 'agustus': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'oktober': 10, 'nov': 11, 'november': 11, 'dec': 12, 'desember': 12
        }
        m3 = month_map.get(month_str.strip().lower())
        if not m3:
            return None
        try:
            return datetime(int(year), m3, int(day))
        except ValueError:
            return None

    # Cari Check-in
    checkin = None
    m_in = re.search(r'Check[-\s]?in\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
    if m_in:
        checkin = parse_date_from_str(m_in.group(1))

    # Cari Check-out
    checkout = None
    m_out = re.search(r'Check[-\s]?out\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
    if m_out:
        checkout = parse_date_from_str(m_out.group(1))

    return checkin, checkout

def extract_duration_days_hotel(checkin: datetime, checkout: datetime) -> int:
    """
    Menghitung lama menginap dalam hari (jumlah malam).
    Jika salah satu None, return 1 (default).
    """
    if checkin and checkout:
        delta = checkout - checkin
        return max(delta.days, 1)
    return 1

def process_ocr_text_multiple(text: str) -> list:
    """
    Memproses OCR hotel, mengembalikan list of dict. 
    Dicetak satu per kamar/tamu.
    """
    city_list = load_city_list()
    cleaned = clean_text(text)
    cleaned_lines = clean_text_keep_lines(text)

    kode_booking = extract_booking_code(cleaned)
    hotel_name = clean_hotel_name(extract_hotel_name(cleaned_lines))
    durasi_night = None
    checkin_dt, checkout_dt = extract_dates_hotel(cleaned)
    durasi_night = extract_duration_days_hotel(checkin_dt, checkout_dt)

    jumlah_kamar = extract_room_count(cleaned)
    harga_beli_total, harga_jual_total = extract_price_info(cleaned)
    customer_names = extract_customer_names(cleaned_lines)

    # Debug print (optional)
    #print(f"[DEBUG] Jumlah kamar: {jumlah_kamar}, Nama Tamu: {customer_names}")

    # Hitung per-kamar
    harga_beli_per_kamar = (harga_beli_total // jumlah_kamar) if (harga_beli_total and jumlah_kamar) else None
    harga_jual_per_kamar = (harga_jual_total // jumlah_kamar) if (harga_jual_total and jumlah_kamar) else None

    # Sesuaikan panjang customer_names dengan jumlah_kamar
    if len(customer_names) < jumlah_kamar:
        customer_names += [None] * (jumlah_kamar - len(customer_names))
    elif len(customer_names) > jumlah_kamar:
        customer_names = customer_names[:jumlah_kamar]

    kota = extract_city(cleaned, city_list)
    bf_status = extract_bf(cleaned)

    results = []
    for idx in range(jumlah_kamar):
        nama_tamu = customer_names[idx] if idx < len(customer_names) else None
        data = {
            'Tgl Pemesanan': datetime.today().strftime('%Y-%m-%d'),
            'Tgl Berangkat': checkin_dt.strftime('%Y-%m-%d') if checkin_dt else '',
            'Kode Booking': kode_booking,
            'No Penerbangan / Nama Hotel / Kereta': hotel_name,
            'Durasi': f"{durasi_night} mlm" if durasi_night else None,
            'Nama Customer': nama_tamu,
            'Rute/Kota': kota,
            'Harga Beli': harga_beli_per_kamar,
            'Harga Jual': harga_jual_per_kamar,
            'Laba': None,
            'Tipe': tipe,
            'BF/NBF': bf_status,
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': ''
        }
        # Hitung laba dan persentase
        if data['Harga Beli'] is not None and data['Harga Jual'] is not None:
            data['Laba'] = data['Harga Jual'] - data['Harga Beli']
            if data['Harga Beli'] > 0:
                data['% Laba'] = f"{round((data['Laba'] / data['Harga Beli']) * 100, 2)}%"

        results.append(data)

    return results

# ===================================
import re
from datetime import datetime

# === PESAWAT PROCESSOR FUNCTIONS ===
# ===================================

def process_ocr_pesawat(text: str) -> list:
    """
    Memproses teks hasil OCR untuk tiket pesawat.
    Mengembalikan list of dict berisi detail pemesanan.
    """
    cleaned = text.strip()

    # 1. Kode Booking / PNR
    kode_booking = None
    m_code = re.search(r"(?:PNR|Kode\s*booking)[:\-]?\s*([A-Z0-9]{5,8})", cleaned, re.IGNORECASE)
    if m_code:
        kode_booking = m_code.group(1)

    # 2. Nama Maskapai + Kode Penerbangan (IATA + nomor)
    penerbangan = None
    m_maskapai = re.search(r"\b(garuda|citilink|lion|batik|airasia|super\s*air\s*jet|pelita|nam\s*air)\b.*?([A-Z]{2})[- ]?(\d{2,4})", cleaned, re.IGNORECASE)
    if m_maskapai:
        penerbangan = m_maskapai.group(2) + m_maskapai.group(3)
    else:
        # fallback, ambil pola umum XX123
        m_fallback = re.search(r"\b([A-Z]{2})[- ]?(\d{2,4})\b", cleaned)
        if m_fallback:
            penerbangan = m_fallback.group(1) + m_fallback.group(2)

    # 3. Durasi jam (berangkat - tiba)
    durasi = None
    m_times = re.findall(r"(\b\d{1,2}[:.]\d{2}\b(?:AM|PM)?)", cleaned, re.IGNORECASE)
    if len(m_times) >= 2:
        durasi = f"{m_times[0]} - {m_times[1]}"

    # 4. Rute bandara (kode IATA)
    iata_codes = re.findall(r"\(([A-Z]{3})\)", cleaned)
    excluded = {'PNR', 'ECO', 'VIP', 'BUS', 'TBA'}
    valid_routes = [code for code in iata_codes if code not in excluded]
    rute_final = None
    if len(valid_routes) >= 2:
        rute_final = f"{valid_routes[0]} - {valid_routes[1]}"

    # 5. Tanggal Berangkat
    tgl_berangkat = ''
    # dua format: '10 Jun 2025' atau 'Jun 10, 2025'
    m_date = re.search(
        r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b|\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b",
        cleaned
    )
    if m_date:
        # grup 1-3 untuk format DMY, 4-6 untuk MDY
        if m_date.group(1):
            day, month_str, year = m_date.group(1), m_date.group(2), m_date.group(3)
        else:
            month_str, day, year = m_date.group(4), m_date.group(5), m_date.group(6)

        month_map = {
            'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2, 'mar': 3, 'maret': 3,
            'apr': 4, 'april': 4, 'mei': 5, 'jun': 6, 'juni': 6,
            'jul': 7, 'juli': 7, 'aug': 8, 'agustus': 8, 'sep': 9, 'september': 9,
            'okt': 10, 'oktober': 10, 'nov': 11, 'november': 11, 'des': 12, 'desember': 12
        }
        mm = month_map.get(month_str.lower()[:3])
        if mm:
            try:
                tgl_berangkat = datetime(int(year), mm, int(day)).strftime('%Y-%m-%d')
            except ValueError:
                tgl_berangkat = ''

    # 6. Harga Beli dan Harga Jual
    harga_beli = harga_jual = None
    # regex diperbarui: cari 'Beli' atau 'BELI' tanpa memperhatikan urutan kata
    hb_match = re.search(r"(?:Beli|HB|Harga\s*Beli)[:\s]*[Rp\.]*([\d,\.]+)", cleaned, re.IGNORECASE)
    hj_match = re.search(r"(?:Jual|HJ|Harga\s*Jual)[:\s]*[Rp\.]*([\d,\.]+)", cleaned, re.IGNORECASE)
    if hb_match:
        harga_beli = int(re.sub(r"[^\d]", "", hb_match.group(1)))
    if hj_match:
        harga_jual = int(re.sub(r"[^\d]", "", hj_match.group(1)))

    # 7. Nama penumpang
    names = []
    m_cust = re.search(
        r"nama\s*(?:penumpang|customer|tamu)?\s*[:\-]?\s*((?:.*\n?)+?)(?:\n\s*\n|Harga|Check[-\s]?in|Check[-\s]?out|$)",
        cleaned,
        re.IGNORECASE
    )
    if m_cust:
        raw_block = m_cust.group(1)
        lines = [line.strip() for line in raw_block.strip().splitlines()]
        for line in lines:
            match = re.match(r"^\d+\.\s*(.+)", line)
            if match:
                name = re.sub(r"\b(Tn|Ny|Nn|Mr|Mrs|Ms)\.?\s+", "", match.group(1)).strip()
                if name:
                    names.append(name)
    if not names:
        fallback_names = re.findall(r"^\d+\.\s*(.+)", cleaned, re.MULTILINE)
        names = [re.sub(r"\b(Tn|Ny|Nn|Mr|Mrs|Ms)\.?\s+", "", n).strip() for n in fallback_names]
        if not names:
            names = [None]

    # 8. Hitung harga per orang dan laba
    per_orang_beli = harga_beli // len(names) if harga_beli else None
    per_orang_jual = harga_jual // len(names) if harga_jual else None

    results = []
    for name in names:
        laba = None
        persen_laba = ''
        if per_orang_beli and per_orang_jual:
            laba = per_orang_jual - per_orang_beli
            if per_orang_beli > 0:
                persen_laba = f"{round((laba / per_orang_beli) * 100, 2)}%"

        entry = {
            'Tgl Pemesanan': datetime.today().strftime('%Y-%m-%d'),
            'Tgl Berangkat': tgl_berangkat,
            'Kode Booking': kode_booking,
            'No Penerbangan / Nama Hotel / Kereta': penerbangan,
            'Durasi': durasi,
            'Nama Customer': name,
            'Rute/Kota': rute_final,
            'Harga Beli': per_orang_beli,
            'Harga Jual': per_orang_jual,
            'Laba': laba,
            'Tipe': tipe,
            'BF/NBF': '',
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': persen_laba
        }
        results.append(entry)

    return results


# ===================================
# === KERETA PROCESSOR FUNCTIONS ===
# ===================================

import re

def extract_kereta_passengers(text_keep_lines: str) -> list:
    m_train = re.search(r'^(KA\s+[A-Za-z ]+$)', text_keep_lines, re.MULTILINE) #hanya mengambil 1 baris setelah KA
    kereta_name = m_train.group(1).strip() if m_train else None

    # Tangkap baris seperti: "1. Nama Penumpang    EKO 7/8A"
    pattern = re.compile(
        r'^\d+\.\s*(.+?)\s+((?:EKS|BIS|EKO|PRE|PAN|KLS)\s*\d+\s*[\/\\]?\s*\d*[A-Za-z]?)\s*$', # <--- Perubahan di sini!
    re.IGNORECASE | re.MULTILINE
    )
    result = []
    for m in pattern.finditer(text_keep_lines):
        name = m.group(1).strip()
        seat = m.group(2).strip()
        full_info = f"{kereta_name}  {seat}" if kereta_name else seat
        result.append((name, full_info))
    return result


def process_ocr_kereta(text: str) -> list:
    """
    Memproses OCR teks tiket kereta, mengembalikan satu dict per penumpang. 
    Field yang dihasilkan serupa dengan hotel/pesawat, namun:
    - 'No Penerbangan / Nama Hotel / Kereta' diisi “KA <NamaKereta>  EKS xx/xA”
    - 'Nama Customer' diisi nama penumpang
    - Rute: misal 'SLO - GMR'
    - Durasi: jam berangkat – jam tiba
    - Tanggal berangkat diambil dari pola '28 Mei 2025'
    - Harga beli/jual dibagi per penumpang jika total diketahui.
    """
    cleaned = clean_text(text)
    cleaned_lines = clean_text_keep_lines(text)
    print(f"DEBUG Kereta Cleaned Text:\n{cleaned}\n---", flush=True)
    print(f"DEBUG Kereta Cleaned Lines Text:\n{cleaned_lines}\n---", flush=True)

    # --- Kode Booking ---
    m_kode = re.search(r'kode\s*booking\s*[:\-]?\s*([A-Z0-9]+)', cleaned, re.IGNORECASE)
    kode_booking = m_kode.group(1) if m_kode else None

    # --- Rute stasiun (asal dan tujuan) ---
    stasiun_asal = None
    stasiun_tujuan = None
     # --- Ambil rute dari stasiun: (SGU) - (GMR) ---
    stasiun_asal = re.search(r'Pergi.*?\(([A-Z]{2,3})\)', cleaned_lines, re.DOTALL | re.IGNORECASE)
    stasiun_tujuan = re.search(r'Tiba.*?\(([A-Z]{2,3})\)', cleaned_lines, re.DOTALL | re.IGNORECASE)
    rute = f"{stasiun_asal.group(1)} - {stasiun_tujuan.group(1)}" if stasiun_asal and stasiun_tujuan else None

    # --- Jam berangkat dan tiba (durasi) ---
    durasi = None
    m_jb = re.search(r'pergi.*?(\d{1,2}[:.]\d{2})', cleaned, re.IGNORECASE)
    m_jt = re.search(r'tiba.*?(\d{1,2}[:.]\d{2})', cleaned, re.IGNORECASE)
    if m_jb and m_jt:
        durasi = f"{m_jb.group(1)} - {m_jt.group(1)}"
    else:
        # fallback: cari pola jam lain
        m_time = re.search(r'(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})', cleaned)
        if m_time:
            durasi = f"{m_time.group(1)} - {m_time.group(2)}"

    # --- Tanggal berangkat ---
    tgl_berangkat = ''
    # Pola '28 Mei 2025' (mungkin setelah “Rab,” atau “berangkat”)
    m_tg = re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b', cleaned)
    if m_tg:
        day, month_str, year = m_tg.groups()
        month_map = {
            'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2,
            'mar': 3, 'maret': 3, 'apr': 4, 'april': 4,
            'mei': 5, 'jun': 6, 'juni': 6,
            'jul': 7, 'juli': 7, 'aug': 8, 'agustus': 8,
            'sep': 9, 'september': 9, 'okt': 10, 'oktober': 10,
            'nov': 11, 'november': 11, 'des': 12, 'desember': 12
        }
        mm = month_map.get(month_str.lower()[:3])
        if mm:
            try:
                tgl_berangkat = datetime(int(year), mm, int(day)).strftime('%Y-%m-%d')
            except ValueError:
                tgl_berangkat = ''

    # --- Harga total beli/jual ---
    harga_beli_total, harga_jual_total = extract_price_info(cleaned)

    # --- Data penumpang: nama + kode EKS ---
    passenger_data = extract_kereta_passengers(cleaned_lines)
    jumlah_penumpang = len(passenger_data)

    # Hitung per-penumpang jika total diketahui
    harga_beli_per = harga_beli_total // jumlah_penumpang if harga_beli_total and jumlah_penumpang else None
    harga_jual_per = (harga_jual_total // jumlah_penumpang) if (harga_jual_total and jumlah_penumpang) else None

    results = []
    for (nama_penumpang, kereta_info) in passenger_data:
        laba = None
        persen_laba = ''
        if harga_beli_per is not None and harga_jual_per is not None:
            laba = harga_jual_per - harga_beli_per
            if harga_beli_per > 0:
                persen_laba = f"{round((laba / harga_beli_per) * 100, 2)}%"

        data = {
            'Tgl Pemesanan': datetime.today().strftime('%Y-%m-%d'),
            'Tgl Berangkat': tgl_berangkat,
            'Kode Booking': kode_booking,
            'No Penerbangan / Nama Hotel / Kereta': kereta_info,
            'Durasi': durasi,
            'Nama Customer': nama_penumpang,
            'Rute/Kota': rute,
            'Harga Beli': harga_beli_per,
            'Harga Jual': harga_jual_per,
            'Laba': laba,
            'Tipe': tipe,
            'BF/NBF': '',
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': persen_laba
        }
        results.append(data)

    return results

# ===================================
# === MASTER PROCESSOR FUNCTION ===
# ===================================

def process_ocr_unified(text: str) -> list:
    """
    Mendeteksi tipe dokumen (hotel/pesawat/kereta) lalu memanggil fungsi processor yang sesuai.
    Jika unknown, kembalikan list kosong.
    """
    tipe = detect_document_type(text)
    print(f"DEBUG: detect_document_type result: '{tipe}'", flush=True)
    if tipe == 'HOTEL':
        return process_ocr_text_multiple(text)
    elif tipe == 'PESAWAT':
        return process_ocr_pesawat(text)
    elif tipe == 'KERETA':
        return process_ocr_kereta(text)
    else:
        print("[INFO] Jenis dokumen tidak dikenali sebagai hotel, pesawat, atau kereta.")
        return []

# ===============================================
# === BAGIAN TEST (jika dijalankan sebagai main) ===
# ===============================================

if __name__ == "__main__":
    # Contoh: baca dari file OCR
    with open("ocr_output.txt", "r", encoding="utf-8") as f:
        ocr_text = f.read()

    results = process_ocr_unified(ocr_text)
    for idx, entry in enumerate(results, start=1):
        print(f"\n--- Entry {idx} ---")
        for k, v in entry.items():
            print(f"{k}: {v}")

