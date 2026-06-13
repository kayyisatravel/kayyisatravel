# ai_auditor.py
import streamlit st
from google import genai

def inisialisasi_gemini():
    try:
        return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        st.error(f"❌ Kunci API Gemini tidak ditemukan: {str(e)}")
        return None

def audit_forensik_dashboard(summary_text):
    client = inisialisasi_gemini()
    if not client:
        return "Sistem AI Auditor tidak aktif karena kendala API Key."
        
    prompt = f"""
    Anda adalah seorang Chief Financial Officer (CFO) Korporat, Konsultan Bisnis Internasional Senior, dan Akuntan Forensik bersertifikat yang ahli dalam industri Biro Perjalanan Wisata (Travel Agent) Indonesia.
    
    Tugas Anda adalah membedah dokumen persenjataan rasio keuangan [Kayyisa Travel] di bawah ini untuk merumuskan Laporan Audit Strategis & Rencana Aksi Pemulihan Modal. Anda DILARANG berbicara teori kaku atau asumsi verbal. Anda WAJIB menggunakan analisis angka aktual dari data penunjang.
    
    DATA ARSENAL KEUANGAN AKTUAL PERUSAHAAN:
    {summary_text}
    
    STANDAR KESEHATAN (BENCHMARK) INDUSTRI TRAVEL AGENT INDONESIA:
    - Net Profit Margin (NPM) Sehat: 4% - 6% (Segmen Korporat/B2B Bervolume Tinggi), 8% - 15% (Segmen Retail/Leisure).
    - ROI Finansial Sehat: 12% - 18% dari perputaran modal tiket maskapai/hotel.
    - Rasio Keterikatan Modal dalam Piutang: Maksimal 10% dari total omzet bulanan.
    - Rasio Kerentanan Laba terhadap Piutang: Maksimal 50% (Jika nilai piutang > 100% dari laba bersih, perusahaan berada dalam kondisi "Kritis Lampu Merah/Insolvensi Teknis").
    
    Susunlah dokumen LHPA formal dengan format Markdown mengikuti struktur wajib di bawah ini:
    
    # 🏛️ REKOMENDASI CFO STRATEGIS & AUDIT FORENSIK — KAYYISA TRAVEL
    
    ### 📊 I. MATRIKS EVALUASI RASIO KEUANGAN & KEPATUHAN INDUSTRI
    Sajikan kembali data angka ke dalam format tabel Markdown berikut, hitung selisih deviasinya dengan standar industri:

    | Senjata / Indikator Finansial | Nilai Aktual Perusahaan | Rasio Realisasi | Batas Sehat IndustriBPW | Status Penilaian CFO |
    | :--- | :--- | :--- | :--- | :--- |
    | **Net Profit Margin (NPM)** | [Isi Nominal] | [Isi % Realisasi]% | 4% - 15% | [Over-performed / Under-performed] |
    | **Return on Investment (ROI)**| [Isi Nominal] | [Isi % Realisasi]% | 12% - 18% | [Efisien / Pemborosan Modal] |
    | **Estimasi Kas Riil Lapangan**| [Isi Nominal] | Rp [Isi Kas Riil] | Harus Positif | [Arus Kas Sehat / Defisit Modal Kerja] |
    | **Rasio Keterikatan Piutang**| [Isi Nominal] | [Isi % Realisasi]% | Maksimal 10% | [Aman / Lampu Merah Kritis] |
    | **Rasio Kerentanan Laba**   | [Isi Nominal] | [Isi % Realisasi]% | Maksimal 50% | [Kertas Kosong / Uang Riil] |
    
    ### 👥 II. AUDIT KONSENTRASI KREDIT: SIAPA PENYUMBANG PIUTANG TERBESAR?
    Berdasarkan data *Laporan Piutang Macet (Top Debitur)* yang dikirimkan, sebutkan nama-nama pemesan/klien tersebut secara spesifik satu per satu beserta nominal utangnya. Jelaskan risiko apa yang dihadapi perusahaan jika nama tersebut menunda pembayaran, dan berikan **instruksi kerja hukum/operasional konkret** untuk menindak nama tersebut minggu ini.
    
    ### 💼 III. PENILAIAN STRATEGI PRICING & TARGET PROFIT YANG SEMESTINYA
    Berdasarkan tabel distribusi produk travel (Pesawat, Hotel, Kereta):
    1. Analisis mengapa produk dengan omzet terbesar (Pesawat) justru menghasilkan margin yang tipis, dan produk hotel mencetak margin paling tebal. Apakah persentase profit saat ini sudah logis secara bisnis?
    2. Hitung secara matematis berapa total nominal rupiah profit yang **seharusnya masuk kantong secara tunai** jika seluruh piutang macet berhasil ditagih lunas.
    3. Berikan rumus strategi penetapan harga (*Mark-up Pricing* atau *Service Fee* per pax) yang tepat untuk mendongkrak margin keuntungan tanpa membuat harga kalah saing dengan OTA (Online Travel Agent) besar.
    
    ### ⚡ IV. EXECUTIVE ACTION PLAN (SOP OPERASIONAL UNTUK ADMIN & FINANCE)
    Berikan 3 perintah kerja yang tegas, lugas, dan taktis untuk langsung dijalankan oleh Admin (seperti Admin PA) dan tim finance Anda:
    - Kebijakan batas kredit maksimal (*Credit Limit Control*) per nama pemesan korporat.
    - Aturan penguncian sistem tiket (*System Hard-Stop Auto Block*) jika ditemukan harga modal vendor naik tiba-tiba di atas harga jual pelanggan.
    - Taktik penagihan massal (*Bulk Debt Collection*) dengan insentif pelunasan cepat.
    
    Gunakan gaya bahasa Indonesia profesional yang tegas, objektif, berwibawa, berpatokan mutlak pada angka, dan berorientasi pada pemulihan dana tunai (*Cash Recovery*).
    """
    
    try:
        response = client.models.generate_content(model='gemini-3.1-flash-lite', contents=prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gagal memproses data audit: {str(e)}"
