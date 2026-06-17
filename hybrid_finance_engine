import pandas as pd
import numpy as np
import re

def bersihkan_angka(val):
    """
    Algoritma Pembersih Angka: Menangani data string mata uang (Rp) 
    maupun angka mentah tanpa merusak format desimal.
    """
    if pd.isna(val) or val == "": 
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).replace("Rp", "").replace(" ", "").strip()
    if not s:
        return 0.0
    try:
        s = re.sub(r',(\d{2})$', '', s)
        s = re.sub(r'\.(\d{2})$', '', s)
        s = re.sub(r'[.,]', '', s)
        return float(s)
    except:
        s_clean = re.sub(r'[^\d.]', '', str(val).replace(",", "."))
        try: 
            return float(s_clean)
        except: 
            return 0.0

def hitung_hybrid_monitoring_v1(df_sales_raw, df_pribadi_raw):
    """
    Engine Hybrid v1: Memisahkan Realitas Kas Fisik dengan Target Alokasi Kertas.
    Menggunakan konsep Gaji Baseline Flat Rp26.259.567.
    """
    # 1. PENGONDISIAN DATA AWAL
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    # Bersihkan angka pada data penjualan
    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
    else:
        df_sales["Harga Beli (Num)"] = 0.0
        df_sales["Harga Jual (Num)"] = 0.0
        df_sales["Laba (Num)"] = 0.0

    # Bersihkan angka pada data pribadi
    if not df_pribadi.empty:
        df_pribadi["Nominal (Num)"] = df_pribadi["Nominal"].apply(bersihkan_angka)
    else:
        df_pribadi["Nominal (Num)"] = 0.0

    # 2. FILTER GERBANG 1: HITUNG PIUTANG & KAS RIIL BISNIS
    # Filter Piutang Aktif berdasarkan kata kunci 'Belum Lunas'
    if "Keterangan" in df_sales.columns:
        is_belum_lunas = df_sales["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
    else:
        is_belum_lunas = False
        
    df_unpaid = df_sales[is_belum_lunas].copy()
    total_piutang = df_unpaid["Harga Jual (Num)"].sum() if not df_unpaid.empty else 0.0
    
    total_omzet_buku = df_sales["Harga Jual (Num)"].sum()
    total_hpp_buku = df_sales["Harga Beli (Num)"].sum()
    
    # Formula Hukum Besi Kas Bisnis: Omzet Terkumpul - Total HPP Toko
    kas_riil_bisnis_toko = (total_omzet_buku - total_piutang) - total_hpp_buku
    laba_buku_total = df_sales["Laba (Num)"].sum()

    # 3. KANTONG REALITAS FISIK MULTI-BANK (DARI MUTASI AKTUAL)
    saldo_bank_aktual = {"BCA": 0.0, "Mandiri": 0.0, "BSI": 0.0, "Kartu Kredit": 0.0}
    
    # KANTONG MUTASI HISTORIS DIGITAL (DI ATAS KERTAS DARI REK_AI)
    mutasi_pos_digital = {"cadangan_bisnis": 0.0, "rumah_tangga": 0.0, "investasi": 0.0, "lifestyle": 0.0}

    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            bank = str(row["Bank_Sumber"]).strip().lower()
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal = row["Nominal (Num)"]
            
            # Hitung Saldo Bank Riil
            bank_key = None
            if "cc" in bank or "credit" in bank or "uob" in bank: bank_key = "Kartu Kredit"
            elif "mandiri" in bank: bank_key = "Mandiri"
            elif "bca" in bank: bank_key = "BCA"
            elif "bsi" in bank: bank_key = "BSI"
            
            if bank_key in saldo_bank_aktual:
                if kat == "pemasukan": saldo_bank_aktual[bank_key] += nominal
                elif kat == "pengeluaran": saldo_bank_aktual[bank_key] -= nominal
                
            # Hitung Akumulasi Berdasarkan Teks Label Pos Digital
            if "cadangan" in pos_rek:
                mutasi_pos_digital["cadangan_bisnis"] += nominal if kat == "pemasukan" else -nominal
            elif "rumah tangga" in pos_rek:
                mutasi_pos_digital["rumah_tangga"] += nominal if kat == "pemasukan" else -nominal
            elif "investasi" in pos_rek:
                mutasi_pos_digital["investasi"] += nominal if kat == "pemasukan" else -nominal
            elif "lifestyle" in pos_rek:
                mutasi_pos_digital["lifestyle"] += nominal if kat == "pemasukan" else -nominal

    # 4. GERBANG LOGIKA HYBRID: PENENTUAN GAJI & ALOKASI TARGET (DI ATAS KERTAS)
    GAJI_BASELINE_FLAT = 26259567.0
    status_darurat_aktif = False
    
    # Alokasi Hak Investor (7.5% dari laba bisnis riil)
    wajib_setor_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    kas_setelah_investor = max(0.0, kas_riil_bisnis_toko) - wajib_setor_investor
    
    # Pengkondisian Gaji Owner Baseline
    if kas_setelah_investor >= GAJI_BASELINE_FLAT:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = (kas_setelah_investor - GAJI_BASELINE_FLAT) * 0.40
    else:
        # Protokol Darurat Aktif: Kas toko tidak cukup membiayai gaji flat dasar
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True

    # Detail Pemecahan Pos Target Domestik Kertas (Rp26.259.567)
    target_kertas_domestik = {
        "1. Tempat Tinggal & Kendaraan (40.9%)": 10728067.0,
        "2. Rumah Tangga & Keluarga (25.8%)": 6768500.0,
        "3. Kebutuhan Pokok Hidup (19.0%)": 5000000.0,
        "4. Tagihan Bulanan & Ops (9.2%)": 2405000.0,
        "5. Edukasi, Anak & Sosial (5.1%)": 1358000.0
    }

    return {
        "laba_buku_total": laba_buku_total,
        "total_piutang": total_piutang,
        "kas_riil_bisnis_toko": kas_riil_bisnis_toko,
        "wajib_setor_investor": wajib_setor_investor,
        "gaji_owner_dialokasikan": gaji_owner_files_dialokasikan if 'gaji_owner_files_dialokasikan' in locals() else gaji_owner_dialokasikan,
        "cadangan_bisnis_kertas": cadangan_bisnis_40_kertas,
        "status_darurat_aktif": status_darurat_aktif,
        "saldo_bank_aktual": saldo_bank_aktual,
        "mutasi_pos_digital": mutasi_pos_digital,
        "target_kertas_domestik": target_kertas_domestik,
        "total_atm_pribadi": saldo_bank_aktual["BCA"] + saldo_bank_aktual["Mandiri"] + saldo_bank_aktual["BSI"]
    }
