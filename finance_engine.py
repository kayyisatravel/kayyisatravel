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


def hitung_performa_dan_aging_v4(df_data_raw, df_cashflow_raw):
    """
    Engine Finansial v4 Resmi: Memperbaiki bug tumpang tindih df_sales,
    menghilangkan kesalahan indentasi, dan menjamin 100% bebas dari KeyError.
    """
    # 🛡️ 1. TAMENG PROTEKSI OBJEK KOSONG / NONE
    if df_data_raw is None or (not isinstance(df_data_raw, pd.DataFrame)) or df_data_raw.empty:
        return {}
        
    if df_cashflow_raw is None or (not isinstance(df_cashflow_raw, pd.DataFrame)) or df_cashflow_raw.empty:
        df_cashflow_raw = pd.DataFrame(columns=["Invoice_Key", "Jumlah", "Tipe", "Kategori"])

    # 🏗️ 2. AMBIL DAN AMANKAN DATA PENJUALAN (SALES JOURNAL)
    df_sales = df_data_raw.copy()
    
    # Deteksi & Normalisasi Kolom Wajib Invoice_Key agar anti-KeyError
    if "Invoice_Key" not in df_sales.columns:
        df_sales["Invoice_Key"] = "N/A"
    else:
        df_sales["Invoice_Key"] = df_sales["Invoice_Key"].fillna("N/A").astype(str).str.strip()
        df_sales.loc[df_sales["Invoice_Key"] == "", "Invoice_Key"] = "N/A"

    # Proteksi tambahan untuk kolom opsional yang dipanggil di akhir fungsi
    if "Admin" not in df_sales.columns:
        df_sales["Admin"] = "N/A"
    if "Kode Booking" not in df_sales.columns:
        df_sales["Kode Booking"] = "N/A"
    if "Tipe" not in df_sales.columns:
        df_sales["Tipe"] = "Umum"

    # Bersihkan Data Nominal Angka & Tanggal Penjualan
        
    df_sales["Harga Beli (Num)"] = pd.to_numeric(df_sales["Harga Beli"].apply(bersihkan_angka), errors="coerce").fillna(0)
    df_sales["Harga Jual (Num)"] = pd.to_numeric(df_sales["Harga Jual"].apply(bersihkan_angka), errors="coerce").fillna(0)
    df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
    df_sales["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_sales["Tgl Pemesanan"], format="mixed", dayfirst=True, errors="coerce")

    
    # Hitung Perhitungan Finansial Makro (Accrual Basis)
    total_pendapatan = df_sales["Harga Jual (Num)"].sum()
    total_hpp = df_sales["Harga Beli (Num)"].sum()
    total_laba_buku = df_sales["Laba (Num)"].sum()

    # 📋 3. PROSES REKONSILIASI KAS MASUK
    total_piutang = 0.0
    overdue_lebih_30 = 0.0
    jumlah_invoice_piutang = 0
    text_top_debitur = "- (Bersih, tidak ada piutang aktif)\n"
    df_display_aging = pd.DataFrame()

    df_cf = df_cashflow_raw.copy()
    
    # Normalisasi struktur kolom wajib tabel cashflow
    if "Invoice_Key" not in df_cf.columns:
        df_cf["Invoice_Key"] = "N/A"
    else:
        df_cf["Invoice_Key"] = df_cf["Invoice_Key"].fillna("N/A").astype(str).str.strip()
        df_cf.loc[df_cf["Invoice_Key"] == "", "Invoice_Key"] = "N/A"
        
    if "Jumlah" not in df_cf.columns: df_cf["Jumlah"] = 0
    if "Tipe" not in df_cf.columns: df_cf["Tipe"] = "Masuk"
    
    # Total akumulasi cicilan pembayaran per invoice (Hanya tipe Masuk)
    df_cf["Jumlah"] = pd.to_numeric(df_cf["Jumlah"], errors="coerce").fillna(0)
    df_payments = (
        df_cf[df_cf["Tipe"] == "Masuk"]
        .groupby("Invoice_Key")["Jumlah"]
        .sum()
        .reset_index()
        .rename(columns={"Jumlah": "Jumlah Masuk"})
    )
    
    # Gabungkan data penjualan dengan data pembayaran cicilan kas masuk
    df_invoice = df_sales[["Invoice_Key", "Nama Pemesan", "No Invoice", "Harga Jual (Num)", "Tgl Pemesanan_Parsed"]].copy()
    df_invoice = df_invoice.merge(df_payments, on="Invoice_Key", how="left")
    df_invoice["Jumlah Masuk"] = df_invoice["Jumlah Masuk"].fillna(0)
    
    # Rumus Hitung Sisa Piutang Aktual
    df_invoice["Piutang"] = df_invoice["Harga Jual (Num)"] - df_invoice["Jumlah Masuk"]
    df_unpaid = df_invoice[df_invoice["Piutang"] > 1000].copy()
    
    if not df_unpaid.empty:
        # Agregasi data per nota tunggal
        df_agg = df_unpaid.groupby(["Invoice_Key", "Nama Pemesan", "No Invoice"], as_index=False).agg({
            "Piutang": "sum",
            "Tgl Pemesanan_Parsed": "min"
        })
        
        # Hitung Selisih Hari Penuaan Piutang (Aging)
        hari_ini = pd.Timestamp.today().normalize()
        df_agg["Tanggal Pemesanan"] = df_agg["Tgl Pemesanan_Parsed"].fillna(hari_ini)
        df_agg["Aging (hari)"] = (hari_ini - df_agg["Tanggal Pemesanan"].dt.normalize()).dt.days
        df_agg["Overdue"] = df_agg["Aging (hari)"] > 30
        
        # Rekap indikator makro risiko kredit (Indentasi Sudah Diperbaiki)
        total_piutang = df_agg["Piutang"].sum()
        jumlah_invoice_piutang = df_agg["No Invoice"].nunique()
        overdue_lebih_30 = df_agg[df_agg["Overdue"] == True]["Piutang"].sum()
        
        # 🕵️ Forensik Top 3 Pembawa Piutang Terbesar berdasarkan Alur Riil
        top_debitur = df_agg.groupby("Nama Pemesan")["Piutang"].sum().reset_index()
        top_debitur = top_debitur.sort_values("Piutang", ascending=False).head(3)
        text_top_debitur = ""
        for _, row in top_debitur.iterrows():
            text_top_debitur += f"- 👥 {row['Nama Pemesan']}: Menunggak Sisa Dana Selesai Rp {int(row['Piutang']):,}\n"
            
        # Siapkan Dataframe Hasil Akhir untuk Tampilan UI
        df_display_aging = df_agg[["Nama Pemesan", "No Invoice", "Tanggal Pemesanan", "Piutang", "Aging (hari)", "Overdue"]].copy()

    # 3. KANTONG PERSENJATAAN RASIO FINANSIAL (UNTUK CFO AI)
    net_profit_margin = (total_laba_buku / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    roi = (total_laba_buku / total_hpp * 100) if total_hpp > 0 else 0.0
    estimasi_kas_riil = (total_pendapatan - total_piutang) - total_hpp
    rasio_keterikatan_modal = (total_piutang / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    rasio_kerentanan_laba = (total_piutang / total_laba_buku * 100) if total_laba_buku > 0 else 0.0
    
    # 4. Segmentasi Profitabilitas per Kategori Tiket/Hotel
    segmentasi = df_sales.groupby("Tipe").agg(
        Omzet=("Harga Jual (Num)", "sum"),
        Laba=("Laba (Num)", "sum"),
        Count=("Kode Booking", "count")
    ).reset_index()
    text_segmentasi = ""
    for _, row in segmentasi.iterrows():
        margin_seg = (row['Laba'] / row['Omzet'] * 100) if row['Omzet'] > 0 else 0
        text_segmentasi += f"- Produk [{row['Tipe']}]: Omzet Rp {int(row['Omzet']):,}, Laba Rp {int(row['Laba']):,}, Margin {margin_seg:.2f}%, Vol: {row['Count']} Tiket\n"

    # 5. Deteksi Kebocoran Transaksi Rugi
    transaksi_boncos = df_sales[df_sales["Laba (Num)"] < 0]
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = transaksi_boncos["Laba (Num)"].sum()

    # Mengambil mode admin dengan aman jika kolom kosong/isi NA
    mode_admin = df_sales["Admin"].dropna().mode()
    top_admin = mode_admin[0] if not mode_admin.empty else "N/A"

    return {
        "total_transaksi": len(df_sales),
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
        "df_aging_report": df_display_aging
    }

