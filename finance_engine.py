# finance_engine.py
# finance_engine.py
import pandas as pd
import numpy as np
import re

def bersihkan_angka(val):
    """
    Algoritma V3 Cerdas: Menangani data angka murni (Float/Int) 
    maupun teks mata uang (String) dari Google Sheets tanpa merusak desimal.
    """
    # 1. Jika data kosong, langsung kembalikan 0.0
    if pd.isna(val) or val == "": 
        return 0.0
    
    # 2. JIKA data dari Google Sheets sudah berupa tipe ANGKA murni (Float/Int)
    if isinstance(val, (int, float)):
        return float(val)
        
    # 3. JIKA data bertipe STRING (Teks seperti 'Rp 583.114.415,00')
    s = str(val).replace("Rp", "").replace(" ", "").strip()
    if not s:
        return 0.0

    try:
        # A. Buang ekor pecahan sen rupiah (,00) di paling belakang string jika ada
        s = re.sub(r',(\d{2})$', '', s)
        
        # B. Buang ekor pecahan sen internasional (.00) di paling belakang string jika ada
        s = re.sub(r'\.(\d{2})$', '', s)
        
        # C. Sapu bersih semua tanda titik ribuan atau koma ribuan yang tersisa
        s = re.sub(r'[.,]', '', s)
        
        return float(s)
    except:
        # Pilihan cadangan darurat jika teks rusak parah
        s_clean = re.sub(r'[^\d.]', '', str(val).replace(",", "."))
        try: 
            return float(s_clean)
        except: 
            return 0.0


def hitung_performa_dan_aging(df):
    """
    Engine Finansial v3: Menghitung Arsenal Rasio Lengkap, Top Debitur, 
    dan data penuaan piutang untuk asupan data analitik AI.
    """
    if df.empty:
        return {}

    df_clean = df.copy()
    
    # 1. Pembersihan Angka & Tanggal
    df_clean["Harga Beli (Num)"] = df_clean["Harga Beli"].apply(bersihkan_angka)
    df_clean["Harga Jual (Num)"] = df_clean["Harga Jual"].apply(bersihkan_angka)
    df_clean["Laba (Num)"] = df_clean["Harga Jual (Num)"] - df_clean["Harga Beli (Num)"]
    df_clean["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_clean["Tgl Pemesanan"], dayfirst=True, errors="coerce")
    
    # 2. Perhitungan Finansial Makro Base
    total_pendapatan = df_clean["Harga Jual (Num)"].sum()
    total_hpp = df_clean["Harga Beli (Num)"].sum()
    total_laba_buku = df_clean["Laba (Num)"].sum()
    
    # 3. Penyaringan & Perhitungan Aging Piutang ("Belum Lunas")
    is_unpaid = df_clean["Keterangan"].str.contains("Belum Lunas", na=False, case=False)
    df_piutang = df_clean[is_unpaid].copy()
    hari_ini = pd.Timestamp.now().normalize()
    
    if not df_piutang.empty:
        df_piutang["Aging (hari)"] = (hari_ini - df_piutang["Tgl Pemesanan_Parsed"]).dt.days
        df_piutang["No Invoice"] = df_piutang["No Invoice"].fillna("").astype(str)
        df_piutang.loc[df_piutang["No Invoice"] == "", "No Invoice"] = "INV-N/A-" + df_piutang["Kode Booking"].astype(str)
        df_piutang["Overdue"] = df_piutang["Aging (hari)"] > 30
        
        total_piutang = df_piutang["Harga Jual (Num)"].sum()
        jumlah_invoice_piutang = df_piutang["No Invoice"].nunique()
        overdue_lebih_30 = df_piutang[df_piutang["Aging (hari)"] > 30]["Harga Jual (Num)"].sum()
        
        # 🕵️ Forensik Top 3 Debitur Penyumbang Piutang Terbesar
        top_debitur = df_piutang.groupby("Nama Pemesan")["Harga Jual (Num)"].sum().reset_index()
        top_debitur = top_debitur.sort_values("Harga Jual (Num)", ascending=False).head(3)
        text_top_debitur = ""
        for _, row in top_debitur.iterrows():
            text_top_debitur += f"- 👥 {row['Nama Pemesan']}: Menunggak Tagihan Sebesar Rp {int(row['Harga Jual (Num)']):,}\n"
    else:
        total_piutang = 0.0
        jumlah_invoice_piutang = 0
        overdue_lebih_30 = 0.0
        text_top_debitur = "- (Bersih, Tidak ada piutang menggantung)\n"
        df_piutang["Aging (hari)"] = 0
        df_piutang["Overdue"] = False

    # 4. ARSENAL RASIO KEUANGAN & AUDIT (Kunci Utama AI Jenius)
    net_profit_margin = (total_laba_buku / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    roi = (total_laba_buku / total_hpp * 100) if total_hpp > 0 else 0.0
    
    # Rasio Likuiditas Jangka Pendek (Cash diestimasikan dari Laba Buku + HPP dikurangi piutang berjalan)
    estimasi_kas_riil = (total_pendapatan - total_piutang) - total_hpp
    rasio_keterikatan_modal = (total_piutang / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    rasio_kerentanan_laba = (total_piutang / total_laba_buku * 100) if total_laba_buku > 0 else 0.0
    
    # 5. Segmentasi Kinerja Berbasis Tipe Produk
    segmentasi = df_clean.groupby("Tipe").agg(
        Omzet=("Harga Jual (Num)", "sum"),
        Laba=("Laba (Num)", "sum"),
        Count=("Kode Booking", "count")
    ).reset_index()
    text_segmentasi = ""
    for _, row in segmentasi.iterrows():
        margin_seg = (row['Laba'] / row['Omzet'] * 100) if row['Omzet'] > 0 else 0
        text_segmentasi += f"- Produk [{row['Tipe']}]: Omzet Rp {int(row['Omzet']):,}, Laba Rp {int(row['Laba']):,}, Margin {margin_seg:.2f}%, Vol: {row['Count']} Tiket\n"

    # 6. Deteksi Kebocoran Transaksi Minus
    transaksi_boncos = df_clean[df_clean["Laba (Num)"] < 0]
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = transaksi_boncos["Laba (Num)"].sum()
    
    # 7. Efisiensi Kerja Admin
    admin_perf = df_clean.groupby("Admin")["Harga Jual (Num)"].sum().reset_index()
    top_admin = admin_perf.loc[admin_perf["Harga Jual (Num)"].idxmax()]["Admin"] if not admin_perf.empty else "N/A"

    return {
        "total_transaksi": len(df_clean),
        "pendapatan": total_pendapatan,
        "hpp": total_hpp,
        "laba_bersih": total_laba_buku,
        "margin_laba_bersih": net_profit_margin,
        "roi": roi,
        "kas_riil": estimasi_kas_riil,
        "total_piutang": total_piutang,
        "jumlah_invoice_piutang": jumlah_invoice_piutang,
        "overdue_lebih_30_hari": overdue_lebih_30,
        "rasio_keterikatan_modal": rasio_keterikatan_modal,
        "rasio_kerentanan_laba": rasio_kerentanan_laba,
        "text_top_debitur": text_top_debitur,
        "text_segmentasi": text_segmentasi,
        "jumlah_transaksi_rugi": jumlah_boncos,
        "total_kerugian": abs(total_kerugian),
        "top_admin": top_admin,
        "df_aging_report": df_piutang[["No Invoice", "Nama Pemesan", "Tgl Pemesanan", "Harga Jual (Num)", "Aging (hari)", "Overdue"]]
    }
