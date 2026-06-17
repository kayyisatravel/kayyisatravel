import pandas as pd
import numpy as np
import re

def bersihkan_angka(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace("Rp", "").replace(" ", "").strip()
    if not s: return 0.0
    try:
        s = re.sub(r',(\d{2})$', '', s)
        s = re.sub(r'\.(\d{2})$', '', s)
        s = re.sub(r'[.,]', '', s)
        return float(s)
    except:
        s_clean = re.sub(r'[^\d.]', '', str(val).replace(",", "."))
        try: return float(s_clean)
        except: return 0.0

def hitung_hybrid_monitoring_v1(df_sales_raw, df_pribadi_raw):
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    # Hitung jumlah baris mentah untuk kebutuhan panel debugging
    debug_raw_sales_count = len(df_sales)
    debug_raw_pribadi_count = len(df_pribadi)
    
    # 1. STANDARISASI DATA PENJUALAN TOKO
    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
    else:
        df_sales["Harga Beli (Num)"] = 0.0
        df_sales["Harga Jual (Num)"] = 0.0
        df_sales["Laba (Num)"] = 0.0

    # 2. STANDARISASI DATA MUTASI KAS PRIBADI
    if not df_pribadi.empty:
        df_pribadi["Nominal (Num)"] = df_pribadi["Nominal"].apply(bersihkan_angka)
    else:
        df_pribadi["Nominal (Num)"] = 0.0

    # 3. SEGREGASI KAS LUNAS VS PIUTANG AKTIF
    if "Keterangan" in df_sales.columns:
        # Mengunci filter murni hanya pada kata kunci 'Belum Lunas'
        is_belum_lunas = df_sales["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
    else:
        is_belum_lunas = False
        
    df_unpaid = df_sales[is_belum_lunas].copy()
    df_paid = df_sales[~is_belum_lunas].copy()
    
    # KALKULASI AMBANG BATAS PIUTANG
    total_piutang = df_unpaid["Harga Jual (Num)"].sum() if not df_unpaid.empty else 0.0
    jumlah_invoice_piutang = df_unpaid["No Invoice"].nunique() if not df_unpaid.empty else 0
    
    # REVISI FORMULA HUKUM BESI KAS: Hanya kurangi HPP dari transaksi yang sudah lunas (Uang Masuk)
    omzet_lunas_riil = df_paid["Harga Jual (Num)"].sum() if not df_paid.empty else 0.0
    hpp_lunas_riil = df_paid["Harga Beli (Num)"].sum() if not df_paid.empty else 0.0
    kas_riil_bisnis_toko = omzet_lunas_riil - hpp_lunas_riil
    
    total_omzet_buku = df_sales["Harga Jual (Num)"].sum()
    total_hpp_buku = df_sales["Harga Beli (Num)"].sum()
    laba_buku_total = df_sales["Laba (Num)"].sum()

    # 4. METRIK RASIO PROFITABILITAS CORPORATE
    npm = (laba_buku_total / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    roi = (laba_buku_total / total_hpp_buku * 100) if total_hpp_buku > 0 else 0.0
    rasio_keterikatan_modal = (total_piutang / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    rasio_kerentanan_laba = (total_piutang / laba_buku_total * 100) if laba_buku_total > 0 else 0.0

    # 5. BALANCING TRANSPARANSI BUKU BANK AKTUAL
    log_bank = {
        "BCA": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Mandiri": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "BSI": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Kartu Kredit": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}
    }
    mutasi_pos_digital = {"cadangan_bisnis": 0.0, "rumah_tangga": 0.0, "investasi": 0.0, "lifestyle": 0.0}

    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            bank = str(row["Bank_Sumber"]).strip().lower()
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal = row["Nominal (Num)"]
            
            bank_key = None
            if "cc" in bank or "credit" in bank or "uob" in bank or "mega" in bank: bank_key = "Kartu Kredit"
            elif "mandiri" in bank: bank_key = "Mandiri"
            elif "bca" in bank: bank_key = "BCA"
            elif "bsi" in bank: bank_key = "BSI"
            
            if bank_key in log_bank:
                if kat == "pemasukan":
                    log_bank[bank_key]["masuk"] += nominal
                    log_bank[bank_key]["saldo"] += nominal
                elif kat == "pengeluaran":
                    log_bank[bank_key]["keluar"] += nominal
                    log_bank[bank_key]["saldo"] -= nominal
                    
            if "cadangan" in pos_rek: mutasi_pos_digital["cadangan_bisnis"] += nominal if kat == "pemasukan" else -nominal
            elif "rumah tangga" in pos_rek: mutasi_pos_digital["rumah_tangga"] += nominal if kat == "pemasukan" else -nominal
            elif "investasi" in pos_rek: mutasi_pos_digital["investasi"] += nominal if kat == "pemasukan" else -nominal
            elif "lifestyle" in pos_rek: mutasi_pos_digital["lifestyle"] += nominal if kat == "pemasukan" else -nominal

    total_atm_pribadi = log_bank["BCA"]["saldo"] + log_bank["Mandiri"]["saldo"] + log_bank["BSI"]["saldo"]
    total_cash_in_pribadi = sum(info["masuk"] for info in log_bank.values())
    total_cash_out_pribadi = sum(info["keluar"] for info in log_bank.values())
    rasio_menabung_domestik = (total_atm_pribadi / total_cash_in_pribadi * 100) if total_cash_in_pribadi > 0 else 0.0

    # 6. PROTOKOL ALOKASI BASELINE FIXED COST
    GAJI_BASELINE_FLAT = 26259567.0
    wajib_setor_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    kas_setelah_investor = max(0.0, kas_riil_bisnis_toko) - wajib_setor_investor
    
    status_darurat_aktif = False
    nilai_defisit_gaji = 0.0
    
    if kas_setelah_investor >= GAJI_BASELINE_FLAT:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = (kas_setelah_investor - GAJI_BASELINE_FLAT) * 0.40
    else:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True
        nilai_defisit_gaji = GAJI_BASELINE_FLAT - kas_setelah_investor

    daya_tahan_bulan = (total_atm_pribadi / GAJI_BASELINE_FLAT) if total_atm_pribadi > 0 else 0.0

    # 7. FORENSIK DETEKSI TRANSAKSI RUGI
    transaksi_boncos = df_sales[df_sales["Laba (Num)"] < 0] if not df_sales.empty else pd.DataFrame()
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = abs(transaksi_boncos["Laba (Num)"].sum()) if not transaksi_boncos.empty else 0.0

    top_admin = "N/A"
    if not df_sales.empty and "Admin" in df_sales.columns:
        mode_admin = df_sales["Admin"].dropna().mode()
        if not mode_admin.empty: top_admin = str(mode_admin[0])

    total_aset_lancar_toko = max(0.0, kas_riil_bisnis_toko) + total_piutang

    return {
        "npm": npm, "roi": roi, "total_tiket_terjual": len(df_sales), "laba_per_tiket": (laba_buku_total / len(df_sales)) if len(df_sales) > 0 else 0.0,
        "kas_riil_bisnis_toko": kas_riil_bisnis_toko, "total_piutang": total_piutang, "rasio_keterikatan_modal": rasio_keterikatan_modal, "rasio_kerentanan_laba": rasio_kerentanan_laba,
        "jumlah_invoice_piutang": jumlah_invoice_piutang, "total_cash_in_pribadi": total_cash_in_pribadi, "total_cash_out_pribadi": total_cash_out_pribadi, "rasio_menabung_domestik": rasio_menabung_domestik,
        "beban_cc_aktual": log_bank["Kartu Kredit"]["saldo"], "total_atm_pribadi": total_atm_pribadi, "daya_tahan_bulan": daya_tahan_bulan, "total_aset_lancar_toko": total_aset_lancar_toko,
        "laba_buku_total": laba_buku_total, "jumlah_boncos": jumlah_boncos, "total_kerugian": total_kerugian, "top_admin": top_admin,
        "wajib_setor_investor": wajib_setor_investor, "gaji_owner_dialokasikan": gaji_owner_dialokasikan, "cadangan_bisnis_kertas": cadangan_bisnis_40_kertas,
        "status_darurat_aktif": status_darurat_aktif, "nilai_defisit_gaji": nilai_defisit_gaji,
        "log_bank_pribadi": log_bank, "mutasi_pos_digital": mutasi_pos_digital,
        "target_kertas_domestik": {"1. Tempat Tinggal & Kendaraan (40.9%)": 10728067.0, "2. Rumah Tangga & Keluarga (25.8%)": 6768500.0, "3. Kebutuhan Pokok Hidup (19.0%)": 5000000.0, "4. Tagihan Bulanan & Ops (9.2%)": 2405000.0, "5. Edukasi, Anak & Sosial (5.1%)": 1358000.0},
        "total_omzet_buku": total_omzet_buku, "total_hpp_buku": total_hpp_buku,
        # Variabel Debug Passthrough
        "debug_raw_sales_count": debug_raw_sales_count, "debug_raw_pribadi_count": debug_raw_pribadi_count
    }
