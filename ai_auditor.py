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

def audit_forensik_dashboard(summary_text):
    """
    Mengirimkan rangkuman arsenal rasio keuangan ke model Gemini 2.5 Flash
    yang terhubung ke internet via Google Search Grounding untuk menghasilkan
    Laporan Audit Strategis yang kontekstual dengan dunia nyata.
    """
    client = inisialisasi_gemini()
    if not client:
        return "Sistem AI Auditor tidak aktif karena kendala API Key."
        
    prompt = f"""
    Anda adalah seorang Chief Financial Officer (CFO) Korporat, Konsultan Bisnis Internasional Senior, dan Akuntan Forensik bersertifikat yang ahli dalam industri Biro Perjalanan Wisata (Travel Agent) Indonesia.
    
    Tugas Anda adalah membedah dokumen persenjataan rasio keuangan [Kayyisa Travel] di bawah ini untuk merumuskan Laporan Audit Strategis & Rencana Aksi Pemulihan Modal. Anda DILARANG berbicara teori kaku atau asumsi verbal. Anda WAJIB menggunakan analisis angka aktual dari data penunjang.
    
    DATA ARSENAL KEUANGAN AKTUAL PERUSAHAAN:
    {summary_text}
    
    TUGAS INTEGRASI INTERNET (GOOGLE SEARCH GROUNDING) TERUPDATE:
    Sebelum memberikan opini, analisis pasar, dan rekomendasi pricing, Anda WAJIB melakukan penelusuran di internet menggunakan Google Search tools untuk memantau:
    1. Tren harga tiket pesawat domestik dan okupansi hotel di Indonesia saat ini (apakah sedang high season, low season, atau efek liburan tertentu).
    2. Kebijakan biaya admin, komisi maskapai terbaru, atau besaran service fee yang saat ini umum dan rasional diterapkan oleh Online Travel Agent (OTA) besar di Indonesia (seperti Traveloka, Tiket.com) agar margin perusahaan tetap kompetitif namun menguntungkan.
    
    STANDAR KESEHATAN (BENCHMARK) INDUSTRI TRAVEL AGENT INDONESIA:
    - Net Profit Margin (NPM) Sehat: 4% - 6% (Segmen Korporat/B2B Bervolume Tinggi), 8% - 15% (Segmen Retail/Leisure).
    - ROI Finansial Sehat: 12% - 18% dari perputaran modal tiket maskapai/hotel.
    - Rasio Keterikatan Modal dalam Piutang: Maksimal 10% dari total omzet bulanan.
    - Rasio Kerentanan Laba terhadap Piutang: Maksimal 50% (Jika nilai piutang > 100% dari laba bersih, perusahaan berada dalam kondisi "Kritis Lampu Merah/Insolvensi Teknis").
    
    Susunlah dokumen LHPA formal dengan format Markdown mengikuti struktur wajib di bawah ini:
    
    # 🏛️ REKOMENDASI CFO STRATEGIS & AUDIT FORENSIK (INTERNET CONNECTED) — KAYYISA TRAVEL
    
    ### 📊 I. MATRIKS EVALUASI RASIO KEUANGAN & KEPATUHAN INDUSTRI
    Sajikan kembali data angka ke dalam format tabel Markdown berikut, hitung selisih deviasinya dengan standar industri serta hubungkan analisisnya dengan kondisi ekonomi riil Indonesia hasil pencarian internet Anda:

    | Senjata / Indikator Finansial | Nilai Aktual Perusahaan | Rasio Realisasi | Batas Sehat Industri BPW | Status Penilaian CFO |
    | :--- | :--- | :--- | :--- | :--- |
    | **Net Profit Margin (NPM)** | [Isi Nominal] | [Isi % Realisasi]% | [Isi aturan terbaru industri yang sama] | [Over-performed / Under-performed] |
    | **Return on Investment (ROI)**| [Isi Nominal] | [Isi % Realisasi]% | [Isi aturan terbaru industri yang sama] | [Efisien / Pemborosan Modal] |
    | **Estimasi Kas Riil Lapangan**| [Isi Nominal] | Rp [Isi Kas Riil] | [Isi aturan terbaru industri yang sama] | [Arus Kas Sehat / Defisit Modal Kerja] |
    | **Rasio Keterikatan Piutang**| [Isi Nominal] | [Isi % Realisasi]% | [Isi aturan terbaru industri yang sama] | [Aman / Lampu Merah Kritis] |
    | **Rasio Kerentanan Laba**   | [Isi Nominal] | [Isi % Realisasi]% | [Isi aturan terbaru industri yang sama] | [Kertas Kosong / Uang Riil] |
    
    ### 👥 II. AUDIT KONSENTRASI KREDIT: SIAPA PENYUMBANG PIUTANG TERBESAR?
    Berdasarkan data *Laporan Piutang Macet (Top Debitur)* yang dikirimkan, sebutkan nama-nama pemesan/klien tersebut secara spesifik satu per satu beserta nominal utangnya. Jelaskan risiko apa yang dihadapi perusahaan jika nama tersebut menunda pembayaran, dan berikan **instruksi kerja hukum/operasional konkret** untuk menindak nama tersebut minggu ini.
    
    ### 💼 III. PENILAIAN STRATEGI PRICING & TARGET PROFIT YANG SEMESTINYA (BERDASARKAN RISET PASAR GOOGLE)
    Berdasarkan tabel distribusi produk travel (Pesawat, Hotel, Kereta):
    1. Analisis mengapa produk dengan omzet terbesar (Pesawat) justru menghasilkan margin yang tipis, dan produk hotel mencetak margin paling tebal. Hubungkan dengan dinamika sistem sub-agent/NTA maskapai di Indonesia saat ini. Apakah persentase profit saat ini sudah kompetitif dibanding pasar luar?
    2. Hitung secara matematis berapa total nominal rupiah profit yang **seharusnya masuk kantong secara tunai** jika seluruh piutang macet berhasil ditagih lunas.
    3. Berikan rumus strategi penetapan harga (*Mark-up Pricing* atau *Service Fee* per pax) yang tepat untuk mendongkrak margin keuntungan tanpa membuat harga kalah saing dengan OTA besar hasil riset internet Anda.
    
    ### ⚡ IV. EXECUTIVE ACTION PLAN (SOP OPERASIONAL UNTUK ADMIN & FINANCE)
    Berikan 3 perintah kerja yang tegas, lugas, dan taktis untuk langsung dijalankan oleh Admin (seperti Admin PA) dan tim finance Anda:
    - Kebijakan batas kredit maksimal (*Credit Limit Control*) per nama pemesan korporat.
    - Aturan penguncian sistem tiket (*System Hard-Stop Auto Block*) jika ditemukan harga modal vendor naik tiba-tiba di atas harga jual pelanggan.
    - Taktik penagihan massal (*Bulk Debt Collection*) dengan insentif pelunasan cepat.
    
    Gunakan gaya bahasa mentor bisnis yang merangkul, memberi semangat, solutif, jujur apa adanya, namun tetap tegas terhadap resiko bisnis kedepan dan fokus pada bagaimana memulihkan uang tunai bisnis secepatnya.
    Juga anda bisa berikan insight tren model bisnis terbaru yang bisa dijajaki namun tetap inline dengan core bisnis utama.
    Buat dalam format laporan siap cetak yang akan digunakan sebagai acuan dan petunjuk pelaksanaan bagi perusahaan. Termasuk periode laporan berdasarkan data yang diambil.
    """
    
    try:
        # 🚀 EKSEKUSI PEMBARUAN: Menggunakan model Gemini 2.5 Flash & Mengaktifkan Google Search Grounding
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
