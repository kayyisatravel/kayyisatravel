# app_v2.py
import streamlit as st
import pandas as pd
from datetime import date

# Import modul-modul modular baru sesuai blueprint
import sheets_utils
import finance_engine
import visualizer
import ai_auditor

# Konfigurasi layout lebar halaman Streamlit
st.set_page_config(layout="wide", page_title="Kayyisa Travel AI Dashboard v2", page_icon="🚀")

# Fungsi pembantu untuk memformat nominal angka ke Rupiah lokal di UI
def format_rupiah_ui(val):
    return f"Rp {int(val):,}".replace(",", ".")

# ========================================================
# 📥 1. AMBIL DATA DARI GOOGLE SHEETS (DENGAN CACHING)
# ========================================================
@st.cache_data(ttl=300) # Simpan di cache selama 5 menit agar hemat kuota API GSheets
def load_data_from_sheets(sheet_id, name_worksheet):
    try:
        worksheet = sheets_utils.connect_to_gsheet(sheet_id, name_worksheet)
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"❌ Gagal memuat data dari Google Sheets: {str(e)}")
        return pd.DataFrame()

# 💡 SILAKAN GANTI DENGAN ID GOOGLE SHEETS ASLI ANDA
SHEET_ID_MASTER = st.secrets.get("GOOGLE_SHEET_ID", "MASUKKAN_ID_GOOGLE_SHEETS_ANDA_DI_SINI")
NAMA_WORKSHEET = "Data" # Sesuai dengan nama tab database penjualan Anda

st.title("🚀 Kayyisa Travel — NextGen Financial AI Dashboard")
st.caption("Sistem Analitik Keuangan Modular yang Didukung oleh Google Gemini 3.1 Flash Lite")
st.markdown("---")

# Tarik data dari hulu spreadsheet
df_raw = load_data_from_sheets(SHEET_ID_MASTER, NAMA_WORKSHEET)

if df_raw.empty:
    st.warning("⚠️ Data kosong atau gagal terhubung ke Google Sheets. Periksa konfigurasi rahasia (`secrets.toml`) Anda.")
else:
    # Pre-parsing tanggal untuk filter global agar aman dari data kotor
    df_raw["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_raw["Tgl Pemesanan"], format="%d-%m-%Y", errors="coerce")
    df_raw = df_raw.dropna(subset=["Tgl Pemesanan_Parsed"]) # Buang baris jika tanggal tidak valid
    
    # ========================================================
    # 🎛️ 2. PANEL FILTER UTAMA (GLOBAL SIDEBAR)
    # ========================================================
    st.sidebar.header("🔍 Pengaturan Filter Global")
    
    # Filter 1: Rentang Tanggal
    min_date = df_raw["Tgl Pemesanan_Parsed"].min().date()
    max_date = df_raw["Tgl Pemesanan_Parsed"].max().date()
    
    tgl_pilihan = st.sidebar.date_input("Pilih Rentang Tanggal", [min_date, max_date])
    
    # Saring data master berdasarkan rentang waktu pilihan
    if len(tgl_pilihan) == 2:
        tgl_mulai, tgl_akhir = tgl_pilihan
        df_filtered = df_raw[
            (df_raw["Tgl Pemesanan_Parsed"].dt.date >= tgl_mulai) &
            (df_raw["Tgl Pemesanan_Parsed"].dt.date <= tgl_akhir)
        ].copy()
    else:
        df_filtered = df_raw.copy()
        
    # Filter 2: Tambahan Admin & Pemesan
    list_admin = ["(Semua)"] + sorted(df_filtered["Admin"].dropna().unique().tolist())
    selected_admin = st.sidebar.selectbox("Saring Berdasarkan Admin", list_admin)
    
    if selected_admin != "(Semua)":
        df_filtered = df_filtered[df_filtered["Admin"] == selected_admin]

    # ========================================================
    # 🧮 3. EKSEKUSI DATA (FINANCE ENGINE AKUNTANSI)
    # ========================================================
    # Kirim data hasil filter ke mesin hitung v2
    metrics = finance_engine.hitung_performa_dan_aging(df_filtered)

    # ========================================================
    # 💻 4. TAMPILKAN INTERFACES TABS (ANTI-EXPANDER MENUMPUK)
    # ========================================================
    tab_ringkasan, tab_aging, tab_ai_audit = st.tabs([
        "📊 Ringkasan Keuangan", 
        "⏳ Aging Report Piutang", 
        "🕵️‍♂️ AI Real-time Auditor"
    ])
    
    # --- TAB 1: RINGKASAN DATA ANGKA & GRAFIK ---
    with tab_ringkasan:
        st.subheader("📌 Indikator Utama Kinerja Keuangan")
        
        # Susun kartu metrik finansial
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("💰 Total Omzet Penjualan", format_rupiah_ui(metrics["pendapatan"]))
        with col_m2:
            st.metric("💸 Total Pengeluaran Modal (HPP)", format_rupiah_ui(metrics["hpp"]))
        with col_m3:
            st.metric("📈 Profit Bersih Buku", format_rupiah_ui(metrics["laba_bersih"]), 
                      delta=f"Margin {metrics['margin_laba_bersih']:.2f}%")
        
        st.markdown("---")
        
        # Tampilkan Grafik Gabungan dari modul visualizer
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            # Hitung data harian untuk tren
            df_daily_chart = df_filtered.copy()
            df_daily_chart["Harga Jual (Num)"] = df_daily_chart["Harga Jual"].apply(finance_engine.bersihkan_angka)
            df_daily_chart = df_daily_chart.groupby("Tgl Pemesanan_Parsed")["Harga Jual (Num)"].sum().reset_index()
            visualizer.render_grafik_tren_harian(df_daily_chart)
            
        with col_g2:
            visualizer.render_segmentasi_profit_margin(df_filtered)

    # --- TAB 2: AGING REPORT (LOGIKA BELUM LUNAS) ---
    with tab_aging:
        st.subheader("⏳ Daftar Invoice Belum Pelunasan Klien")
        
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.warning(f"🔴 Total Piutang Menggantung: {format_rupiah_ui(metrics['total_piutang'])} ({metrics['jumlah_invoice_piutang']} Invoice)")
        with col_a2:
            st.error(f"⚠️ Kritis (Overdue > 30 Hari): {format_rupiah_ui(metrics['overdue_lebih_30_hari'])}")
            
        st.markdown("---")
        
        df_aging = metrics["df_aging_report"]
        if df_aging.empty:
            st.success("🎉 Luar biasa! Seluruh tagihan invoice pada rentang filter ini sudah Lunas.")
        else:
            # Fungsi inline styling untuk baris yang jatuh tempo >30 hari
            def style_row_overdue(row):
                return ["background-color: #FF9999" if row.Overdue else "" for _ in row]
            
            # Format tampilan kolom harga agar ramah di tabel UI
            df_display_aging = df_aging.copy()
            df_display_aging["Harga Jual (Num)"] = df_display_aging["Harga Jual (Num)"].apply(format_rupiah_ui)
            df_display_aging = df_display_aging.rename(columns={"Harga Jual (Num)": "Nilai Tagihan"})
            
            st.dataframe(
                df_display_aging.style.apply(style_row_overdue, axis=1),
                use_container_width=True,
                height=400
            )
            st.caption("💡 Catatan: Baris berlatar belakang merah muda menandakan invoice menunggak parah melewati batas 30 hari.")

    # --- TAB 3: REAL-TIME FORENSIK AUDIT AI GEMINI 3.1 FLASH LITE ---
    with tab_ai_audit:
        st.subheader("🕵️‍♂️ Laporan Hasil Penelaahan Audit Forensik AI")
        st.info("Fitur ini mengirimkan rangkuman data indikator keuangan Anda ke model Gemini 3.1 Flash Lite untuk di-audit secara kritis.")
        
        # Merakit teks ringkasan untuk mata AI (Sangat Hemat Token & Kuota!)
        text_payload_ai = f"""
        DATA UTAMA:
        - Total Transaksi: {metrics['total_transaksi']} baris data
        - Omzet Penjualan: Rp {int(metrics['pendapatan']):,}
        - Total Pengeluaran Modal (HPP): Rp {int(metrics['hpp']):,}
        - Laba Bersih Buku: Rp {int(metrics['laba_bersih']):,}
        - Persentase Margin Laba: {metrics['margin_laba_bersih']:.2f}%
        - Admin Paling Aktif: {metrics['top_admin']}
        
        DISTRIBUSI PRODUK:
        {metrics['text_segmentasi']}
        
        RISIKO OPERASIONAL & KREDIT:
        - Total Invoice Belum Lunas: {metrics['jumlah_invoice_piutang']} buah nota
        - Nilai Total Piutang Klien: Rp {int(metrics['total_piutang']):,}
        - Dana Piutang Macet (>30 Hari): Rp {int(metrics['overdue_lebih_30_hari']):,}
        - Kebocoran Harga (Transaksi Rugi/Minus): {metrics['jumlah_transaksi_rugi']} kali transaksi, dengan total nilai boncos Rp {int(metrics['total_kerugian']):,}
        """
        
        # Gunakan Session State agar hasil jawaban Gemini terkunci di memori Streamlit saat pindah tab
        if "response_audit_ai" not in st.session_state:
            st.session_state.response_audit_ai = None
            
        if st.button("🔍 Mulai Jalankan Audit Finansial Sekarang", type="primary"):
            with st.spinner("Gemini AI sedang meneliti struktur pembukuan dan mengalkulasi risiko keuangan Anda..."):
                hasil_lhpa = ai_auditor.audit_forensik_dashboard(text_payload_ai)
                st.session_state.response_audit_ai = hasil_lhpa
                
        # Jika memori session state berisi jawaban AI, cetak di layar
        if st.session_state.response_audit_ai:
            st.markdown("---")
            st.markdown(st.session_state.response_audit_ai)
