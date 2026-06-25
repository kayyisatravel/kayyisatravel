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

def hitung_hybrid_monitoring_v2(df_sales_raw, df_pribadi_raw, jurnal_data=None):
    """
    Engine V2 Resmi: Diperbarui dengan Formula Plafon Anggaran Dinamis (Solusi 1 & 2)
    Melacak realisasi 19 Sub-Kategori domestik dan mengamankan Laporan SAK EMKM.
    """
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    debug_raw_sales_count = len(df_sales)
    debug_raw_pribadi_count = len(df_pribadi)
    
    # ─────────────────────────────────────────────────────────────────
    # SINKRONISASI SOLUSI 1: HITUNG JUMLAH BULAN UNIK YANG TERFILTER
    # ─────────────────────────────────────────────────────────────────
    # Membaca kolom Tanggal untuk mendeteksi rentang waktu data yang aktif di layar
    if not df_pribadi.empty and "Tanggal" in df_pribadi.columns:
        df_pribadi["Tgl_Temp_Parsed"] = pd.to_datetime(df_pribadi["Tanggal"], errors="coerce")
        jumlah_bulan_aktif = df_pribadi["Tgl_Temp_Parsed"].dt.to_period("M").nunique()
        jumlah_bulan_aktif = max(1, int(jumlah_bulan_aktif)) # Pengaman minimal 1 bulan
    else:
        jumlah_bulan_aktif = 1

    # 1. STANDARISASI DATA PENJUALAN TOKO (BUKU UTAMA)
    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
        
        df_sales["No Invoice"] = df_sales["No Invoice"].fillna("").astype(str).str.strip()
        
        is_belum_lunas = df_sales["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
        is_sudah_lunas = df_sales["Keterangan"].astype(str).str.contains(r'(?<!belum\s)lunas', case=False, na=False, regex=True)
        
        df_unpaid = df_sales[is_belum_lunas & (~is_sudah_lunas)].copy()
        
        if not df_unpaid.empty:
            df_agg_piutang = df_unpaid.groupby("No Invoice", as_index=False).agg({"Harga Jual (Num)": "sum"})
            total_piutang = df_agg_piutang["Harga Jual (Num)"].sum()
            df_agg_piutang_clean = df_agg_piutang[df_agg_piutang["No Invoice"] != ""]
            jumlah_invoice_piutang = df_agg_piutang_clean["No Invoice"].nunique()
        else:
            total_piutang = 0.0
            jumlah_invoice_piutang = 0
            
        df_paid = df_sales[is_sudah_lunas & (~is_belum_lunas)].copy()
        kas_riil_bisnis_toko = df_paid["Harga Jual (Num)"].sum() - df_paid["Harga Beli (Num)"].sum()
    else:
        df_sales["Harga Beli (Num)"], df_sales["Harga Jual (Num)"], df_sales["Laba (Num)"] = 0.0, 0.0, 0.0
        total_piutang = kas_riil_bisnis_toko = 0.0
        jumlah_invoice_piutang = 0

    # 2. STANDARISASI DATA MUTASI KAS PRIBADI
    if not df_pribadi.empty:
        df_pribadi["Nominal (Num)"] = df_pribadi["Nominal"].apply(bersihkan_angka)
    else:
        df_pribadi["Nominal (Num)"] = 0.0

    total_omzet_buku = df_sales["Harga Jual (Num)"].sum()
    total_hpp_buku = df_sales["Harga Beli (Num)"].sum()
    laba_buku_total = df_sales["Laba (Num)"].sum()

    npm = (laba_buku_total / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    roi = (laba_buku_total / total_hpp_buku * 100) if total_hpp_buku > 0 else 0.0
    rasio_keterikatan_modal = (total_piutang / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    
    log_bank = {
        "BCA": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Mandiri": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "BSI": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Bank Mega": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "BRI": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Sea Bank": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Gopay": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "OVO": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "DANA": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Kartu Kredit": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}
    }

    DAFTAR_PENGELUARAN_PRIBADI = [
        "pengeluaran", "cicilan_rumah", "perbaikan_rumah", "pajak_kendaraan", "servis_kendaraan",
        "belanja_dapur", "perlengkapan_rumah", "asisten_rumah_tangga",
        "bensin_transport", "makan_harian", "kesehatan_obat",
        "listrik_air", "wifi_internet", "pulsa_hp", "langganan_digital",
        "pendidikan_anak", "dana_sosial", "lifestyle", "investasi_pribadi", "pelunasan_cc_bisnis"
    ]

    mutasi_pos_digital = {
        "cicilan_rumah": 0.0, "perbaikan_rumah": 0.0, "pajak_kendaraan": 0.0, "servis_kendaraan": 0.0,
        "belanja_dapur": 0.0, "perlengkapan_rumah": 0.0, "asisten_rumah_tangga": 0.0,
        "bensin_transport": 0.0, "makan_harian": 0.0, "kesehatan_obat": 0.0,
        "listrik_air": 0.0, "wifi_internet": 0.0, "pulsa_hp": 0.0, "langganan_digital": 0.0,
        "pendidikan_anak": 0.0, "dana_sosial": 0.0, "lifestyle": 0.0, "investasi_pribadi": 0.0,
        "pelunasan_cc_bisnis": 0.0
    }

    total_biaya_operasional_bisnis = 0.0 
    total_bayar_tagihan_cc = 0.0

    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            bank = str(row["Bank_Sumber"]).strip().lower()
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal = row["Nominal (Num)"]
            
            bank_key = None
            if any(x in bank for x in ["cc", "credit", "uob", "kartu kredit", "cimb"]): bank_key = "Kartu Kredit"
            elif "mandiri" in bank: bank_key = "Mandiri"
            elif "bca" in bank: bank_key = "BCA"
            elif "bsi" in bank: bank_key = "BSI"
            elif "mega" in bank: bank_key = "Bank Mega"
            elif "bri" in bank: bank_key = "BRI"
            elif "sea" in bank: bank_key = "Sea Bank"
            elif "gopay" in bank or "gojek" in bank: bank_key = "Gopay"
            elif "ovo" in bank: bank_key = "OVO"
            elif "dana" in bank: bank_key = "DANA"
            
            if bank_key in log_bank:
                if kat == "pemasukan":
                    log_bank[bank_key]["masuk"] += nominal
                    log_bank[bank_key]["saldo"] += nominal
                elif kat in DAFTAR_PENGELUARAN_PRIBADI:
                    log_bank[bank_key]["keluar"] += nominal
                    log_bank[bank_key]["saldo"] -= nominal
            
            if kat in mutasi_pos_digital:
                mutasi_pos_digital[kat] += nominal

            if kat in ["pengeluaran", "peralatan_kantor", "ops_bisnis"]:
                if any(x in pos_rek for x in ["cadangan", "aset kantor"]):
                    total_biaya_operasional_bisnis += nominal

            if kat == "pelunasan_cc_bisnis" or "tagihan cc" in str(row.get("Keterangan", "")).lower():
                total_bayar_tagihan_cc += nominal

    total_atm_pribadi = sum(info["saldo"] for bank_nm, info in log_bank.items() if bank_nm != "Kartu Kredit")
    total_cash_in_pribadi = sum(info["masuk"] for info in log_bank.values())
    total_cash_out_pribadi = sum(info["keluar"] for info in log_bank.values())
    rasio_menabung_domestik = (total_atm_pribadi / total_cash_in_pribadi * 100) if total_cash_in_pribadi > 0 else 0.0

    # ─────────────────────────────────────────────────────────────────
    # SINKRONISASI SOLUSI 2: FORMULA GAJI / PRIVE OWNER DINAMIS
    # ─────────────────────────────────────────────────────────────────
    GAJI_BASELINE_FLAT = 26259567.0 * jumlah_bulan_aktif
    beban_bagi_hasil_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    kas_setelah_investor = max(0.0, kas_riil_bisnis_toko) - beban_bagi_hasil_investor
    
    status_darurat_aktif = False
    nilai_defisit_gaji = 0.0
    rasio_kerentanan_laba = (total_piutang / laba_buku_total * 100) if laba_buku_total > 0 else 0.0

    # Penentuan batas dana domestik aktual (Jika untung besar, jatah prive membesar secara otomatis)
    if kas_setelah_investor < GAJI_BASELINE_FLAT:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True
        nilai_defisit_gaji = GAJI_BASELINE_FLAT - kas_setelah_investor
        prive_dinamis_aktual = GAJI_BASELINE_FLAT
    elif rasio_kerentanan_laba > 100.0:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True
        nilai_defisit_gaji = 0.0 
        prive_dinamis_aktual = GAJI_BASELINE_FLAT
    else:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = (kas_setelah_investor - GAJI_BASELINE_FLAT) * 0.40
        # Kombinasi: Sisa kas setelah dipotong 40% cadangan fisik adalah Hak Prive Dinamis Pemilik Seutuhnya
        prive_dinamis_aktual = kas_setelah_investor - cadangan_bisnis_40_kertas

    transaksi_boncos = df_sales[df_sales["Laba (Num)"] < 0] if not df_sales.empty else pd.DataFrame()
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = abs(transaksi_boncos["Laba (Num)"].sum()) if not transaksi_boncos.empty else 0.0

    top_admin = "N/A"
    if not df_sales.empty and "Admin" in df_sales.columns:
        mode_admin = df_sales["Admin"].dropna().mode()
        if not mode_admin.empty: top_admin = str(mode_admin[0])

    total_aset_lancar_toko = max(0.0, kas_riil_bisnis_toko) + total_piutang

    # --- OPERASIONAL KARTU KREDIT KULAKAN BISNIS ---
    outstanding_cc_total = 0.0
    if not df_sales.empty and "Sumber Dana" in df_sales.columns:
        mask_sumber_cc = df_sales["Sumber Dana"].astype(str).str.lower().str.contains("credit|cc|kartu", na=False)
        df_cc_all = df_sales[mask_sumber_cc].copy()
        if not df_cc_all.empty:
            df_cc_all["Tgl_Parsed_CC"] = pd.to_datetime(df_cc_all["Tgl Pemesanan"], dayfirst=True, errors="coerce")
            df_cc_cutoff = df_cc_all[df_cc_all["Tgl_Parsed_CC"] >= pd.Timestamp("2026-05-01")]
            outstanding_cc_total = df_cc_cutoff["Harga Beli (Num)"].sum()

    outstanding_cc_final = max(0.0, outstanding_cc_total - total_bayar_tagihan_cc)
    laba_bersih_riil_bisnis = laba_buku_total - total_biaya_operasional_bisnis - beban_bagi_hasil_investor
    daya_tahan_bulan = (kas_riil_bisnis_toko / (GAJI_BASELINE_FLAT / jumlah_bulan_aktif)) if kas_riil_bisnis_toko > 0 else 0.0

    # ─────────────────────────────────────────────────────────────────
    # IMPLEMENTASI TARGET KERTAS DOMESTIK BERBASIS LABA DINAMIS & BULAN
    # ─────────────────────────────────────────────────────────────────
    # Jatah nominal sub-kategori membesar proporsional mengikuti Laba Berjalan & Kelipatan Bulan Filter
    target_kertas_dinamis = {
        "1. Tempat Tinggal & Kendaraan (40.9%)": prive_dinamis_aktual * 0.409,
        "2. Rumah Tangga & Keluarga (25.8%)": prive_dinamis_aktual * 0.258,
        "3. Kebutuhan Pokok Hidup (19.0%)": prive_dinamis_aktual * 0.190,
        "4. Tagihan Bulanan & Ops (9.2%)": prive_dinamis_aktual * 0.092,
        "5. Edukasi, Anak & Sosial (5.1%)": prive_dinamis_aktual * 0.051
    }

    return {
        "npm": npm,
        "roi": roi,
        "total_tiket_terjual": len(df_sales),
        "laba_per_tiket": (laba_buku_total / len(df_sales)) if len(df_sales) > 0 else 0.0,
        "kas_riil_bisnis_toko": kas_riil_bisnis_toko,
        "total_piutang": total_piutang,
        "rasio_keterikatan_modal": rasio_keterikatan_modal,
        "rasio_kerentanan_laba": rasio_kerentanan_laba,
        "jumlah_invoice_piutang": jumlah_invoice_piutang,
        "total_cash_in_pribadi": total_cash_in_pribadi,
        "total_cash_out_pribadi": total_cash_out_pribadi,
        "rasio_menabung_domestik": rasio_menabung_domestik,
        "beban_cc_aktual": outstanding_cc_final,
        "total_atm_pribadi": total_atm_pribadi,
        "daya_tahan_bulan": daya_tahan_bulan,
        "wajib_setor_investor": beban_bagi_hasil_investor,
        "laba_bersih_riil_bisnis": laba_bersih_riil_bisnis,
        "total_biaya_operasional_bisnis": total_biaya_operasional_bisnis,
        "total_aset_lancar_toko": total_aset_lancar_toko,
        "laba_buku_total": laba_buku_total,
        "jumlah_boncos": jumlah_boncos,
        "total_kerugian": total_kerugian,
        "top_admin": top_admin,
        "gaji_owner_dialokasikan": prive_dinamis_aktual, 
        "cadangan_bisnis_kertas": cadangan_bisnis_40_kertas,
        "status_darurat_aktif": status_darurat_aktif,
        "nilai_defisit_gaji": nilai_defisit_gaji,
        "log_bank_pribadi": log_bank,
        "mutasi_pos_digital": mutasi_pos_digital,
        "target_kertas_domestik": target_kertas_dinamis, 
        "total_omzet_buku": total_omzet_buku,
        "total_hpp_buku": total_hpp_buku,
        "debug_raw_sales_count": debug_raw_sales_count,
        "debug_raw_pribadi_count": debug_raw_pribadi_count
    }


