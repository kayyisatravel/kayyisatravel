# finance_engine.py
import pandas as pd
import numpy as np

def bersihkan_angka(val):
    """Membersihkan format Rp, titik, koma, dan spasi dari Google Sheets menjadi Float murni."""
    if pd.isna(val): return 0.0
    s = str(val).replace("Rp", "").replace(".", "").replace(" ", "").strip()
    s = s.replace(",", "")
    try: 
        return float(s)
    except: 
        return 0.0

def hitung_performa_dan_aging(df):
    """
    Engine utama untuk memproses Buku Jurnal Penjualan Kayyisa Travel.
    Menghasilkan metrik finansial, segmentasi produk, dan data Aging Report.
    """
    if df.empty:
        return {}

    df_clean = df.copy()
    
    # 1. Standardisasi Data Angka dan Tanggal
    df_clean["Harga Beli (Num)"] = df_clean["Harga Beli"].apply(bersihkan_angka)
    df_clean["Harga Jual (Num)"] = df_clean["Harga Jual"].apply(bersihkan_angka)
    df_clean["Laba (Num)"] = df_clean["Harga Jual (Num)"] - df_clean["Harga Beli (Num)"]
    df_clean["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_clean["Tgl Pemesanan"], format="%d-%m-%Y", errors="coerce")
    
    # 2. Perhitungan Finansial Makro (Accrual Basis)
    total_pendapatan = df_clean["Harga Jual (Num)"].sum()
    total_hpp = df_clean["Harga Beli (Num)"].sum()
    total_laba_buku = df_clean["Laba (Num)"].sum()
    margin_laba_total = (total_laba_buku / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    
    # 3. Algoritma Identifikasi Piutang & Perhitungan Aging (Status: Belum Lunas)
    is_unpaid = df_clean["Keterangan"].str.contains("Belum Lunas", na=False, case=False)
    df_piutang = df_clean[is_unpaid].copy()
    
    # Menggunakan asumsi waktu berjalan sistem operasional Anda (Juni 2026)
    hari_ini = pd.Timestamp.now().normalize()
    
    if not df_piutang.empty:
        df_piutang["Aging (hari)"] = (hari_ini - df_piutang["Tgl Pemesanan_Parsed"]).dt.days
        # Jika kolom No Invoice kosong, buat key unik kombinasi agar tidak cross-join
        df_piutang["No Invoice"] = df_piutang["No Invoice"].fillna("").astype(str)
        df_piutang.loc[df_piutang["No Invoice"] == "", "No Invoice"] = "INV-N/A-" + df_piutang["Kode Booking"].astype(str)
        
        df_piutang["Overdue"] = df_piutang["Aging (hari)"] > 30
        
        total_piutang = df_piutang["Harga Jual (Num)"].sum()
        jumlah_invoice_piutang = df_piutang["No Invoice"].nunique()
        overdue_lebih_30 = df_piutang[df_piutang["Aging (hari)"] > 30]["Harga Jual (Num)"].sum()
    else:
        total_piutang = 0.0
        jumlah_invoice_piutang = 0
        overdue_lebih_30 = 0.0
        df_piutang["Aging (hari)"] = 0
        df_piutang["Overdue"] = False

    # 4. Segmentasi Profitabilitas Produk (Pesawat, Hotel, Kereta)
    segmentasi = df_clean.groupby("Tipe").agg(
        Omzet=("Harga Jual (Num)", "sum"),
        Modal=("Harga Beli (Num)", "sum"),
        Laba_Bersih=("Laba (Num)", "sum"),
        Transaksi=("Kode Booking", "count")
    ).reset_index()
    
    segmentasi["Margin_%"] = (segmentasi["Laba_Bersih"] / segmentasi["Omzet"] * 100).round(2)
    
    # Mengubah data tabel segmentasi menjadi teks ringkas siap baca untuk AI
    text_segmentasi = ""
    for _, row in segmentasi.iterrows():
        text_segmentasi += f"- Jenis [{row['Tipe']}]: Omzet Rp {int(row['Omzet']):,}, Laba Rp {int(row['Laba_Bersih']):,}, Margin {row['Margin_%']}%, Total {row['Transaksi']} Transaksi.\n"

    # 5. Deteksi Kebocoran Transaksi (Laba Negatif / Boncos)
    transaksi_boncos = df_clean[df_clean["Laba (Num)"] < 0]
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = transaksi_boncos["Laba (Num)"].sum()
    
    # 6. Pemetaan Efisiensi Kinerja Admin
    admin_perf = df_clean.groupby("Admin")["Harga Jual (Num)"].sum().reset_index()
    top_admin = admin_perf.loc[admin_perf["Harga Jual (Num)"].idxmax()]["Admin"] if not admin_perf.empty else "N/A"

    return {
        "total_transaksi": len(df_clean),
        "pendapatan": total_pendapatan,
        "hpp": total_hpp,
        "laba_bersih": total_laba_buku,
        "margin_laba_bersih": margin_laba_total,
        "total_piutang": total_piutang,
        "jumlah_invoice_piutang": jumlah_invoice_piutang,
        "overdue_lebih_30_hari": overdue_lebih_30,
        "text_segmentasi": text_segmentasi,
        "jumlah_transaksi_rugi": jumlah_boncos,
        "total_kerugian": abs(total_kerugian),
        "top_admin": top_admin,
        "df_aging_report": df_piutang[["No Invoice", "Nama Pemesan", "Tgl Pemesanan", "Harga Jual (Num)", "Aging (hari)", "Overdue"]]
    }
