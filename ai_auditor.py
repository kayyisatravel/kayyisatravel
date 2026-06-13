# ai_auditor.py
import streamlit as st
from google import genai
from google.genai import types

def inisialisasi_gemini():
    """Mengaktifkan client Google GenAI secara aman menggunakan API Key dari secrets."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Kunci API Gemini tidak ditemukan di Secrets: {str(e)}")
        return None

def audit_forensik_dashboard(summary_text):
    """
    Mengirimkan ringkasan data finansial ke Gemini 3.1 Flash Lite
    untuk menghasilkan Laporan Keuangan Audit Formal (LHPA) yang berbasis data angka.
    """
    client = inisialisasi_gemini()
    if not client:
        return "Sistem AI gagal dimuat karena kendala autentikasi API Key."
        
    prompt = f"""
    Anda adalah seorang Senior Financial Auditor, Akuntan Forensik, dan Konsultan Pajak bersertifikat khusus industri biro perjalanan (Travel Agent).
    
    Tugas Anda adalah menyusun "Laporan Hasil Penelaahan Audit (LHPA)" formal berdasarkan data indikator mentah berikut. 
    Anda DILARANG HANYA BERBICARA TEORI. Anda WAJIB menyajikan ulang data angka dalam bentuk tabel komparasi akuntansi dan langsung menganalisis dampaknya terhadap kas perusahaan.
    
    DATA MENTAH DARI ENGINE:
    {summary_text}
    
    Susunlah LHPA tersebut dengan format Markdown resmi mengikuti template struktur berikut:
    
    # 📝 LAPORAN HASIL PENELAAHAN AUDIT (LHPA) — REKONSILIASI KEUANGAN
    
    ### 📊 I. RINGKASAN EKSEKUTIF DATA AKTUAL
    Sajikan ulang data dalam bentuk tabel Markdown berikut, hitung persentase rasionya secara matematis:

    | Indikator Finansial | Nilai Nominal (Rupiah) | Persentase / Rasio Kontribusi | Status Audit |
    | :--- | :--- | :--- | :--- |
    | **Omzet Penjualan** | [Isi Angka] | 100% | [OK / Perlu Review] |
    | **Harga Beli (HPP)** | [Isi Angka] | [HPP ÷ Omzet] % | [OK / Margin Tipis] |
    | **Profit Bersih Buku**| [Isi Angka] | [Laba ÷ Omzet] % | [Sehat / Kritis] |
    | **Total Piutang Mandek**| [Isi Angka] | [Piutang ÷ Omzet] % | [Aman / Bahaya Likuiditas] |
    
    ### ✈️ II. AUDIT PORTFOLIO PRODUK (PERFORMA MARGIN)
    Buatlah tabel analisis performa produk berdasarkan data distribusi yang dikirimkan:

    | Kategori Produk | Omzet | Laba Bersih | Realisasi Margin (%) | Peringkat Kontribusi |
    | :--- | :--- | :--- | :--- | :--- |
    | **PESAWAT** | [Isi Angka] | [Isi Angka] | [Margin %] | [Isi Peringkat] |
    | **HOTEL** | [Isi Angka] | [Isi Angka] | [Margin %] | [Isi Peringkat] |
    | **KERETA** | [Isi Angka] | [Isi Angka] | [Margin %] | [Isi Peringkat] |
    
    ### 🚨 III. TEMUAN FORENSIK ANOMALi & KEBOCORAN DANA
    Berikan analisis tajam berbasis data angka mengenai dua poin kritis berikut:
    1. **Kebocoran Harga (Transaksi Boncos)**: Sebutkan berapa kali terjadi transaksi laba negatif, berapa total kerugiannya, dan beri tahu manajemen mengapa ini bisa terjadi di sistem agen.
    2. **Ancaman Piutang Overdue (>30 Hari)**: Sebutkan nominal dana kritis yang macet, bandingkan dengan profit bersih perusahaan saat ini. Apakah dana macet ini sanggup mematikan arus kas harian?
    
    ### 💡 IV. REKOMENDASI AUDIT YANG DAPAT DIEKSEKUSI
    Berikan 3 rekomendasi taktis operasional (bukan teori kaku) khusus untuk bisnis Kayyisa Travel untuk:
    - Cara memperketat kontrol selisih harga beli tiket maskapai/hotel agar tidak boncos.
    - Strategi penagihan massal (*bulk collection*) untuk invoice yang berstatus Overdue.
    
    Gunakan gaya bahasa Indonesia Akuntan Publik yang formal, tajam, objektif, berpatokan penuh pada data angka, dan langsung menusuk pada solusi.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gagal mendapatkan respons analisis dari AI Auditor: {str(e)}"
