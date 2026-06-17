# finance_engine.py
import pandas as pd
import numpy as np
import re

def bersihkan_angka(val):
    """
    Algoritma V3 Cerdas: Menangani data angka murni (Float/Int) 
    maupun teks mata uang (String) dari Google Sheets tanpa merusak desimal.
    """
    if pd.isna(val) or val == "": 
        return 0.0
    
    if isinstance(val, (int, float)):
        return float(val)
        
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
        s_clean = re.sub(r'[^\d.]', '', str(val).replace(",", "."))
        try: 
            return float(s_clean)
        except: 
            return 0.0


# ==========================================
# FILE PERBAIKAN TOTAL: finance_engine.py
# ==========================================
import pandas as pd

def hitung_performa_dan_reconciliation_v5(df_sales_raw, df_pribadi_raw):
    """
    Engine Finansial v5 Steril: Menggunakan 2 Parameter Realita Sekarang.
    Menghubungkan Data Penjualan Utama dengan Data Mutasi Pribadi secara Fleksibel.
    """
    # 🛡️ 1. TAMENG PROTEKSI OBJEK KOSONG
    if df_sales_raw is None or (not isinstance(df_sales_raw, pd.DataFrame)):
        df_sales_raw = pd.DataFrame(columns=["Tgl Pemesanan", "Harga Beli", "Harga Jual", "Kode Booking", "Admin", "No Invoice", "Keterangan", "Nama Pemesan", "Tipe"])
        
    if df_pribadi_raw is None or (not isinstance(df_pribadi_raw, pd.DataFrame)):
        df_pribadi_raw = pd.DataFrame(columns=["Tanggal", "Bank_Sumber", "No_Rekening_AI", "Kategori", "Nominal", "Keterangan"])

    # 🏗️ 2. AMBIL DAN AMANKAN DATA PENJUALAN
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    
    if df_sales.empty:
        total_pendapatan = total_hpp = total_laba_buku = 0.0
    else:
        # Pembersihan Data Angka
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
        df_sales["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_sales["Tgl Pemesanan"], dayfirst=True, errors="coerce")
        
        total_pendapatan = df_sales["Harga Jual (Num)"].sum()
        total_hpp = df_sales["Harga Beli (Num)"].sum()
        total_laba_buku = df_sales["Laba (Num)"].sum()

    # 📋 3. REKONSILIASI OTOMATIS BERBASIS DATA MUTASI AKTUAL (PRIBADI)
    total_piutang = overdue_lebih_30 = jumlah_invoice_piutang = 0.0
    text_top_debitur = "- (Bersih, tidak ada piutang aktif)\n"
    df_display_aging = pd.DataFrame()

    # 🧼 Proses ekstraksi pembayaran dari data 'Pribadi' yang berkategori 'pemasukan'
    df_pr_copy = df_pribadi_raw.copy()
    df_payments = pd.DataFrame(columns=["No Invoice", "Jumlah Masuk"])
    
    if not df_pr_copy.empty and "No Invoice" in df_sales.columns:
        df_pr_copy["Nominal (Num)"] = df_pr_copy["Nominal"].apply(bersihkan_angka)
        df_pemasukan = df_pr_copy[df_pr_copy["Kategori"].astype(str).str.strip().str.lower() == "pemasukan"].copy()
        
        # Detektif AI: Mencari kecocokan Nomor Invoice di dalam Teks Keterangan mutasi pribadi
        list_pembayaran = []
        list_invoice_unik = df_sales["No Invoice"].dropna().unique().tolist()
        
        for inv in list_invoice_unik:
            inv_str = str(inv).strip()
            if inv_str == "" or inv_str == "N/A": continue
            # Cek apakah nomor invoice tertulis di kolom Keterangan Bank Pribadi
            mask_match = df_pemasukan["Keterangan"].astype(str).str.contains(inv_str, case=False, na=False)
            total_terbayar = df_pemasukan[mask_match]["Nominal (Num)"].sum()
            if total_terbayar > 0:
                list_pembayaran.append({"No Invoice": inv, "Jumlah Masuk": total_terbayar})
                
        if list_pembayaran:
            df_payments = pd.DataFrame(list_pembayaran)

    # Kawinkan data jualan dengan data cicilan yang terdeteksi
    if "No Invoice" in df_sales.columns:
        df_invoice = df_sales[["No Invoice", "Nama Pemesan", "Harga Jual (Num)", "Tgl Pemesanan_Parsed", "Keterangan"]].copy()
        if not df_payments.empty:
            df_invoice = df_invoice.merge(df_payments, on="No Invoice", how="left")
        else:
            df_invoice["Jumlah Masuk"] = 0.0
            
        df_invoice["Jumlah Masuk"] = df_invoice["Jumlah Masuk"].fillna(0)
        df_invoice["Piutang"] = df_invoice["Harga Jual (Num)"] - df_invoice["Jumlah Masuk"]
        
        # Filter Piutang Aktif (Keterangan mengandung 'Belum Lunas')
        is_belum_lunas = df_invoice["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
        is_sudah_lunas = df_invoice["Keterangan"].astype(str).str.contains(r'(?<!belum\s)lunas', case=False, na=False, regex=True)
        
        df_unpaid = df_invoice[((df_invoice["Piutang"] > 1000) | is_belum_lunas) & (~is_sudah_lunas)].copy()
        
        if not df_unpaid.empty:
            # Mengelompokkan murni berdasarkan kolom fisik nyata: No Invoice & Nama Pemesan
            df_agg = df_unpaid.groupby(["Nama Pemesan", "No Invoice"], as_index=False).agg({
                "Piutang": "sum",
                "Tgl Pemesanan_Parsed": "min"
            })
            
            hari_ini = pd.Timestamp.today().normalize()
            df_agg["Tanggal Pemesanan"] = df_agg["Tgl Pemesanan_Parsed"].fillna(hari_ini)
            df_agg["Aging (hari)"] = (hari_ini - df_agg["Tanggal Pemesanan"].dt.normalize()).dt.days
            df_agg["Overdue"] = df_agg["Aging (hari)"] > 30
            
            total_piutang = df_agg["Piutang"].sum()
            jumlah_invoice_piutang = df_agg["No Invoice"].nunique()
            overdue_lebih_30 = df_agg[df_agg["Overdue"] == True]["Piutang"].sum()
            
            # Top 3 Debitur
            top_debitur = df_agg.groupby("Nama Pemesan")["Piutang"].sum().reset_index()
            top_debitur = top_debitur.sort_values("Piutang", ascending=False).head(3)
            text_top_debitur = ""
            for _, row in top_debitur.iterrows():
                text_top_debitur += f"- 👥 {row['Nama Pemesan']}: Menunggak Rp {int(row['Piutang']):,}\n"
                
            df_display_aging = df_agg[["Nama Pemesan", "No Invoice", "Tanggal Pemesanan", "Piutang", "Aging (hari)", "Overdue"]].copy()

    # 🏦 4. KALKULASI REKENING BANK RIIL (PERBAIKAN SINKRONISASI MUTASI AKTUAL)
    dict_saldo_bank = {"BCA": 0.0, "Mandiri": 0.0, "BSI": 0.0, "BNI": 0.0, "BRI": 0.0, "SeaBank": 0.0, "Tunai": 0.0, "CC Mega": 0.0}
    
    # Inisialisasi akumulasi kantong anggaran digital riil berbasis mutasi kas ruko
    dict_alokasi_aktual = {"investor": 0.0, "cadangan_bisnis": 0.0, "rumah_tangga": 0.0, "investasi": 0.0, "lifestyle": 0.0}

    df_pr = df_pribadi_raw.copy()
    if not df_pr.empty:
        # Gunakan nama kolom berhuruf besar sesuai format fisik Google Sheets Anda
        df_pr["Nominal (Num)"] = df_pr["Nominal"].apply(bersihkan_angka)
        df_pr["Bank_Sumber"] = df_pr["Bank_Sumber"].astype(str).str.strip()
        
        for _, row in df_pr.iterrows():
            bank = row["Bank_Sumber"]
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal_mutasi = row["Nominal (Num)"]
            
            if nominal_mutasi <= 0:
                continue

            # A. KALKULASI MULTI-BANK (Sesuai Nilai ATM Nyata)
            # Normalisasi nama bank agar kebal dari variasi spasi/huruf kecil dari data input
            bank_key = None
            if "mandiri" in bank.lower(): bank_key = "Mandiri"
            elif "bca" in bank.lower(): bank_key = "BCA"
            elif "bsi" in bank.lower(): bank_key = "BSI"
            elif "bni" in bank.lower(): bank_key = "BNI"
            elif "bri" in bank.lower(): bank_key = "BRI"
            elif "seabank" in bank.lower() or "sea bank" in bank.lower(): bank_key = "SeaBank"
            elif "tunai" in bank.lower() or "cash" in bank.lower(): bank_key = "Tunai"
            
            if bank_key in dict_saldo_bank:
                if kat == "pemasukan":
                    dict_saldo_bank[bank_key] += nominal_mutasi
                elif kat == "pengeluaran":
                    dict_saldo_bank[bank_key] -= nominal_mutasi

            # B. KALKULASI POS ANGGARAN DIGITAL BERBASIS MUTASI NYATA
            if "cadangan" in pos_rek:
                dict_alokasi_aktual["cadangan_bisnis"] += nominal_mutasi if kat == "pemasukan" else -nominal_mutasi
            elif "rumah tangga" in pos_rek or "aset" in pos_rek:
                dict_alokasi_aktual["rumah_tangga"] += nominal_mutasi if kat == "pemasukan" else -nominal_mutasi
            elif "investasi" in pos_rek:
                dict_alokasi_aktual["investasi"] += nominal_mutasi if kat == "pemasukan" else -nominal_mutasi
            elif "lifestyle" in pos_rek:
                dict_alokasi_aktual["lifestyle"] += nominal_mutasi if kat == "pemasukan" else -nominal_mutasi

    # 🧮 5. FORENSIK FORMULA ALOKASI POS ANGGARAN DIGITAL AI (HYBRID RULES)
    # Gabungkan persenan laba toko travel utama dengan mutasi kas pribadi aktual agar angkanya sinkron
    laba_bersih_usaha = max(0.0, total_laba_buku)
    wajib_setor_investor = (laba_bersih_usaha * 0.075) + dict_alokasi_aktual["investor"]
    laba_setelah_investor = laba_bersih_usaha - (laba_bersih_usaha * 0.075)
    
    cadangan_bisnis_40 = (laba_setelah_investor * 0.40) + dict_alokasi_aktual["cadangan_bisnis"]
    gaji_owner_60 = laba_setelah_investor * 0.60
    
    pos_rumah_tangga_50 = (gaji_owner_60 * 0.50) + dict_alokasi_aktual["rumah_tangga"]
    pos_investasi_30 = (gaji_owner_60 * 0.30) + dict_alokasi_aktual["investasi"]
    pos_lifestyle_20 = (gaji_owner_60 * 0.20) + dict_alokasi_aktual["lifestyle"]


    # KANTONG PERSENJATAAN RASIO FINANSIAL (UNTUK CFO AI)
    net_profit_margin = (total_laba_buku / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    roi = (total_laba_buku / total_hpp * 100) if total_hpp > 0 else 0.0
    estimasi_kas_riil = (total_pendapatan - total_piutang) - total_hpp
    rasio_keterikatan_modal = (total_piutang / total_pendapatan * 100) if total_pendapatan > 0 else 0.0
    rasio_kerentanan_laba = (total_piutang / total_laba_buku * 100) if total_laba_buku > 0 else 0.0
    
    # ✈️ 6. SEGMENTASI PROFITABILITAS PER KATEGORI PRODUK
    text_segmentasi = ""
    if "Tipe" in df_sales.columns:
        segmentasi = df_sales.groupby("Tipe").agg(
            Omzet=("Harga Jual (Num)", "sum"),
            Laba=("Laba (Num)", "sum"),
            Count=("Kode Booking", "count")
        ).reset_index()
        for _, row in segmentasi.iterrows():
            margin_seg = (row['Laba'] / row['Omzet'] * 100) if row['Omzet'] > 0 else 0
            text_segmentasi += f"- Produk [{row['Tipe']}]: Omzet Rp {int(row['Omzet']):,}, Laba Rp {int(row['Laba']):,}, Margin {margin_seg:.2f}%, Vol: {row['Count']} Tiket\n"
    
    # 🚨 7. DETEKSI KEBOCORAN TRANSAKSI RUGI (BONCOS)
    transaksi_boncos = df_sales[df_sales["Laba (Num)"] < 0]
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = transaksi_boncos["Laba (Num)"].sum()
    
    # Mengambil mode admin dengan aman jika kolom kosong/isi NA
    mode_admin = df_sales["Admin"].dropna().mode()
    top_admin = mode_admin[0] if not mode_admin.empty else "N/A"
    
    # 📦 RETURN DICTIONARY DIKUNCI MATANG UNTUK DASHBOARD STREAMLIT UI
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
        "df_aging_report": df_display_aging,
        "saldo_bank_riil": dict_saldo_bank,
        "alokasi_ai": {
            "investor": wajib_setor_investor,
            "sisa_laba_murni": laba_setelah_investor,
            "cadangan_bisnis": cadangan_bisnis_40,
            "gaji_owner": gaji_owner_60,
            "rumah_tangga": pos_rumah_tangga_50,
            "investasi": pos_investasi_30,
            "lifestyle": pos_lifestyle_20
        }
    }

    
