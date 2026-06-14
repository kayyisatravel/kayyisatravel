# ai_input_processor.py
import streamlit as st
from google import genai
from google.genai import types
import json

def inisialisasi_gemini_client():
    """Mengaktifkan koneksi ke Google GenAI SDK menggunakan API Key dari secrets."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Autentikasi Gemini API Gagal: {str(e)}")
        return None

def proses_pembacaan_multimodal_universal(text_input=None, file_input=None, audio_input=None):
    """
    Core Engine Input Universal: Membaca teks area, rekaman suara dikte, atau foto struk.
    Otomatis mendeteksi parameter 'Is_Bisnis' dan 'Tabel_Tujuan' (DATA atau PRIBADI).
    Mendukung kasus khusus Redeem Point (Harga Beli = 0) dan Uang Sosial RT.
    """
    client = inisialisasi_gemini_client()
    if not client:
        return None

    # INSTRUKSI KETAT PROMPT: Mengunci kecerdasan buatan agar patuh pada rules Kayyisa Travel
    prompt_rules = """
    Anda adalah sistem kecerdasan buatan entri data akuntansi profesional untuk Kayyisa Tour & Travel.
    Tugas Anda adalah membaca data input (bisa berupa teks salinan chat WA, rekaman suara dikte, atau foto nota/struk pengeluaran).
    
    Ekstrak data tersebut secara objektif menjadi LIST OF DICTIONARIES dalam format JSON bersih.
    
    🛡️ GERBANG ATURAN PENGALIHAN DATA (ROUTING RULES):
    1. Transaksi JALUR BISNIS (Set properti "Is_Bisnis": true, "Tabel_Tujuan": "DATA"):
       Jika input berisi manifes pemesanan tiket pesawat, booking hotel, atau tiket kereta api milik customer/klien.
       - Tentukan kolom "tipe" dengan nilai wajib CAPITAL: 'PESAWAT', 'HOTEL', atau 'KERETA'.
       - JIKALAU ada pembelian bisnis menggunakan poin reward/diskon poin, set kolom "harga_beli" menjadi 0 dan berikan keterangan 'Redeem Point' di bagian platform.
       
    2. Transaksi JALUR PRIBADI DOMPET KELUARGA (Set properti "Is_Bisnis": false, "Tabel_Tujuan": "PRIBADI"):
       Jika input berisi pengeluaran operasional rumah merangkap kantor, belanja bulanan sembako, uang jajan, bensin istri, cicilan KPR, transit antar-bank, atau titipan iuran RT perumahan.
       - Kosongkan kolom "tipe" (set nilainya menjadi string kosong "").
       - Pilih pos "no_rekening" secara cerdas berdasarkan aturan berikut:
         * 'Aset Kantor' : Untuk cicilan KPR rumah kantor kosong atau perbaikan properti kantor tersebut.
         * 'Rumah Tangga' : Untuk belanja dapur, listrik/air rumah tinggal, gaji ART, atau bensin harian mobil istri.
         * 'Lifestyle' : Untuk makan di mall (Trans Studio), jajan kopi, liburan keluarga, atau belanja konsumtif pribadi.
         * 'Investasi' : For emas logam mulia, reksa dana, saham, atau tabungan masa depan mandiri.
         * 'Cadangan Bisnis' : Untuk setoran tabungan 40% laba toko atau penarikan dana darurat modal.
         * 'Dana Sosial / Titipan' : Khusus untuk iuran keamanan/RT titipan warga perumahan (Uang Sosial).
    
    STRUKTUR KELUARAN JSON WAJIB (Harus seragam agar dibaca mulus oleh Pandas DataFrame):
    [
        {
            "Is_Bisnis": true atau false (Boolean),
            "Tabel_Tujuan": "DATA" atau "PRIBADI" (String),
            "tgl_pemesanan": "Format DD-MM-YYYY, jika tidak terdeteksi gunakan tanggal hari ini",
            "tgl_berangkat": "Format DD-MM-YYYY, kosongkan "" jika transaksi pribadi",
            "kode_booking": "Teks string kapital, kosongkan "" jika transaksi pribadi",
            "item_name": "Nama penerbangan/hotel/kereta ATAU nama barang belanjaan pribadi",
            "durasi": "Durasi penerbangan/menginap, kosongkan "" jika transaksi pribadi",
            "nama_customer": "Nama penumpang/tamu ATAU nama toko tempat belanja pribadi",
            "rute": "Rute kota asal-tujuan, kosongkan "" jika transaksi pribadi",
            "harga_beli": Angka murni integer. Set 0 jika transaksi pribadi atau bisnis via redeem point,
            "harga_jual": Angka murni integer. Isi dengan nominal uang belanja jika ini transaksi pribadi,
            "tipe": "PESAWAT / HOTEL / KERETA atau kosongkan "" jika transaksi pribadi",
            "bf_status": "BF atau NBF, kosongkan "" jika transaksi pribadi",
            "platform": "Nama vendor/platform booking (Tiket.com, Traveloka, Agoda, KAI Access, dll), set 'Lainnya' jika pribadi",
            "no_rekening": "Isi salah satu dari 6 pos rekening pribadi di atas jika Is_Bisnis adalah false, kosongkan "" jika bisnis",
            "keterangan_tambahan": "Catatan ringkas pendukung transaksi"
        }
    ]
    
    Kembalikan HANYA string teks JSON murni yang valid tanpa dibungkus kode markdown ```json dan tanpa teks basa-basi pembuka/penutup apa pun.
    """

    content_payload = [prompt_rules]

    # Menyuntikkan media secara dinamis sesuai apa yang diinput oleh user di UI screen
    if text_input:
        content_payload.append(f"INPUT TEKS/SUARA USER: {text_input}")
    if file_input:
        content_payload.append(types.Part.from_bytes(data=file_input.getvalue(), mime_type=file_input.type))
    if audio_input:
        content_payload.append(types.Part.from_bytes(data=audio_input.getvalue(), mime_type=audio_input.type))

    try:
        # Mengeksekusi model Gemini 2.5 Flash yang sangat tajam dan cepat memproses visual nota & suara
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=content_payload
        )
        json_clean_text = response.text.strip()
        return json.loads(json_clean_text)
    except Exception as e:
        st.error(f"⚠️ Gagal mengekstrak dokumen melalui AI Engine: {str(e)}")
        return None
