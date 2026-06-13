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
    Mengirimkan ringkasan data finansial yang padat (hemat token) ke Gemini 3.1 Flash Lite
    untuk menghasilkan Laporan Hasil Penelaahan Audit otomatis yang interaktif.
    """
    client = inisialisasi_gemini()
    if not client:
        return "Sistem AI gagal dimuat karena kendala autentikasi API Key."
        
    prompt = f"""
    Anda adalah seorang Senior Financial Auditor dan Akuntan Forensik profesional yang bekerja khusus di industri keagenan travel (Pesawat, Hotel, Kereta).
    Tugas Anda adalah memeriksa dokumen ringkasan indikator keuangan berikut untuk mencari risiko operasional, kebocoran margin, dan masalah likuiditas kas.
    
    DATA RINGKASAN FINANSIAL:
    {summary_text}
    
    Analisis data keuangan tersebut dengan sangat kritis dan susunlah Laporan Hasil Audit Eksklusif dalam format Markdown yang rapi dengan poin-poin wajib berikut:
    
    1. 🎯 **Kesehatan Portofolio & Efisiensi Margin**: Evaluasi performa segmen Pesawat, Hotel, dan Kereta. Berikan opini produk mana yang kinerjanya sehat dan mana yang tidak efisien.
    2. 🚨 **Analisis Kebocoran Dana & Transaksi Boncos**: Soroti secara tajam jika ditemukan transaksi yang menghasilkan laba negatif serta evaluasi apa penyebab mendasarnya.
    3. ⏳ **Evaluasi Risiko Kredit (Piutang Menggantung)**: Analisis jumlah invoice yang berstatus Belum Lunas, terutama dana kritis yang sudah Overdue > 30 hari. Berapa tingkat ancamannya terhadap kelancaran kas perusahaan?
    4. 💡 **Rekomendasi Taktis & Solutif**: Berikan 3 rekomendasi konkret yang dapat dieksekusi pemilik bisnis minggu ini untuk memperbaiki sistem kontrol harga dan mempercepat penagihan piutang pelanggan.
    
    Gunakan gaya bahasa Indonesia yang formal, berwibawa, tajam, dan langsung menusuk pada akar masalah bisnis operasional travel agen.
    """
    
    try:
        # Menggunakan model Gemini 3.1 Flash Lite sesuai dengan alokasi Free Tier Anda
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gagal mendapatkan respons analisis dari AI Auditor: {str(e)}"
