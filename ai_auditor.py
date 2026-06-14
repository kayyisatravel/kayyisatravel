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

def audit_forensik_dashboard(hasil_v5):
    """
    Engine AI Auditor Eksekutif untuk Bahan Rapat Kinerja Harian/Bulanan.
    Menghasilkan laporan komprehensif berbasis tabel Markdown yang matang dan berbobot.
    """
    client = inisialisasi_gemini()
    if client is None:
        return "⚠️ Gagal menjalankan audit karena kendala API Key."

    # 📊 1. PREPARASI DATA: Ekstrak metrik krusial dari Hasil V5 menjadi teks ringkas
    alokasi = hasil_v5.get("alokasi_ai", {})
    summary_text = f"""
    === METRIK FINANSIAL UTAMA ===
    - Total Transaksi: {hasil_v5.get('total_transaksi')}
    - Omzet Penjualan: Rp {int(hasil_v5.get('pendapatan', 0)):,}
    - Total HPP: Rp {int(hasil_v5.get('hpp', 0)):,}
    - Laba Bersih Buku: Rp {int(hasil_v5.get('laba_murni', hasil_v5.get('laba_bersih', 0))):,}
    - Margin Laba Bersih (NPM): {hasil_v5.get('margin_laba_bersih', 0):.2f}%
    - Return on Investment (ROI): {hasil_v5.get('roi', 0):.2f}%
    - Estimasi Kas Riil (Cash-in): Rp {int(hasil_v5.get('kas_riil', 0)):,}
    
    === MANAJEMEN RISIKO KREDIT (PIUTANG) ===
    - Total Piutang Aktif: Rp {int(hasil_v5.get('total_piutang', 0)):,}
    - Jumlah Invoice Menggantung: {hasil_v5.get('jumlah_invoice_piutang', 0)}
    - Piutang Overdue (>30 Hari): Rp {int(hasil_v5.get('overdue_lebih_30_hari', 0)):,}
    - Rasio Keterikatan Modal: {hasil_v5.get('rasio_keterikatan_modal', 0):.2f}%
    - Rasio Kerentanan Laba: {hasil_v5.get('rasio_kerentanan_laba', 0):.2f}%
    - Detail Debitur Terbesar:\n{hasil_v5.get('text_top_debitur', '- None')}
    
    === DETEKSI KEBOCORAN & PERFORMA ===
    - Jumlah Transaksi Rugi (Boncos): {hasil_v5.get('jumlah_transaksi_rugi', 0)}
    - Total Nilai Kerugian: Rp {int(hasil_v5.get('total_kerugian', 0)):,}
    - Admin Paling Aktif/Modus: {hasil_v5.get('top_admin', 'N/A')}
    - Kinerja Produk:\n{hasil_v5.get('text_segmentasi', '- None')}
    
    === KESEHATAN KAS BANK FISIK ===
    {chr(10).join([f"- Saldo {bank}: Rp {int(saldo):,}" for bank, saldo in hasil_v5.get('saldo_bank_riil', {}).items()])}
    
    === KEPATUHAN KANTONG ANGGARAN DIGITAL AI ===
    - Setoran Wajib Investor (7.5%): Rp {int(alokasi.get('investor', 0)):,}
    - Kantong Cadangan Bisnis (40%): Rp {int(alokasi.get('cadangan_bisnis', 0)):,}
    - Gaji Bersih Owner (60%): Rp {int(alokasi.get('gaji_owner', 0)):,}
    - Pos Rumah Tangga (50% dari Gaji): Rp {int(alokasi.get('rumah_tangga', 0)):,}
    - Pos Investasi Pribadi (30% dari Gaji): Rp {int(alokasi.get('investasi', 0)):,}
    - Pos Lifestyle Keluarga (20% dari Gaji): Rp {int(alokasi.get('lifestyle', 0)):,}
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
    - Distribusi margin kontribusi laba per segmen produk travel.

    ### 3. TABEL MANAJEMEN RISIKO KREDIT & PENAGIHAN PIUTANG (BAD DEBT ACCRUAL)
    Buat tabel penuaan piutang (aging report) yang memuat:
    - Rasio Keterikatan Modal & Rasio Kerentanan Laba terhadap piutang.
    - Pemetaan prioritas penagihan untuk daftar debitur penunggak terbesar (Top Debitur) berdasarkan tingkat kedaruratan (Overdue >30 Hari).

    ### 4. TABEL EVALUASI KEPATUHAN KANTONG DIGITAL OWNER & BANK MUTASI
    Buat tabel yang menyoroti:
    - Akun kas bank fisik yang mengalami defisit/overdraft terhadap pembukuan.
    - Kepatuhan pengeluaran pos pribadi owner (Gaya Hidup/Lifestyle) dibandingkan dengan batas aman pembiayaan pos Cadangan Bisnis.

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
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gagal memproses data audit bertenaga internet: {str(e)}"
