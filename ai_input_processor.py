# ai_input_processor.py
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re
import json
from datetime import datetime

tgl_sekarang_str = datetime.today().strftime("%Y-%m-%d")

# =====================================================================
# 1. SKEMA DATA PYDANTIC (SUDAH DISESUAIKAN SINKRON SUB-KATEGORI)
# =====================================================================
class AIUniversalEntry(BaseModel):
    Is_Bisnis: bool = Field(description="True jika transaksi tiket/hotel pelanggan. False jika pengeluaran pribadi/operasional rumah-kantor.")
    Tabel_Tujuan: str = Field(description="Wajib diisi 'DATA' jika Is_Bisnis true, atau 'PRIBADI' jika Is_Bisnis false.")
    kategori: str = Field(description=(
        "Jika Is_Bisnis true: wajib pilih 'Pemasukan' atau 'Pengeluaran'. "
        "Jika Is_Bisnis false: WAJIB pilih salah satu dari sub-kategori berikut: "
        "'Pemasukan' (untuk dana masuk/transferan/setoran modal pribadi), "
        "'cicilan_rumah', 'perbaikan_rumah', 'pajak_kendaraan', 'servis_kendaraan', "
        "'belanja_dapur', 'perlengkapan_rumah', 'asisten_rumah_tangga', "
        "'bensin_transport', 'makan_harian', 'kesehatan_obat', "
        "'listrik_air', 'wifi_internet', 'pulsa_hp', 'langganan_digital', "
        "'pendidikan_anak', 'dana_sosial', 'lifestyle', 'investasi_pribadi', 'pelunasan_cc_bisnis'."
    ))
    tgl_pemesanan: str = Field(description="Format YYYY-MM-DD. Jika ragu, gunakan tanggal hari ini atau samakan dengan tgl berangkat.")
    tgl_berangkat: str = Field(description="Format YYYY-MM-DD. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    kode_booking: str = Field(description="Teks string kapital (PNR/ID Pesanan). WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    item_name: str = Field(description="Nama properti hotel, detail penerbangan/kereta, atau nama barang belanjaan pribadi sesuai aturan format ketat.")
    durasi: str = Field(description="Durasi menginap hotel atau jam perjalanan transportasi. contoh: '1 mlm' untuk hotel, atau jam perjalanan '17:52-20:35' untuk transportasi. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    nama_customer: str = Field(description="Nama penumpang/tamu yang sudah dibersihkan sesuai EYD baku, atau nama toko belanja pribadi.")
    rute: str = Field(description="Kode bandara 3 huruf, stasiun, atau nama kota hotel. WAJIB kosongkan '' jika Is_Bisnis adalah false.")
    harga_beli: int = Field(description="Angka murni integer modal per unit (pax/kamar). Set 0 jika transaksi pribadi.")
    harga_jual: int = Field(description="Angka murni integer jual per unit atau nominal total uang belanja jika transaksi pribadi.")
    tipe: str = Field(description="Jika Is_Bisnis true, wajib pilih: 'PESAWAT', 'HOTEL', atau 'KERETA'. Jika Is_Bisnis false, wajib kosongkan ''.")
    bf_status: str = Field(description="Khusus HOTEL bisnis: isi 'BF' atau 'NBF'. Transportasi atau pribadi wajib kosongkan ''.")
    platform: str = Field(description="Nama vendor/platform booking. Set 'Lainnya' jika transaksi pribadi.")
    no_rekening: str = Field(description="Wajib pilih salah satu jika Is_Bisnis false: 'Aset Kantor', 'Rumah Tangga', 'Lifestyle', 'Investasi', 'Cadangan Bisnis', 'Dana Sosial / Titipan', 'Modal Kerja Bisnis'. Jika Is_Bisnis true: wajib kosongkan ''.")
    keterangan_tambahan: str = Field(description="Catatan ringkas pendukung transaksi atau nama paket wisata tambahan (add-on promo).")
    detail_dana: str = Field(description="Ekstrak nama bank yang tertulis di teks secara tepat. Contoh: 'Mandiri', 'BSI', 'BCA', 'BNI', 'BRI', 'OVO', 'DANA', atau 'SeaBank'")

    @field_validator('tgl_pemesanan', 'tgl_berangkat')
    @classmethod
    def pastikan_format_tanggal(cls, v: str) -> str:
        if not v:
            return ""
        v = v.strip()
        if re.match(r"^\d{2}[/-]\d{2}[/-]\d{4}$", v):
            pembatas = "/" if "/" in v else "-"
            return datetime.strptime(v, f"%d{pembatas}%m{pembatas}%Y").strftime("%Y-%m-%d")
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Format tanggal '{v}' tidak valid. Harus berupa YYYY-MM-DD atau DD/MM/YYYY.")

class AIUniversalParserResult(BaseModel):
    entries: List[AIUniversalEntry]

# =====================================================================
# 2. LOGIKA PYTHON KONVENSIONAL
# =====================================================================
def inisialisasi_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Autentikasi Gemini API Gagal: {str(e)}")
        return None

def terapkan_otomatisasi_bank(platform_name: str) -> str:
    p_lower = platform_name.lower()
    if any(x in p_lower for x in ["traveloka", "tiket", "kai", "access"]):
        return "UOB"
    elif any(x in p_lower for x in ["agoda", "book cabin"]):
        return "BNI"
    else:
        return "UOB"

def proses_pembacaan_multimodal_universal(text_input=None, file_input=None, audio_input=None):
    client = inisialisasi_gemini_client()
    if not client:
        return None

    prompt_rules = f"""
    Anda adalah sistem kecerdasan buatan entri data akuntansi profesional terpadu untuk Kayyisa Tour & Travel.
    Tugas Anda adalah mengekstrak data input (teks chat WA, rekaman suara dikte, atau foto nota/struk) menjadi struktur data JSON secara presisi.
    
    🛡️ GERBANG ATURAN PENGALIHAN DATA (ROUTING RULES):
    1. Transaksi JALUR BISNIS (Set properti "Is_Bisnis": true, "Tabel_Tujuan": "DATA"):
       Jika input berisi manifes pemesanan tiket pesawat, booking hotel, atau tiket kereta api milik customer/klien.
       
    2. Transaksi JALUR PRIBADI DOMPET KELUARGA & OPERASIONAL (Set properti "Is_Bisnis": false, "Tabel_Tujuan": "PRIBADI"):
       Wajib digunakan jika input berisi:
       - Pengeluaran operasional rumah/kantor, belanja bulanan sembako, uang jajan, bensin istri, cicilan KPR, iuran RT perumahan, tabungan investasi, atau pelunasan tagihan kartu kredit.
       - MUTASI REKENING MURNI, TRANSFER MASUK, ATAU NOTIFIKASI PEMBAYARAN TUNAI. Meskipun berasal dari nama PT/Perusahaan, jika inputnya HANYA BERUPA NOTIFIKASI MUTASI/TRANSFER DANA, maka WAJIB dikategorikan sebagai JALUR PRIBADI dengan kategori "Pemasukan".
       
       Aturan Penentuan "kategori" dan "no_rekening" Jalur Pribadi Berdasarkan Sub-Kategori Cerdas:
       - Kolom "tipe", "bf_status", "kode_booking", "durasi", "rute", "tgl_berangkat" WAJIB DIISI STRING KOSONG "".
       - Analisis teks input secara semantik, lalu wajib petakan bidang "kategori" dan "no_rekening" sesuai aturan berikut:
         
         * JIKA pembayaran/pelunasan Tagihan KARTU KREDIT (mayoritas kulakan tiket bisnis):
           Set "kategori": "pelunasan_cc_bisnis" dan "no_rekening": "Modal Kerja Bisnis"
         
         * JIKA pengeluaran terkait Tempat Tinggal & Kendaraan:
           - Cicilan rumah/KPR -> "kategori": "cicilan_rumah", "no_rekening": "Rumah Tangga"
           - Tukang/renovasi/perbaikan rumah -> "kategori": "perbaikan_rumah", "no_rekening": "Rumah Tangga"
           - Pajak STNK/mobil/motor -> "kategori": "pajak_kendaraan", "no_rekening": "Rumah Tangga"
           - Bengkel/oli/servis/cuci kendaraan -> "kategori": "servis_kendaraan", "no_rekening": "Rumah Tangga"
         
         * JIKA pengeluaran terkait Rumah Tangga & Keluarga:
           - Sembako/pasar/supermarket/sayur -> "kategori": "belanja_dapur", "no_rekening": "Rumah Tangga"
           - Sabun/sapu/perlengkapan rumah/galon/gas -> "kategori": "perlengkapan_rumah", "no_rekening": "Rumah Tangga"
           - Gaji ART/THR ART -> "kategori": "asisten_rumah_tangga", "no_rekening": "Rumah Tangga"
         
         * JIKA pengeluaran terkait Kebutuhan Pokok Hidup:
           - Bensin/tol/parkir/ojek online -> "kategori": "bensin_transport", "no_rekening": "Rumah Tangga"
           - Makan siang/warung harian non-rekreasi -> "kategori": "makan_harian", "no_rekening": "Rumah Tangga"
           - Dokter/obat/apotek/BPJS -> "kategori": "kesehatan_obat", "no_rekening": "Rumah Tangga"
         
         * JIKA pengeluaran terkait Tagihan Bulanan & Ops:
           - Token listrik/PLN/PDAM -> "kategori": "listrik_air", "no_rekening": "Rumah Tangga"
           - IndiHome/Biznet/Wifi rumah -> "kategori": "wifi_internet", "no_rekening": "Rumah Tangga"
           - Paket data/pulsa hp -> "kategori": "pulsa_hp", "no_rekening": "Rumah Tangga"
           - Netflix/Spotify/iCloud/Google One -> "kategori": "langganan_digital", "no_rekening": "Rumah Tangga"
         
         * JIKA pengeluaran terkait Edukasi, Anak, Sosial & Gaya Hidup:
           - Uang sekolah/SPP/les/buku anak -> "kategori": "pendidikan_anak", "no_rekening": "Rumah Tangga"
           - Sedekah/zakat/kondangan/kado -> "kategori": "dana_sosial", "no_rekening": "Dana Sosial / Titipan"
           - Kopi kekinian/restoran mall/bioskop/hobi/belanja baju -> "kategori": "lifestyle", "no_rekening": "Lifestyle"
         
         * JIKA pengeluaran untuk Tabungan Investasi Masa Depan:
           - Logam mulia/reksadana/saham/tabungan berjangka pribadi -> "kategori": "investasi_pribadi", "no_rekening": "Investasi"

         * JIKA pengeluaran operasional toko travel langsung dari dana cadangan/kantor:
           - Kertas print/alat kantor/AC kantor -> "kategori": "Pengeluaran", "no_rekening": "Aset Kantor" (atau "Cadangan Bisnis")

    🔀 PENANGANAN INPUT HIBRIDA (CAMPURAN):
    - Jika user mengirimkan teks yang berisi gabungan transaksi bisnis travel DAN transaksi pengeluaran/pemasukan pribadi sekaligus dalam satu teks, Anda WAJIB memisahkannya menjadi objek entri yang berbeda di dalam array JSON output.

    Aturan Tambahan Ekstraksi Tanggal:
        - Jika menemukan format tanggal dengan garis miring seperti DD/MM/YYYY (Contoh: 10/09/2026 artinya 10 September), ubah secara ketat ke YYYY-MM-DD (2026-09-10). Jangan tertukar antara bulan dan hari!

    🧮 ATURAN MATEMATIKA PECAH BARIS & HARGA ECERAN:
    1. UNTUK JALUR BISNIS: Periksa nama penumpang atau tamu terlebih dahulu.
       - JIKA nama tamu/penumpang BERBEDA-BEDA, Anda WAJIB memecah data menjadi beberapa baris entri, lalu bagi rata nominal total vendor/internal dengan jumlah pax/kamar tersebut.
       - JIKA nama tamu/penumpang YANG SAMA/NAMA TUNGGAL, memesan lebih dari 1 kamar/tiket sekaligus (ANTI-SPLIT DATA), Anda DILARANG keras memecahnya. Satukan menjadi 1 BARIS ENTRI TUNGGAL dan gunakan nominal total keseluruhan secara utuh.
       - Cari teks nama penumpang di tiket atau voucher hotel, biasanya didekat Label 'Nama Penumpang' atau 'Nama Tamu' atau 'Detail Tamu' atau 'Detail Penumpang' atau 'Passenger Name' atau 'Detail Passenger' dan sebagainya maka nama tersebut WAJIB kamu tetapkan sebagai "nama_customer"

    2. Perhitungan "harga_beli" (MODAL):
       - Cari teks nominal modal yang dibayarkan ke pihak vendor/OTA. cari teks nominal di dekat label 'Total Pembayaran' atau 'Dibayar Hari Ini' atau 'Jumlah Pembayaran' atau 'Jumlah yang dibayarkan' atau 'Telah Dibayar' atau 'Jumlah Total Pembayaran' maka nominal tersebut WAJIB kamu tetapkan sebagai "harga_beli". Set 0 jika bisnis via redeem point atau transaksi pribadi.

    3. Perhitungan "harga_jual" (HARGA TOKO PER KAMAR / PER PAX):
       - Langkah 1: Jika admin mengetik kata manual (cth: 'Jual 950000'), gunakan angka itu. Jika ada kata 'Harga' diikuti nominal angka, maka nominal tersebut WAJIB kamu tetapkan sebagai "harga_jual". Jika ada perkalian malam/pax (cth: 200.000/mlm selama 2 malam), kalikan nilainya (400000).
       - Langkah 2: Jika tidak ada input manual, cari teks nominal di dekat label 'GRAND TOTAL PRICE' atau 'Rate per Malam'. Bagi rata nominal total tersebut dengan jumlah kamar atau penumpang, masukkan sebagai "harga_jual".
       - Langkah 3 (FALLBACK): Jika Langkah 1 dan 2 tidak ada, samakan nilai "harga_jual" dengan "harga_beli".

    4. UNTUK JALUR PRIBADI: Masukkan nominal total uang belanja/transfer langsung ke field "harga_jual", set "harga_beli" menjadi 0.
       - Untuk JALUR PRIBADI, kolom "tgl_berangkat", "harga_beli" dan "durasi" WAJIB DIISI STRING KOSONG "".
       - Jika pada jalur pribadi tidak disebutkan nama toko spesifik, isi kolom "nama_customer" dengan nama vendor, nama pembayar/perusahaan mutasi dana, atau 'Lainnya'.

    📋 ATURAN STRUKTUR DATA UTAMA:
    0. NAMA CUSTOMER: Wajib ubah ke format Title Case (EYD Baku). Bersihkan dan balik format nama maskapai/internasional (Last Name/First Name) serta hapus gelar sapaan seperti 'MR', 'MRS', 'MS', 'TN', 'NY'.
    1. Tipe PESAWAT: "item_name" berisi Nama Maskapai dan No Penerbangan. "durasi" format 'HH:MM - HH:MM'. Rute HANYA kode bandara 3 huruf.
    2. Tipe HOTEL: "item_name" berisi Nama properti hotel bersih. "durasi" format Jumlah malam + 'mlm'. Rute HANYA nama kota/kabupaten. "bf_status" isi 'BF' atau 'NBF'.
    3. Tipe KERETA: "item_name" format [Nama Kereta] [Singkatan Kelas] [Nomor Gerbong]/[Nomor Kursi]. "durasi" format 'HH:MM - HH:MM'. Rute berisi kode stasiun asal - tujuan. Singkatan kelas Bisnis adalah 'Bis'.
    4. TANGGAL: Format standar ISO 'YYYY-MM-DD'. Teks input menggunakan standar penanggalan Indonesia (DD/MM/YYYY). Angka depan adalah tanggal, angka tengah adalah bulan.

    Output Anda WAJIB berupa JSON valid yang mengikuti skema data AIUniversalParserResult.
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


