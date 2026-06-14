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
    Engine AI Auditor berbasis Gemini 2.5 Flash + Google Search Grounding.
    Menerima dictionary hasil rekonsiliasi v5 dan menghasilkan laporan audit mendalam.
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

    # 🧠 2. PROMPT FORENSIK TAJAM & SPESIFIK
    prompt = f"""
    Anda adalah seorang Senior Financial Auditor, Fraud Investigator, dan CFO AI bersertifikasi (CPA/CIA).
    Tugas Anda adalah melakukan audit forensik mendalam dan memberikan Executive Advisory Report berdasarkan data bisnis dan data pribadi owner berikut:

    {summary_text}

    Berikan hasil analisis Anda yang terintegrasi dalam format Markdown yang rapi dengan poin-poin berikut:
    1. **Executive Risk Score & Status Summary**: Berikan rating risiko (LOW/MEDIUM/HIGH) beserta ringkasan kondisi kesehatan gabungan (bisnis & pribadi).
    2. **Investigasi & Temuan Kritis**: Deteksi kejanggalan kas, gap antara Laba Buku vs Kas Riil (apakah mengalami 'Profit Rich, Cash Poor'?), transaksi boncos oleh admin, serta saldo bank yang minus/overdraft.
    3. **Analisis Risiko Kredit (Bad Debt Risk)**: Bedah rasio kerentanan laba terhadap piutang yang macet, serta analisis top debitur yang menunggak.
    4. **Audit Kepatuhan Anggaran Digital Owner**: Evaluasi apakah alokasi gaya hidup (Lifestyle) atau kantong pribadi menggerogoti stabilitas dana cadangan bisnis.
    5. **Rekomendasi Taktis Berbasis Tren Bisnis Travel Terkini**: Gunakan keahlian Anda dan akses pencarian internet untuk memberikan rekomendasi taktis atau strategi pricing/manajemen kas khusus untuk industri keagenan tiket travel di tahun berjalan ini.

    Gunakan gaya bahasa profesional, lugas, kritis, dan solutif. Jangan memuji data yang buruk.
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
