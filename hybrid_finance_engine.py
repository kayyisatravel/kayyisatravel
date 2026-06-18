# hybrid_finance_engine.py
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

def hitung_hybrid_monitoring_v2(df_sales_raw, df_pribadi_raw):
    """
    Engine V2: Mengintegrasikan 100% Logika Alokasi Lama dengan 
    Mekanisme Deteksi Pelunasan Otomatis dari Sheet Pribadi.
    """
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    # Mengembalikan nilai passthrough untuk Panel Debugging UI
    debug_raw_sales_count = len(df_sales)
    debug_raw_pribadi_count = len(df_pribadi)
    
    # 1. STANDARISASI DATA PENJUALAN TOKO (BUKU UTAMA)
    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
    else:
        df_sales["Harga Beli (Num)"], df_sales["Harga Jual (Num)"], df_sales["Laba (Num)"] = 0.0, 0.0, 0.0

    # 2. STANDARISASI DATA MUTASI KAS PRIBADI (Perbaikan Bug String)
    if not df_pribadi.empty:
        df_pribadi["Nominal (Num)"] = df_pribadi["Nominal"].apply(bersihkan_angka)
    else:
        df_pribadi["Nominal (Num)"] = 0.0

    # =========================================================================
    # JEMBATAN LOGIKA BARU: DETEKSI PELUNASAN INVOICE DARI SHEET PRIBADI
    # =========================================================================
    def ekstrak_nomor_invoice(teks):
        teks_str = str(teks).upper()
        # Mencari pola teks INV diikuti tanda hubung/spasi opasional dan angka (Contoh: INV-001)
        match = re.search(r'INV[-\s]?\d+', teks_str)
        if match:
            return match.group(0).replace(" ", "-")
        return None

    # Isolasi mutasi masuk dari konsumen di rekening pribadi owner
    df_pribadi["No_Invoice_Terdeteksi"] = df_pribadi["Keterangan"].apply(ekstrak_nomor_invoice)
    df_pribadi_masuk = df_pribadi[df_pribadi["Kategori"].str.lower().str.contains("pemasukan", na=False)].copy()
    
    # Hitung akumulasi transfer masuk per nomor invoice nyata
    if not df_pribadi_masuk.empty:
        df_terbayar_agg = df_pribadi_masuk.dropna(subset=["No_Invoice_Terdeteksi"]).groupby("No_Invoice_Terdeteksi")["Nominal (Num)"].sum().reset_index()
        df_terbayar_agg.columns = ["No Invoice", "Total_Terbayar_Fisik"]
    else:
        df_terbayar_agg = pd.DataFrame(columns=["No Invoice", "Total_Terbayar_Fisik"])

    # Hitung piutang terintegrasi (Vektorisasi Kilat)
    if not df_sales.empty:
        df_sales_agg = df_sales.groupby("No Invoice")["Harga Jual (Num)"].sum().reset_index()
        df_piutang_skenario = df_sales_agg.merge(df_terbayar_agg, on="No Invoice", how="left").fillna(0.0)
        df_piutang_skenario["Sisa_Piutang"] = (df_piutang_skenario["Harga Jual (Num)"] - df_piutang_skenario["Total_Terbayar_Fisik"]).clip(lower=0.0)
        
        # Ekstraksi hasil akhir untuk metrik dashboard
        total_piutang = df_piutang_skenario["Sisa_Piutang"].sum()
        jumlah_invoice_piutang = len(df_piutang_skenario[df_piutang_skenario["Sisa_Piutang"] > 0])
        
        # KAS RIIL BISNIS = Total dana masuk yang teridentifikasi milik toko (Bukan uang pribadi)
        kas_riil_bisnis_toko = df_piutang_skenario["Total_Terbayar_Fisik"].sum()
    else:
        total_piutang, jumlah_invoice_piutang, kas_riil_bisnis_toko = 0.0, 0, 0.0

    # =========================================================================
    # KEMBALI KE 100% RUMUS LOGIKA CORPORATE LAMA ANDA
    # =========================================================================
    total_omzet_buku = df_sales["Harga Jual (Num)"].sum()
    total_hpp_buku = df_sales["Harga Beli (Num)"].sum()
    laba_buku_total = df_sales["Laba (Num)"].sum()

    npm = (laba_buku_total / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    roi = (laba_buku_total / total_hpp_buku * 100) if total_hpp_buku > 0 else 0.0
    rasio_keterikatan_modal = (total_piutang / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    rasio_kerentanan_laba = (total_piutang / laba_buku_total * 100) if laba_buku_total > 0 else 0.0

    # BALANCING TRANSPARANSI BUKU BANK AKTUAL
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
            if any(x in bank for x in ["cc", "credit", "uob", "mega"]): bank_key = "Kartu Kredit"
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

    # PROTOKOL ALOKASI BASELINE FIXED COST LAMA Anda
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

    # FORENSIK DETEKSI TRANSAKSI RUGI LAMA Anda
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
