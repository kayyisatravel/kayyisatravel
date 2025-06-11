import re
from datetime import datetime

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
    Fokus hanya pada pembersihan spasi berlebih dan karakter non-print (kecuali newline).
    """
    # Menghapus karakter non-ASCII yang bukan newline atau carriage return
    # Mengizinkan karakter Unicode umum (misalnya di luar ASCII) jika diperlukan
    cleaned = re.sub(r'[^\x00-\x7F\n\r]+', ' ', text) # Hapus non-ASCII, ganti dengan spasi
    cleaned_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return '\n'.join(cleaned_lines)

def normalize_price(raw_price: str) -> int:
    """
    Menghapus “Rp” atau “IDR”, lalu mengambil hanya digit dan mengembalikan sebagai int.
    Jika string kosong atau tidak ada digit, kembalikan None.
    """
    if not raw_price:
        return None
    
    # Hapus spasi, simbol mata uang, dan tanda ribuan (titik atau koma, tergantung lokal)
    # Kemudian ambil bagian sebelum desimal jika ada
    cleaned = re.sub(r'[Rr][Pp]\s*|\bIDR\b|\s+|\.', '', raw_price) # Hapus Rp, IDR, spasi, titik
    cleaned = cleaned.replace(',', '') # Hapus koma (untuk ribuan)
    
    # Jika ada desimal (koma atau titik), ambil bagian integer
    if '.' in cleaned:
        cleaned = cleaned.split('.')[0]
    elif ',' in cleaned: # Jika koma digunakan sebagai desimal
        cleaned = cleaned.split(',')[0]
        
    digits = re.sub(r"[^\d]", "", cleaned) # Hapus semua kecuali digit
    return int(digits) if digits else None

def extract_price_info(text: str) -> (int, int):
    """
    Mencari pola harga beli dan harga jual dari satu teks OCR (dalam satu string).
    - Mengembalikan tuple (harga_beli_total, harga_jual_total) dalam bentuk integer.
    - Jika tidak ditemukan, nilai akan None.
    """
    harga_beli = None
    harga_jual = None
    text_lower = text.lower().replace('\n', ' ').replace('\r', ' ')

    # Pola untuk harga beli (lebih spesifik)
    beli_patterns = [
        r'\bharga\s*beli\s*total\s*(?:idr|rp)?\s*([\d.,]+)',
        r'\b(harga\s*beli|hb|beli)\s*[:\s]*[rp\.]*([\d.,]+)', # Menangkap 'Beli:' atau 'HB'
        r'\b(total\s*beli|biaya\s*beli)\s*(?:idr|rp)?\s*([\d.,]+)',
    ]

    # Pola untuk harga jual (lebih spesifik)
    jual_patterns = [
        r'\bharga\s*jual\s*total\s*(?:idr|rp)?\s*([\d.,]+)',
        r'\b(harga\s*jual|hj|jual)\s*[:\s]*[rp\.]*([\d.,]+)', # Menangkap 'Jual:' atau 'HJ'
        r'\b(total\s*harga|total\s*jual)\s*(?:idr|rp)?\s*([\d.,]+)',
        r'\b(tarif)\s*(?:idr|rp)?\s*([\d.,]+)',
        r'(?:rp)?\s*([\d.,]+)\s*/\s*mlm' # Untuk harga per malam (hotel)
    ]

    # Coba pola harga beli
    for pat in beli_patterns:
        m = re.search(pat, text_lower)
        if m:
            # Group 1 jika ada kata kunci, Group 2 jika ada kata kunci yang lebih spesifik
            # Pastikan mengambil group yang benar sesuai pola
            harga_beli = normalize_price(m.group(m.lastindex)) # Ambil grup terakhir yang cocok
            break

    # Coba pola harga jual
    for pat in jual_patterns:
        m = re.search(pat, text_lower)
        if m:
            harga_jual = normalize_price(m.group(m.lastindex)) # Ambil grup terakhir yang cocok
            break
            
    # Fallback untuk total (jika tidak ada keyword "jual") - hindari tumpang tindih
    if harga_jual is None:
        m_total_fallback = re.search(r'\b(total)\s*(?:idr|rp)?\s*([\d.,]+)', text_lower)
        if m_total_fallback:
            harga_jual = normalize_price(m_total_fallback.group(2))

    return harga_beli, harga_jual

def extract_general_booking_code(text: str) -> str:
    """
    Fungsi universal untuk mengekstrak kode booking (baik hotel, pesawat, atau kereta).
    Mencari pola umum seperti PNR, Order ID, Kode Booking, No. Pesanan.
    """
    m = re.search(
        r"(?:PNR|Kode\s*booking|Booking\s*Code|Order\s*ID|ID\s*Pesanan|No\.?\s*Pesanan(?:\s*Traveloka)?)[ :\-\_]*([A-Z0-9]{5,10})\b", 
        text, 
        re.IGNORECASE
    )
    return m.group(1).upper() if m else None

def parse_date_from_str(s: str) -> datetime:
    """
    Mencari pola tanggal '(\\d{1,2}) <nama_bulan> (\\d{4})' atau '<nama_bulan> (\\d{1,2}), (\\d{4})' di s,
    mengembalikan datetime atau None.
    """
    month_map = {
        'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2, 'mar': 3, 'maret': 3,
        'apr': 4, 'april': 4, 'mei': 5, 'jun': 6, 'juni': 6,
        'jul': 7, 'juli': 7, 'aug': 8, 'agustus': 8, 'sep': 9, 'september': 9,
        'okt': 10, 'oktober': 10, 'nov': 11, 'november': 11, 'des': 12, 'desember': 12
    }
    
    # Format: DD Mon YYYY
    m_dmy = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', s, re.IGNORECASE)
    if m_dmy:
        day, month_str, year = m_dmy.groups()
        mm = month_map.get(month_str.lower()[:3])
        if mm:
            try:
                return datetime(int(year), mm, int(day))
            except ValueError:
                pass

    # Format: Mon DD, YYYY
    m_mdy = re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', s, re.IGNORECASE)
    if m_mdy:
        month_str, day, year = m_mdy.groups()
        mm = month_map.get(month_str.lower()[:3])
        if mm:
            try:
                return datetime(int(year), mm, int(day))
            except ValueError:
                pass
                
    return None

## B. HOTEL PROCESSOR FUNCTIONS

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

def extract_hotel_name(text_keep_lines: str) -> str:
    """
    Heuristik mengekstrak nama hotel dari blok teks (per baris).
    - Abaikan baris yang mengandung stopwords tertentu (alamat, jl, tipe kamar, dsb).
    - Prioritaskan baris setelah 'Order ID' atau 'Itinerary'.
    - Prioritaskan baris sebelum 'jl' atau 'jalan'.
    - Coba baris paling atas yang tidak mengandung stopwords.
    """
    stopwords = [
        'alamat', 'jl', 'jalan', 'tipe kamar', 'check-in', 'check out', 'makanan', 
        'nama tamu', 'jual', 'beli', 'order id', 'itinerary', 'total', 'harga', 
        'tanggal', 'jam', 'pnr', 'kode booking', 'no. pesanan', 'hotel' # Tambah stopwords
    ]
    lines = [line.strip() for line in text_keep_lines.splitlines() if line.strip()]

    # Pencarian berbasis konteks (sebelum/sesudah kata kunci)
    for idx, line in enumerate(lines):
        lowercase = line.lower()
        
        # Prioritas 1: Baris setelah "Order ID" atau "Itinerary"
        if idx > 0 and re.search(r'(order\s*id|itinerary|pemesanan)', lines[idx - 1], re.IGNORECASE):
            if not any(sw in lowercase for sw in stopwords): # Pastikan bukan stopwords
                return line.strip()

        # Prioritas 2: Baris sebelum "jl" atau "jalan"
        if idx + 1 < len(lines) and re.search(r'\b(jl|jalan)\b', lines[idx + 1], re.IGNORECASE):
            if not any(sw in lowercase for sw in stopwords):
                return line.strip()
    
    # Prioritas 3: Coba baris paling atas yang bersih dari stopwords dan bukan angka
    for line in lines:
        lowercase = line.lower()
        if not any(sw in lowercase for sw in stopwords) and not line.strip().isdigit():
            # Cek jika baris terlihat seperti kode pos, telepon, atau harga
            if not re.search(r'^\d{5,}$|^\+?\d{7,}|[\d.,]{4,}', line): # Angka panjang, telepon, harga
                 return line.strip()

    return None

def clean_hotel_name(name: str) -> str:
    """
    Jika perlu, bersihkan trailing karakter seperti ')', tanda baca, atau kata-kata umum.
    """
    if not name:
        return None
    # Hapus spasi di akhir, tanda kurung, titik, koma
    name = re.sub(r'[)\.,]+$', '', name.strip())
    # Hapus "Hotel" jika ada di akhir dan bukan bagian dari nama unik
    name = re.sub(r'\bHotel\b$', '', name, flags=re.IGNORECASE).strip()
    return name if name else None

def extract_city(text: str, city_list: list) -> str:
    """
    Mencari kota dari teks dengan dua metode:
    1. Langsung mencari pola 'Kota Xxxx' atau 'Kabupaten Xxxx'
    2. Jika gagal, cari salah satu kota di city_list yang muncul di teks (case-insensitive, word boundary).
    """
    text_lower = text.lower()
    
    # Metode 1: Cari pola 'Kota Xxxx' atau 'Kabupaten Xxxx'
    m = re.search(r'\b(kota|kabupaten)\s+([a-z\s]+)', text_lower)
    if m:
        candidate = m.group(2).strip()
        # Cocokkan dengan daftar kota (case-insensitive)
        for city in city_list:
            if city.lower() == candidate:
                return city
        return candidate # Jika tidak ada di city_list tapi polanya kuat

    # Metode 2: Cari salah satu kota di city_list
    # Urutkan city_list dari yang terpanjang agar nama kota multi-kata cocok lebih dulu
    sorted_cities = sorted(city_list, key=len, reverse=True)
    for city in sorted_cities:
        # Gunakan word boundary untuk menghindari pencocokan parsial (misal: "solo" di "konsolo")
        if re.search(r'\b' + re.escape(city.lower()) + r'\b', text_lower):
            return city
            
    return None

def extract_room_count(text: str) -> int:
    """
    Mencari pola seperti '2 x Kamar' → kembalikan 2.
    Jika tidak ketemu, default 1.
    """
    m = re.search(r'(\d+)\s*(x|kali)\s*(kamar|room)', text, re.IGNORECASE)
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
    
    # Pola NBF (lebih spesifik)
    nbf_patterns = [
        r'\b(tidak\s+termasuk\s+sarapan|tidak.*sarapan|non[-\s]?breakfast|room\s+only|tanpa\s+sarapan)\b',
        r'\bmakanan\s*[:\-]?\s*(tidak ada|tidak tersedia|tidak disediakan|[-]|x)\b' # Pola untuk "makanan: -"
    ]
    for pat in nbf_patterns:
        if re.search(pat, tl):
            return 'NBF'

    # Pola BF (lebih spesifik)
    bf_patterns = [
        r'\b(termasuk\s+sarapan|sarapan\s+termasuk|free\s+breakfast|breakfast\s+included|dengan\s+sarapan)\b',
        r'\bmakanan\s*[:\-]?\s*sarapan\b'
    ]
    for pat in bf_patterns:
        if re.search(pat, tl):
            return 'BF'

    # Jika ada keyword "makanan" tapi tidak ada "sarapan" di dekatnya (ambigu)
    if re.search(r'\bmakanan\b', tl) and not re.search(r'\b(sarapan|breakfast)\b', tl):
        return 'N/A' # Ini bisa jadi "N/A" atau default ke "NBF" tergantung aturan bisnis

    return 'N/A'

def extract_customer_names(text_keep_lines: str) -> list:
    """
    Mencari blok 'Nama Tamu:' dan mengumpulkan semua nama yang tertera hingga menemukan
    kata kunci selanjutnya (Check-in, Check-out, Permintaan, Harga, Jual, Beli, atau akhir blok).
    Mendukung format nama dengan atau tanpa penomoran '1. Nama', '2. Nama', dsb.
    """
    names = []
    # Pola untuk menangkap blok teks setelah "Nama (Tamu/Penumpang/Customer):"
    m = re.search(
        r'Nama(?:\s+(?:Tamu|Penumpang|Customer))?\s*[:\-]?\s*((?:[^\n]*\n?)+?)(?=\n\s*(?:Check[-\s]?in|Check[-\s]?out|Permintaan|Harga|Jual|Beli|Total|No\.?\s*Invoice|\d+\.\s*[\w\s]+:\s*\d+|Pembayaran)|$)',
        text_keep_lines,
        re.IGNORECASE | re.DOTALL # re.DOTALL agar '.' cocok dengan newline
    )
    
    if m:
        raw_block = m.group(1).strip()
        lines = [line.strip() for line in raw_block.splitlines() if line.strip()] # Filter baris kosong
        
        for line in lines:
            # Hapus prefix angka "1." atau "2."
            name_match = re.match(r'^\d+\.\s*(.+)', line) 
            if name_match:
                name = name_match.group(1).strip()
            else:
                name = line.strip() # Jika tidak ada penomoran

            # Hapus gelar seperti Tn, Ny, Mr, Mrs, Ms, Sdr
            name = re.sub(r"\b(Tn|Ny|Nn|Mr|Mrs|Ms|Sdr|Bapak|Ibu)\.?\s+", "", name, flags=re.IGNORECASE).strip()
            
            # Tambahkan nama hanya jika bukan string kosong atau hanya angka
            if name and not name.isdigit():
                names.append(name)
    
    return names if names else []

def extract_dates_hotel(text: str) -> (datetime, datetime):
    """
    Mencari tanggal Check-in & Check-out di korpus teks.
    Mengembalikan tuple (checkin_datetime, checkout_datetime).
    Jika salah satu tidak ditemukan, kembalikan None untuk yang tidak ada.
    """
    checkin = None
    m_in = re.search(r'Check[-\s]?in\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
    if m_in:
        checkin = parse_date_from_str(m_in.group(1))

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
    cleaned = clean_text(text) # Untuk pencarian global (regex tanpa newline)
    cleaned_lines = clean_text_keep_lines(text) # Untuk ekstraksi berbasis baris (nama, hotel name)

    kode_booking = extract_general_booking_code(cleaned)
    hotel_name = clean_hotel_name(extract_hotel_name(cleaned_lines))
    
    checkin_dt, checkout_dt = extract_dates_hotel(cleaned)
    durasi_night = extract_duration_days_hotel(checkin_dt, checkout_dt)

    jumlah_kamar = extract_room_count(cleaned)
    harga_beli_total, harga_jual_total = extract_price_info(cleaned)
    customer_names = extract_customer_names(cleaned_lines)
    
    kota = extract_city(cleaned, city_list)
    bf_status = extract_bf(cleaned)

    # Sesuaikan panjang customer_names dengan jumlah_kamar
    # Jika jumlah_kamar lebih besar dari jumlah nama, tambahkan None
    # Jika jumlah_kamar lebih kecil, potong daftar nama
    if len(customer_names) < jumlah_kamar:
        customer_names.extend([None] * (jumlah_kamar - len(customer_names)))
    elif len(customer_names) > jumlah_kamar and jumlah_kamar > 0: # Cek jumlah_kamar > 0 untuk menghindari pemotongan nama jadi []
        customer_names = customer_names[:jumlah_kamar]
    
    # Jika tidak ada nama dan jumlah kamar 1, gunakan None sebagai nama default
    if not customer_names and jumlah_kamar == 1:
        customer_names = [None]
    elif not customer_names and jumlah_kamar > 1: # Jika tidak ada nama, tapi banyak kamar, isi dengan None
        customer_names = [None] * jumlah_kamar


    # Hitung harga per-kamar
    harga_beli_per_kamar = (harga_beli_total // jumlah_kamar) if (harga_beli_total is not None and jumlah_kamar > 0) else None
    harga_jual_per_kamar = (harga_jual_total // jumlah_kamar) if (harga_jual_total is not None and jumlah_kamar > 0) else None

    results = []
    # Iterasi berdasarkan jumlah kamar untuk membuat entri
    for idx in range(jumlah_kamar if jumlah_kamar > 0 else 1): # Pastikan setidaknya satu iterasi jika jumlah_kamar = 0 atau nama kosong
        nama_tamu = customer_names[idx] if idx < len(customer_names) else None
        
        laba = None
        persen_laba = ''
        if harga_beli_per_kamar is not None and harga_jual_per_kamar is not None:
            laba = harga_jual_per_kamar - harga_beli_per_kamar
            if harga_beli_per_kamar > 0:
                persen_laba = f"{round((laba / harga_beli_per_kamar) * 100, 2)}%"

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
            'Laba': laba,
            'BF/NBF': bf_status,
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': persen_laba
        }
        results.append(data)

    return results

## C. PESAWAT PROCESSOR FUNCTIONS

def process_ocr_pesawat(text: str) -> list:
    """
    Memproses teks hasil OCR untuk tiket pesawat.
    Mengembalikan list of dict berisi detail pemesanan.
    """
    cleaned = text.strip()
    tl = cleaned.lower()

    # 1. Kode Booking / PNR (menggunakan fungsi universal)
    kode_booking = extract_general_booking_code(cleaned)

    # 2. Nama Maskapai + Kode Penerbangan (IATA + nomor)
    penerbangan = None
    maskapai_keywords = r"(garuda|citilink|lion|batik|airasia|super\s*air\s*jet|pelita|sriwijaya|nam\s*air|wings\s*air|susi\s*air)"
    
    # Pola pertama: Cari maskapai, lalu kode penerbangan
    m_maskapai = re.search(rf"{maskapai_keywords}.*?([A-Z]{2}[- ]?\d{{2,4}})\b", tl, re.IGNORECASE)
    if m_maskapai:
        penerbangan = m_maskapai.group(2).replace(" ", "").upper()
    else:
        # Fallback: Cari pola XX123 di mana saja
        m_fallback = re.search(r"\b([A-Z]{2}[- ]?\d{2,4})\b", tl)
        if m_fallback:
            penerbangan = m_fallback.group(1).replace(" ", "").upper()

    # 3. Waktu Berangkat dan Tiba (bukan durasi)
    waktu_berangkat_tiba = None
    # Prioritaskan waktu setelah 'Berangkat' dan 'Tiba'/'Datang'
    m_berangkat_time = re.search(r'(?:berangkat|depart)\s*.*?(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?)', tl, re.IGNORECASE)
    m_tiba_time = re.search(r'(?:tiba|datang|arrive)\s*.*?(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?)', tl, re.IGNORECASE)

    if m_berangkat_time and m_tiba_time:
        t_berangkat = m_berangkat_time.group(1).replace('.', ':').replace(' ', '').upper()
        t_tiba = m_tiba_time.group(1).replace('.', ':').replace(' ', '').upper()
        waktu_berangkat_tiba = f"{t_berangkat} - {t_tiba}"
    else: # Fallback ke pola jam umum (jika tidak ada keyword berangkat/tiba)
        m_times_general = re.findall(r"(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?)", tl, re.IGNORECASE)
        if len(m_times_general) >= 2:
            t_berangkat = m_times_general[0].replace('.', ':').replace(' ', '').upper()
            t_tiba = m_times_general[1].replace('.', ':').replace(' ', '').upper()
            waktu_berangkat_tiba = f"{t_berangkat} - {t_tiba}"

    # 4. Rute bandara (kode IATA)
    iata_codes_raw = re.findall(r"\b([A-Z]{3})\b", tl)
    # Perluas daftar excluded dengan common non-airport codes
    excluded_iata = {'PNR', 'ECO', 'VIP', 'BUS', 'TBA', 'STD', 'DPR', 'JKT', 'KUL', 'SIN', 'IDR', 'USD'} # Tambahkan lebih banyak
    
    valid_routes = [code.upper() for code in iata_codes_raw if code.upper() not in excluded_iata]
    rute_final = None
    
    # Prioritaskan rute berpasangan seperti CGK-SUB atau dari konteks 'dari'/'ke'
    m_rute_dash = re.search(r"\b([A-Z]{3})[- ]?([A-Z]{3})\b", tl) # CGK-SUB atau CGK SUB
    if m_rute_dash:
        from_iata = m_rute_dash.group(1).upper()
        to_iata = m_rute_dash.group(2).upper()
        if from_iata not in excluded_iata and to_iata not in excluded_iata:
            rute_final = f"{from_iata} - {to_iata}"
    
    # Fallback jika tidak ada rute dash, ambil 2 IATA valid pertama
    if not rute_final and len(valid_routes) >= 2:
        rute_final = f"{valid_routes[0]} - {valid_routes[1]}"

    # 5. Tanggal Berangkat
    tgl_berangkat_str = ''
    # Prioritaskan tanggal setelah 'Berangkat', 'Departs', atau 'Tanggal'
    m_date_after_keyword = re.search(
        r"(?:berangkat|depart|tanggal)\s*[:,\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", 
        tl,
        re.IGNORECASE
    )
    if m_date_after_keyword:
        tgl_berangkat_dt = parse_date_from_str(m_date_after_keyword.group(1))
        if tgl_berangkat_dt:
            tgl_berangkat_str = tgl_berangkat_dt.strftime('%Y-%m-%d')
    else: # Fallback ke pola tanggal umum jika tidak ada keyword
        m_date_general = re.search(
            r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})|([A-Za-z]+\s+\d{1,2},\s*\d{4})", # DD Mon YYYY atau Mon DD, YYYY
            tl
        )
        if m_date_general:
            date_str_to_parse = m_date_general.group(1) if m_date_general.group(1) else m_date_general.group(2)
            tgl_berangkat_dt = parse_date_from_str(date_str_to_parse)
            if tgl_berangkat_dt:
                tgl_berangkat_str = tgl_berangkat_dt.strftime('%Y-%m-%d')

    # 6. Harga Beli dan Harga Jual (menggunakan fungsi universal)
    harga_beli, harga_jual = extract_price_info(cleaned)

    # 7. Nama penumpang
    names = []
    # Re-use extract_customer_names dari modul hotel, atau modifikasi sedikit jika perlu
    # Asumsi Nama Penumpang: di pesawat juga pakai format yang mirip (1. Nama, 2. Nama)
    names = extract_customer_names(cleaned) # Menggunakan clean_text untuk nama juga bisa, tapi lebih baik clean_text_keep_lines

    if not names:
        names = [None] # Pastikan minimal satu entri jika tidak ada nama

    # 8. Hitung harga per orang dan laba
    # Menggunakan None jika harga atau jumlah penumpang tidak valid
    per_orang_beli = harga_beli // len(names) if harga_beli is not None and len(names) > 0 else None
    per_orang_jual = harga_jual // len(names) if harga_jual is not None and len(names) > 0 else None

    results = []
    for name in names:
        laba = None
        persen_laba = ''
        if per_orang_beli is not None and per_orang_jual is not None:
            laba = per_orang_jual - per_orang_beli
            if per_orang_beli > 0:
                persen_laba = f"{round((laba / per_orang_beli) * 100, 2)}%"

        entry = {
            'Tgl Pemesanan': datetime.today().strftime('%Y-%m-%d'),
            'Tgl Berangkat': tgl_berangkat_str,
            'Kode Booking': kode_booking,
            'No Penerbangan / Nama Hotel / Kereta': penerbangan,
            'Durasi': waktu_berangkat_tiba,
            'Nama Customer': name,
            'Rute/Kota': rute_final,
            'Harga Beli': per_orang_beli,
            'Harga Jual': per_orang_jual,
            'Laba': laba,
            'BF/NBF': '', # N/A untuk pesawat
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': persen_laba
        }
        results.append(entry)

    return results

---

## D. KERETA PROCESSOR FUNCTIONS

def extract_kereta_passengers(text_keep_lines: str) -> list:
    """
    Mencari nama kereta dan penumpang dari teks OCR kereta.
    Mengembalikan list of tuples: (nama_penumpang, info_kereta_kursi).
    """
    kereta_name = None
    # Lebih fleksibel mencari nama kereta
    m_train_name = re.search(r'(?:Kereta\s*Api|KA)\s+([A-Za-z\s]+)', text_keep_lines, re.IGNORECASE)
    if m_train_name:
        kereta_name = m_train_name.group(1).strip()
    
    # Cari pola penumpang dan info kursi
    # Contoh: "1. Nama Penumpang EKO 7/8A"
    pattern = re.compile(
        r'^\d+\.\s*(.+?)\s+((?:EKS|BIS|EKO|PRE|PAN|KLS)\s+\d+(?:/\d+)?[A-Za-z]?)\s*$', 
        re.IGNORECASE | re.MULTILINE
    )

    result = []
    for m in pattern.finditer(text_keep_lines):
        name = m.group(1).strip()
        seat = m.group(2).strip()
        
        # Hapus gelar dari nama penumpang
        name = re.sub(r"\b(Tn|Ny|Nn|Mr|Mrs|Ms|Sdr|Bapak|Ibu)\.?\s+", "", name, flags=re.IGNORECASE).strip()

        full_info = f"{kereta_name} {seat}" if kereta_name else seat
        result.append((name, full_info))
    return result

def process_ocr_kereta(text: str) -> list:
    """
    Memproses OCR teks tiket kereta, mengembalikan satu dict per penumpang.
    """
    cleaned = clean_text(text)
    cleaned_lines = clean_text_keep_lines(text)
    tl = cleaned.lower()

    # --- Kode Booking (menggunakan fungsi universal) ---
    kode_booking = extract_general_booking_code(cleaned)

    # --- Rute stasiun (asal dan tujuan) ---
    rute = None
    # Prioritaskan pola "Xxx - Yyy" atau "Xxx to Yyy"
    m_rute_dash = re.search(r'\b([A-Za-z\s]+)\s*[-–]\s*([A-Za-z\s]+)\b', tl)
    if m_rute_dash:
        stasiun_asal = m_rute_dash.group(1).strip().title() # Title case untuk nama stasiun
        stasiun_tujuan = m_rute_dash.group(2).strip().title()
        rute = f"{stasiun_asal} - {stasiun_tujuan}"
    else:
        # Fallback: Cari kode stasiun 3-huruf dalam kurung (SGU) - (GMR)
        stasiun_asal_code = re.search(r'berangkat.*?\(([A-Z]{2,3})\)', tl, re.DOTALL)
        stasiun_tujuan_code = re.search(r'datang.*?\(([A-Z]{2,3})\)', tl, re.DOTALL)
        if stasiun_asal_code and stasiun_tujuan_code:
            rute = f"{stasiun_asal_code.group(1).upper()} - {stasiun_tujuan_code.group(1).upper()}"
        # Fallback lain: mencari nama kota di text (misal, "Surabaya" atau "Gambir")
        # Perlu list kota/stasiun kereta jika ingin ini lebih akurat

    # --- Jam berangkat dan tiba (durasi) ---
    durasi = None
    m_jb = re.search(r'(?:berangkat|depart).*?(\d{1,2}[:.]\d{2})', tl)
    m_jt = re.search(r'(?:datang|arrive).*?(\d{1,2}[:.]\d{2})', tl)
    if m_jb and m_jt:
        durasi = f"{m_jb.group(1)} - {m_jt.group(1)}"
    else: # Fallback ke pola jam umum HH:MM - HH:MM
        m_time_range = re.search(r'(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})', tl)
        if m_time_range:
            durasi = f"{m_time_range.group(1)} - {m_time_range.group(2)}"

    # --- Tanggal berangkat ---
    tgl_berangkat_str = ''
    # Prioritaskan tanggal setelah 'Berangkat', 'Tanggal', atau hari dalam seminggu
    m_tg = re.search(r'(?:(?:berangkat|tanggal|senin|selasa|rabu|kamis|jumat|sabtu|minggu|mon|tue|wed|thu|fri|sat|sun)[,:\s]*)*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', tl, re.IGNORECASE)
    if m_tg:
        tgl_berangkat_dt = parse_date_from_str(m_tg.group(1))
        if tgl_berangkat_dt:
            tgl_berangkat_str = tgl_berangkat_dt.strftime('%Y-%m-%d')


    # --- Harga total beli/jual (menggunakan fungsi universal) ---
    harga_beli_total, harga_jual_total = extract_price_info(cleaned)

    # --- Data penumpang: nama + info kereta/kursi ---
    passenger_data = extract_kereta_passengers(cleaned_lines)
    jumlah_penumpang = len(passenger_data) if passenger_data else 1 # Default 1 jika tidak ada penumpang terdeteksi

    # Hitung per-penumpang jika total diketahui
    harga_beli_per = (harga_beli_total // jumlah_penumpang) if (harga_beli_total is not None and jumlah_penumpang > 0) else None
    harga_jual_per = (harga_jual_total // jumlah_penumpang) if (harga_jual_total is not None and jumlah_penumpang > 0) else None

    results = []
    # Jika tidak ada penumpang terdeteksi tapi ada info harga, buat 1 entri default
    if not passenger_data and (harga_beli_total or harga_jual_total):
        passenger_data = [(None, None)] # Buat entri dummy untuk loop

    for (nama_penumpang, kereta_info) in passenger_data:
        laba = None
        persen_laba = ''
        if harga_beli_per is not None and harga_jual_per is not None:
            laba = harga_jual_per - harga_beli_per
            if harga_beli_per > 0:
                persen_laba = f"{round((laba / harga_beli_per) * 100, 2)}%"

        data = {
            'Tgl Pemesanan': datetime.today().strftime('%Y-%m-%d'),
            'Tgl Berangkat': tgl_berangkat_str,
            'Kode Booking': kode_booking,
            'No Penerbangan / Nama Hotel / Kereta': kereta_info,
            'Durasi': durasi,
            'Nama Customer': nama_penumpang,
            'Rute/Kota': rute,
            'Harga Beli': harga_beli_per,
            'Harga Jual': harga_jual_per,
            'Laba': laba,
            'BF/NBF': '', # N/A untuk kereta
            'No Invoice': '',
            'Keterangan': '',
            'Pemesan': '',
            'Admin': '',
            '% Laba': persen_laba
        }
        results.append(data)

    return results

---

## E. MASTER PROCESSOR FUNCTION

def process_ocr_unified(text: str) -> list:
    """
    Mendeteksi tipe dokumen (hotel/pesawat/kereta) lalu memanggil fungsi processor yang sesuai.
    Jika unknown, kembalikan list kosong.
    """
    tipe = detect_document_type(text)
    print(f"DEBUG: detect_document_type result: '{tipe}'", flush=True) # Tambahkan flush=True untuk log segera
    if tipe == 'hotel':
        return process_ocr_text_multiple(text)
    elif tipe == 'pesawat':
        return process_ocr_pesawat(text)
    elif tipe == 'kereta':
        return process_ocr_kereta(text)
    else:
        print("[INFO] Jenis dokumen tidak dikenali sebagai hotel, pesawat, atau kereta.")
        return []

# ===============================================
# === BAGIAN TEST (jika dijalankan sebagai main) ===
# ===============================================

if __name__ == "__main__":
    # Ini adalah contoh input teks yang kita diskusikan sebelumnya
    pesawat_example_text = """
Kode Booking: TTES2
Berangkat
Sel, 10 Jun 2025
08:35
Soekarno Hatta (CGK)

Garuda Indonesia
GA123

Datang
Sel, 10 Jun 2025
09.20
Radin Inten II (TKG)
Nama Penumpang:
1.Sontoloyo
JUAL 940000
Beli 786446
"""

    hotel_example_text = """
Order ID 987654321
Grand Hyatt Jakarta
Jl. M.H. Thamrin Kav. 28-30, Jakarta
Check-in: 15 Agustus 2025
Check-out: 17 Agustus 2025
2 x Kamar Deluxe (termasuk sarapan)
Nama Tamu:
1. Ibu Budi Santoso
2. Mr. Alex Cokro
Harga Beli Total: Rp 1.500.000
Harga Jual: 2.000.000
"""
    
    kereta_example_text = """
No. Pesanan: XYZ789
Kereta Api Argo Bromo Anggrek
Berangkat: 28 Mei 2025, 09:00
Stasiun Surabaya Pasar Turi (SBI)
Tiba: 28 Mei 2025, 17:00
Stasiun Gambir (GMR)
Nama Penumpang:
1. Tn. Joko Susilo EKS 5/12A
2. Ny. Ayu Lestari EKS 5/12B
Jual: 600.000
Beli: 450.000
"""

    unknown_example_text = """
Ini adalah teks acak.
Tidak ada pola yang dikenali.
"""

    test_cases = {
        "Pesawat Example": pesawat_example_text,
        "Hotel Example": hotel_example_text,
        "Kereta Example": kereta_example_text,
        "Unknown Example": unknown_example_text,
    }

    # Testing process_ocr_unified dengan contoh-contoh
    for name, text_input in test_cases.items():
        print(f"\n--- Processing: {name} ---")
        print(f"DEBUG: Input text to detect_document_type:\n---START TEXT---\n{text_input}\n---END TEXT---", flush=True)
        results = process_ocr_unified(text_input)
        
        if results:
            for idx, entry in enumerate(results, start=1):
                print(f"\n--- Extracted Data ({name}) - Entry {idx} ---")
                for k, v in entry.items():
                    print(f"{k}: {v}")
        else:
            print(f"Tidak ada data yang diekstrak untuk {name}.")
        print("=" * 50)
