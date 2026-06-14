# ai_input_processor.py
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import json
from datetime import datetime


tgl_sekarang_str = datetime.today().strftime("%Y-%m-%d")
# =====================================================================
# 1. SKEMA DATA PYDANTIC
# =====================================================================
class AIUniversalEntry(BaseModel):
    Is_Bisnis: bool = Field(description="True jika transaksi tiket/hotel pelanggan. False jika pengeluaran pribadi/operasional rumah-kantor.")
    Tabel_Tujuan: str = Field(description="Wajib diisi 'DATA' jika Is_Bisnis true, atau 'PRIBADI' jika Is_Bisnis false.")
    tgl_pemesanan: str = Field(description="Format YYYY-MM-DD. Jika ragu/tidak terdeteksi, gunakan tanggal hari ini yaitu: {tgl_sekarang_str} atau samakan dengan tgl berangkat.")
    tgl_berangkat: str = Field(description="Format YYYY-MM-DD. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    kode_booking: str = Field(description="Teks string kapital (PNR/ID Pesanan). WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    item_name: str = Field(description="Nama properti hotel, detail penerbangan/kereta, atau nama barang belanjaan pribadi sesuai aturan format ketat.")
    durasi: str = Field(description="Durasi menginap hotel atau jam perjalanan transportasi. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    nama_customer: str = Field(description="Nama penumpang/tamu yang sudah dibersihkan sesuai EYD baku, atau nama toko belanja pribadi.")
    rute: str = Field(description="Kode bandara 3 huruf, stasiun, atau nama kota hotel. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    harga_beli: int = Field(description="Angka murni integer modal per unit (pax/kamar). Jika kondisi ANTI-SPLIT DATA aktif (nama tamu sama/tunggal), gunakan nominal TOTAL keseluruhan vendor secara utuh tanpa dibagi rata. Set 0 jika transaksi pribadi.")
    harga_jual: int = Field(description="Angka murni integer jual per unit (pax/kamar). Sesuai urutan prioritas: 1) Manual admin 'Jual/Harga', 2) Tabel internal itinerary. Jika kondisi ANTI-SPLIT DATA aktif (nama tamu sama/tunggal), gunakan nominal TOTAL keseluruhan internal secara utuh tanpa dibagi rata. Untuk pribadi: isi nominal total belanja.")
    tipe: str = Field(description="Jika Is_Bisnis true, wajib pilih: 'PESAWAT', 'HOTEL', atau 'KERETA'. Jika Is_Bisnis false, wajib kosongkan ''.")
    bf_status: str = Field(description="Khusus HOTEL bisnis: isi 'BF' atau 'NBF'. Transportasi atau pribadi wajib kosongkan ''.")
    platform: str = Field(description="Nama vendor/platform booking. Set 'Lainnya' jika transaksi pribadi.")
    no_rekening: str = Field(description="Wajib pilih salah satu jika Is_Bisnis false: 'Aset Kantor', 'Rumah Tangga', 'Lifestyle', 'Investasi', 'Cadangan Bisnis', 'Dana Sosial / Titipan'. Jika Is_Bisnis true: wajib kosongkan ''.")
    keterangan_tambahan: str = Field(description="Catatan ringkas pendukung transaksi atau nama paket wisata tambahan (add-on promo).")

class AIUniversalParserResult(BaseModel):
    entries: List[AIUniversalEntry]


# =====================================================================
# 2. LOGIKA PYTHON KONVENSIONAL
# =====================================================================
def inisialisasi_gemini_client():
    """Mengaktifkan koneksi ke Google GenAI SDK menggunakan API Key dari secrets."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Autentikasi Gemini API Gagal: {str(e)}")
        return None

def terapkan_otomatisasi_bank(platform_name: str) -> str:
    """Mengakomodasi 100% aturan pembagian bank dari skrip lama Part 2"""
    p_lower = platform_name.lower()
    if any(x in p_lower for x in ["traveloka", "tiket", "kai", "access"]):
        return "UOB"
    elif any(x in p_lower for x in ["agoda", "book cabin"]):
        return "BNI"
    else:
        return "UOB"


# =====================================================================
# 3. CORE ENGINE MULTIMODAL TERPADU
# =====================================================================
def proses_pembacaan_multimodal_universal(text_input=None, file_input=None, audio_input=None):
    """
    Core Engine Universal: Membaca teks, gambar, atau audio.
    """
    client = inisialisasi_gemini_client()
    if not client:
        return None

    # Teks prompt murni (Kurung kurawal tunggal karena tidak menggunakan f-string)
    prompt_rules = f"""
    Anda adalah sistem kecerdasan buatan entri data akuntansi profesional terpadu untuk Kayyisa Tour & Travel.
    Tugas Anda adalah mengekstrak data input (teks chat WA, rekaman suara dikte, atau foto nota/struk) menjadi struktur data JSON secara presisi.
    
    🛡️ GERBANG ATURAN PENGALIHAN DATA (ROUTING RULES):
    1. Transaksi JALUR BISNIS (Set properti "Is_Bisnis": true, "Tabel_Tujuan": "DATA"):
       Jika input berisi manifes pemesanan tiket pesawat, booking hotel, atau tiket kereta api milik customer/klien.
       
    2. Transaksi JALUR PRIBADI DOMPET KELUARGA (Set properti "Is_Bisnis": false, "Tabel_Tujuan": "PRIBADI"):
       Jika input berisi pengeluaran operasional rumah/kantor, belanja bulanan sembako, uang jajan, bensin istri, cicilan KPR, iuran RT perumahan (Uang Sosial).
       - Kosongkan kolom "tipe", "bf_status", "kode_booking", "durasi", "rute", "tgl_berangkat".
       - Pilih pos "no_rekening" secara cerdas wajib salah satu dari:
         * 'Aset Kantor' : Untuk cicilan KPR rumah kantor kosong atau perbaikan properti kantor tersebut.
         * 'Rumah Tangga' : Untuk belanja dapur, listrik/air rumah tinggal, gaji ART, atau bensin harian mobil istri.
         * 'Lifestyle' : Untuk makan di mall (Trans Studio), jajan kopi, liburan keluarga, atau belanja konsumtif pribadi.
         * 'Investasi' : Untuk emas logam mulia, reksa dana, saham, atau tabungan masa depan mandiri.
         * 'Cadangan Bisnis' : Untuk setoran tabungan 40% laba toko atau penarikan dana darurat modal.
         * 'Dana Sosial / Titipan' : Khusus untuk iuran keamanan/RT titipan warga perumahan (Uang Sosial).

    🧮 ATURAN MATEMATIKA PECAH BARIS & HARGA ECERAN:
    1. UNTUK JALUR BISNIS: Periksa nama penumpang atau tamu terlebih dahulu.
       - JIKA nama tamu/penumpang BERBEDA-BEDA (cth: Jane Susanna & Gascha Firga), Anda WAJIB memecah data menjadi beberapa baris entri, lalu bagi rata nominal total vendor/internal dengan jumlah pax/kamar tersebut.
       - JIKA nama tamu/penumpang YANG SAMA/NAMA TUNGGAL, memesan lebih dari 1 kamar/tiket sekaligus (ANTI-SPLIT DATA), Anda DILARANG keras memecahnya. Satukan menjadi 1 BARIS ENTRI TUNGGAL dan gunakan nominal total keseluruhan secara utuh (JANGAN dibagi rata).

    2.     2. Perhitungan "harga_beli" (MODAL):
       - Cari teks nominal modal yang dibayarkan ke pihak vendor/OTA (di dekat kata 'JUMLAH PEMBAYARAN', 'TOTAL', atau 'Dibayar Hari Ini'). 
       - Ikuti aturan nama tamu: Jika nama tamu berbeda-beda, bagi rata nominal tersebut dengan jumlah kamar/pax. Jika nama tamu tunggal (ANTI-SPLIT DATA), ambil nominal total tersebut secara utuh (2.608.500) tanpa pembagian. Masukkan hasilnya ke field "harga_beli". Set 0 jika bisnis via redeem point atau transaksi pribadi.
    3. Perhitungan "harga_jual" (HARGA TOKO PER KAMAR / PER PAX):
       - Langkah 1: Jika admin mengetik kata manual (cth: 'Jual 950000'), gunakan angka itu. Atau (ATURAN SHORTCUT): Jika admin mengetik manual kata 'Harga' diikuti nominal angka (Contoh: 'Harga Rp 1.000.000' atau 'Harga 1000000'), maka nominal tersebut WAJIB kamu tetapkan sebagai "harga_jual".
       - Langkah 2: Jika tidak ada input manual, cari teks nominal yang ditawarkan ke konsumen di dalam tabel itinerary internal Kayyisa. Kata kuncinya berada di dekat label 'Total Harga' atau 'Rate per Malam' (Contoh pada teks: 'Total Harga Rp 1.860.000').
       - Kamu WAJIB membagi rata nominal total internal tersebut dengan jumlah kamar atau jumlah penumpang (Contoh: 1.860.000 / 2 kamar = 930000).
       - Masukkan hasil pembagian bersih per kamar/per pax ini sebagai "harga_jual".
       - Jika dokumen HOTEL, tidak ada instruksi 'Jual'/'Harga' manual, tetapi ada kolom 'Total Harga' resmi dari tabel voucher (cth: 'Total Harga Rp 1.860.000'), ambil angka ini sebagai total omzet jual. Kamu WAJIB membagi rata total harga ini dengan 'Jumlah Kamar' (Contoh: Total Harga tabel 1.860.000 / 2 kamar = 930000). Masukkan hasil pembagian per kamar ini sebagai "harga_jual".
       - Langkah 3 (FALLBACK): Jika Langkah 1 dan 2 tidak ada, samakan nilai "harga_jual" dengan "harga_beli" per baris.
    4. UNTUK JALUR PRIBADI: Masukkan nominal total uang belanja langsung ke field "harga_jual", dan set "harga_beli" menjadi 0.

    📋 ATURAN STRUKTUR DATA UTAMA (WAJIB DIPATUHI BAGAIMANAPUN INPUT TEKSNYA):
    0. NAMA CUSTOMER: Wajib ubah ke format Title Case / Huruf Kapital di Awal Kata (EYD Baku). 
       Wajib bersihkan dan balik total jika mendeteksi format nama maskapai/internasional (Last Name/First Name) serta hapus gelar sapaan seperti 'MR', 'MRS', 'MS', 'TN', 'NY'.
       (Contoh: 'UTOMO/PRABOWO MR' -> Hasil: 'Prabowo Utomo').
       (Contoh: 'SUTRISNO/DEWI MRS' -> Hasil: 'Dewi Sutrisno').
    1. Tipe PESAWAT: "item_name" berisi Nama Maskapai dan No Penerbangan (cth: "QG997-QG 174"). Durasi format 'HH:MM - HH:MM'. Rute HANYA kode bandara 3 huruf (cth: "TKG - SUB").
    2. Tipe HOTEL:
       - "item_name": Nama properti hotel bersih (Contoh: "Montana Hotel Syariah Banjarbaru").
       - "durasi": Jumlah malam + kata 'mlm' (Contoh: "2 mlm").
       - "rute": HANYA nama kota/kabupaten lokasi hotel (Contoh: "Banjarbaru").
       - "bf_status": Isi 'BF' (jika ada sarapan) atau 'NBF' (jika tanpa sarapan/Room Only).
    3. Tipe KERETA (Termasuk Whoosh): "item_name" format penulisan WAJIB: [Nama Kereta] [Singkatan Kelas] [Nomor Gerbong]/[Nomor Kursi] (Contoh: "Sembrani Eks 4/5D"). Durasi format 'HH:MM - HH:MM'. Rute berisi kode stasiun asal - tujuan (cth: "GMR - SBI").
       INGAT: Jika kelasnya 'Business Class', singkatan kelasnya adalah 'Bis' (Contoh: "Whoosh Bis 2/4A"). JANGAN PERNAH menulis kata "Bus"!
    4. TANGGAL: Format standar ISO 'YYYY-MM-DD'. 
       - Jika teks menyebutkan kata 'Hari ini', 'Sekarang', atau tanggal tidak terdeteksi, Anda WAJIB menggunakan tanggal acuan ini: {tgl_sekarang_str}.
       - Untuk JALUR PRIBADI (Is_Bisnis: false), kolom "tgl_berangkat" WAJIB hukumnya diisi string kosong "" tanpa pengecualian, jangan pernah memasukkan tanggal apa pun di sana.
    5. PLATFORM: Pilih salah satu dari: "Tiket.com", "Traveloka", "Agoda", "Trip.com", "Book Cabin", "KAI Access", "RedDoorz", "Lainnya".
    6. KETERANGAN PAKET TAMBAHAN: Jika di dalam teks input terdapat informasi paket wisata tambahan (add-on promo ticket seperti Dufan, Ancol, Jatim Park, dll), kamu WAJIB menuliskan nama paket tersebut secara ringkas ke dalam field "keterangan_tambahan" agar datanya tidak hilang.
       
    """
    content_payload = [prompt_rules]
    
    if text_input:
        content_payload.append(f"INPUT TEKS/SUARA USER: {text_input}")
    
    if file_input:
        content_payload.append(types.Part.from_bytes(data=file_input.getvalue(), mime_type=file_input.type))
    
    if audio_input:
        content_payload.append(types.Part.from_bytes(data=audio_input.getvalue(), mime_type=audio_input.type))
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=content_payload,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIUniversalParserResult,
                temperature=0.1
            ),
        )
        
        parsed_json = json.loads(response.text)
        entries = parsed_json.get("entries", [])
        
        for entry in entries:
            if entry.get("Is_Bisnis") is True:
                bank_rekomendasi = terapkan_otomatisasi_bank(entry.get("platform", ""))
                if bank_rekomendasi:
                    entry["keterangan_tambahan"] = f"[{bank_rekomendasi}] {entry.get('keterangan_tambahan', '')}".strip()
                    
        return entries
    
    except Exception as e:
        st.error(f"⚠️ Gagal mengekstrak dokumen melalui AI Engine Terpadu: {str(e)}")
        return None

