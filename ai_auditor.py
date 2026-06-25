# ai_auditor.py
import streamlit as st
from google import genai
from google.genai import types  # Wajib di-import untuk mendukung konfigurasi tools

def inisialisasi_gemini():
    """Mengaktifkan client Google GenAI secara aman menggunakan API Key dari secrets."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Kunci API Gemini tidak ditemukan di Secrets: {str(e)}")
        return None

def audit_forensik_dashboard(db):
    """
    Engine AI Auditor Eksekutif untuk Bahan Rapat Kinerja Harian/Bulanan.
    Menghasilkan laporan komprehensif berbasis tabel Markdown yang matang dan berbobot.
    """
    client = inisialisasi_gemini()
    if client is None:
        return "⚠️ Gagal menjalankan audit karena kendala API Key."

    # 📊 1. PREPARASI DATA: Ekstrak metrik krusial dari Hasil db V2 Baru menjadi teks ringkas
    target_kertas_dinamis = db.get("target_kertas_domestik", {})
    saldo_bank_map = db.get("log_bank_pribadi", {})

    # Ekstraksi saldo bersih fisik bank secara aman dari struktur sub-dictionary
    text_rincian_bank = ""
    for bank_nm, info in saldo_bank_map.items():
        if isinstance(info, dict):
            text_rincian_bank += f"- Saldo {bank_nm}: Rp {int(info.get('saldo', 0.0)):,}\n"

    summary_text = f"""
    === METRIK FINANSIAL UTAMA BISNIS TRAVEL ===
    - Total Tiket/Pax Terjual: {db.get('total_tiket_terjual', 0)} Pax
    - Omzet Penjualan Buku: Rp {int(db.get('total_omzet_buku', 0)):,}
    - Total Pengeluaran Modal (HPP): Rp {int(db.get('total_hpp_buku', 0)):,}
    - Laba Buku Total (Paper Profit): Rp {int(db.get('laba_buku_total', 0)):,}
    - Margin Laba Bersih (NPM): {db.get('npm', 0):.2f}%
    - Return on Investment (ROI): {db.get('roi', 0):.2f}%
    - Net Cash Flow Operating (Kas Riil Fisik): Rp {int(db.get('kas_riil_bisnis_toko', 0)):,}
    
    === MANAJEMEN RISIKO KREDIT (PIUTANG) ===
    - Total Piutang Aktif: Rp {int(db.get('total_piutang', 0)):,}
    - Jumlah Invoice Menggantung: {db.get('jumlah_invoice_piutang', 0)} Nota Unpaid
    - Rasio Keterikatan Modal (Capital Tie-Up): {db.get('rasio_keterikatan_modal', 0):.2f}%
    - Rasio Kerentanan Laba (Earnings Vulnerability): {db.get('rasio_kerentanan_laba', 0):.2f}%
    
    === DETEKSI KEBOCORAN & PERFORMA ===
    - Jumlah Transaksi Rugi (Boncos): {db.get('jumlah_boncos', 0)} Kasus
    - Total Nilai Kerugian Operasional: Rp {int(db.get('total_kerugian', 0)):,}
    - Admin Teraktif: {db.get('top_admin', 'N/A')}
    - Laba Bersih Riil Bisnis (Net Income State): Rp {int(db.get('laba_bersih_riil_bisnis', 0)):,}
    
    === KESEHATAN KAS BANK FISIK OPERASIONAL & PRIBADI ===
    {text_rincian_bank}
    
    === KEPATUHAN KANTONG ANGGARAN DOMESTIK DINAMIS AI OWNER ===
    - Total Jatah Prive Dinamis Dialokasikan: Rp {int(db.get('gaji_owner_dialokasikan', 0)):,}
    - Kuota Dinamis Kelompok 1 (Tempat Tinggal & KPR): Rp {int(target_kertas_dinamis.get("1. Tempat Tinggal & Kendaraan (40.9%)", 0)):,}
    - Kuota Dinamis Kelompok 2 (Rumah Tangga & ART): Rp {int(target_kertas_dinamis.get("2. Rumah Tangga & Keluarga (25.8%)", 0)):,}
    - Kuota Dinamis Kelompok 3 (Kebutuhan Pokok Hidup): Rp {int(target_kertas_dinamis.get("3. Kebutuhan Pokok Hidup (19.0%)", 0)):,}
    - Kuota Dinamis Kelompok 4 (Tagihan Bulanan & Ops): Rp {int(target_kertas_dinamis.get("4. Tagihan Bulanan & Ops (9.2%)", 0)):,}
    - Kuota Dinamis Kelompok 5 (Edukasi, Anak & Investasi Emas): Rp {int(target_kertas_dinamis.get("5. Edukasi, Anak & Sosial (5.1%)", 0)):,}
    """

    # 🧠 2. PROMPT FORENSIK BERBASIS STRUKTUR TABEL RAPAT
    prompt = f"""
    Anda adalah seorang Senior Financial Auditor, Fraud Investigator, dan CFO AI bersertifikasi (CPA/CIA).
    Tugas Anda adalah menyusun Laporan Dokumen Acuan Resmi Rapat Kinerja Finansial (Harian/Bulanan) berdasarkan data berikut:

    {summary_text}

    Wajib sajikan analisis Anda ke dalam format Markdown dengan struktur tabel komprehensif berikut:

    # 📋 LAPORAN AUDIT FORENSIK & KINERJA FINANSIAL (BAHAN ADVISORY RAPAT)
    *Gunakan dokumen ini sebagai acuan evaluasi kebijakan operasional, kontrol risiko, dan penyesuaian porsi modal kerja.*

    ### 1. RINGKASAN EKSEKUTIF & SKOR RISIKO GABUNGAN
    Sajikan tabel parameter risiko (LOW/MEDIUM/HIGH) yang menggabungkan aspek profitabilitas bisnis dan kepatuhan dompet pribadi owner beserta catatan evaluasi kilat untuk direksi.

    ### 2. TABEL FORENSIK KEBOCORAN KAS & MATRIKS PROFITABILITAS
    Buat tabel yang membandingkan metrik akuntansi, seperti:
    - Selisih Laba Buku vs Estimasi Kas Riil Lapangan (Sorot isu 'Profit Rich, Cash Poor' jika ada).
    - Kebocoran transaksi boncos dari sistem pricing/promo beserta performa pengawasan Admin.
    - Analisis performa rata-rata margin per tiket/pax travel.

    ### 3. TABEL MANAJEMEN RISIKO KREDIT & PENAGIHAN PIUTANG (BAD DEBT ACCRUAL)
    Buat tabel penuaan piutang (aging report) yang memuat:
    - Rasio Keterikatan Modal & Rasio Kerentanan Laba terhadap piutang.
    - Pemetaan tingkat kedaruratan penagihan invoice unpaid menggantung berdasarkan rasio kerentanan laba kertas toko.

    ### 4. TABEL EVALUASI KEPATUHAN KANTONG DIGITAL OWNER & BANK MUTASI
    Buat tabel yang menyoroti:
    - Akun kas bank fisik yang mengalami defisit/overdraft terhadap pembukuan berjalan.
    - Kepatuhan pengeluaran realisasi pos pribadi owner dibandingkan dengan batas aman plafon kuota anggaran dinamis hasil kombinasi Solusi 1 & 2.

    ### 5. ADVISORY STRATEGIS & PROYEKSI EVALUASI KERJA (BERDASARKAN TREN TRAVEL TAHUN INI)
    Gunakan kapabilitas internet search Anda untuk mengecek kondisi keagenan tiket travel/maskapai/wisata di tahun berjalan ini. Berikan rekomendasi kebijakan bisnis nyata, bukan teori kaku (misal: strategi deposit, kebijakan kredit klien, atau efisiensi biaya operasional).

    *Aturan Penulisan:* Gunakan gaya bahasa profesional, dingin, tegas, dan berbasis data objektif. Pastikan format tabel Markdown rapi dan mudah dibaca di layar proyektor rapat.
    """

    # 🚀 3. EKSEKUSI PEMBARUAN DENGAN GROUNDING INTERNET
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2
            )
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gagal memproses data audit bertenaga internet: {str(e)}"
