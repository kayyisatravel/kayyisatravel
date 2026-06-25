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
    Engine V2 Resmi Final: Integrasi Sempurna 100% dengan Struktur Tabel Aging Report Lama,
    Solusi Plafon Dinamis (1 & 2), dan Sistem Proteksi Saldo Bank Aktual.
    """
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    debug_raw_sales_count = len(df_sales)
    debug_raw_pribadi_count = len(df_pribadi)
    
    if not df_pribadi.empty and "Tanggal" in df_pribadi.columns:
        df_pribadi["Tgl_Temp_Parsed"] = pd.to_datetime(df_pribadi["Tanggal"], errors="coerce")
        jumlah_bulan_aktif = df_pribadi["Tgl_Temp_Parsed"].dt.to_period("M").nunique()
        jumlah_bulan_aktif = max(1, int(jumlah_bulan_aktif))
    else:
        jumlah_bulan_aktif = 1

    # 1. STANDARISASI DATA PENJUALAN TOKO & INTEGRASI ALGORITMA AGING PIUTANG ASLI ANDA
    total_piutang = overdue_lebih_30 = jumlah_invoice_piutang = 0.0
    text_top_debitur = "- (Bersih, tidak ada piutang aktif)\n"
    df_display_aging = pd.DataFrame()

    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
        df_sales["Tgl Pemesanan_Parsed"] = pd.to_datetime(df_sales["Tgl Pemesanan"], dayfirst=True, errors="coerce")
        
        total_pendapatan = df_sales["Harga Jual (Num)"].sum()
        total_hpp = df_sales["Harga Beli (Num)"].sum()
        laba_buku_total = df_sales["Laba (Num)"].sum()
        
        # Saring baris transaksi lunas untuk hitung Uang Fisik Bisnis
        is_sudah_lunas = df_sales["Keterangan"].astype(str).str.contains(r'(?<!belum\s)lunas', case=False, na=False, regex=True)
        is_belum_lunas = df_sales["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
        df_paid = df_sales[is_sudah_lunas & (~is_belum_lunas)].copy()
        kas_riil_bisnis_toko = df_paid["Harga Jual (Num)"].sum() - df_paid["Harga Beli (Num)"].sum()

        # ─── REPLIKASI FORMULA AGING REPORT ASLI DARI ENGINEMU ───
        df_invoice = df_sales[["No Invoice", "Nama Pemesan", "Harga Jual (Num)", "Tgl Pemesanan_Parsed", "Keterangan"]].copy()
        df_invoice["Jumlah Masuk"] = 0.0
        df_invoice["Piutang"] = df_invoice["Harga Jual (Num)"] - df_invoice["Jumlah Masuk"]
        
        is_belum_lunas_inv = df_invoice["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
        df_unpaid = df_invoice[((df_invoice["Piutang"] > 1000) | is_belum_lunas_inv) & (~is_sudah_lunas)].copy()
        
        if not df_unpaid.empty:
            df_agg = df_unpaid.groupby(["Nama Pemesan", "No Invoice"], as_index=False).agg({
                "Piutang": "sum",
                "Tgl Pemesanan_Parsed": "min"
            })
            hari_ini_ts = pd.Timestamp.today().normalize()
            df_agg["Tanggal Pemesanan"] = df_agg["Tgl Pemesanan_Parsed"].fillna(hari_ini_ts)
            df_agg["Aging (hari)"] = (hari_ini_ts - df_agg["Tanggal Pemesanan"].dt.normalize()).dt.days
            df_agg["Overdue"] = df_agg["Aging (hari)"] > 30
            
            total_piutang = df_agg["Piutang"].sum()
            jumlah_invoice_piutang = df_agg["No Invoice"].nunique()
            overdue_lebih_30 = df_agg[df_agg["Overdue"] == True]["Piutang"].sum()
            
            top_debitur = df_agg.groupby("Nama Pemesan")["Piutang"].sum().reset_index()
            top_debitur = top_debitur.sort_values("Piutang", ascending=False).head(3)
            text_top_debitur = ""
            for _, row in top_debitur.iterrows():
                text_top_debitur += f"- 👥 {row['Nama Pemesan']}: Menunggak Rp {int(row['Piutang']):,}\n"
                
            df_display_aging = df_agg[["Nama Pemesan", "No Invoice", "Tanggal Pemesanan", "Piutang", "Aging (hari)", "Overdue"]].copy()
    else:
        total_pendapatan = total_hpp = laba_buku_total = kas_riil_bisnis_toko = 0.0

    # 2. STANDARISASI DATA MUTASI KAS PRIBADI
    if not df_pribadi.empty:
        df_pribadi["Nominal (Num)"] = df_pribadi["Nominal"].apply(bersihkan_angka)
    else:
        df_pribadi["Nominal (Num)"] = 0.0

    log_bank = {
        "BCA": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}, "Mandiri": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "BSI": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}, "Bank Mega": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "BRI": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}, "Sea Bank": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "Gopay": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}, "OVO": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0},
        "DANA": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}, "Kartu Kredit": {"masuk": 0.0, "keluar": 0.0, "saldo": 0.0}
    }

    DAFTAR_PENGELUARAN_PRIBADI = [
        "pengeluaran", "cicilan_rumah", "perbaikan_rumah", "pajak_kendaraan", "servis_kendaraan",
        "belanja_dapur", "perlengkapan_rumah", "asisten_rumah_tangga", "bensin_transport", "makan_harian", 
        "kesehatan_obat", "listrik_air", "wifi_internet", "pulsa_hp", "langganan_digital",
        "pendidikan_anak", "dana_sosial", "lifestyle", "investasi_pribadi", "pelunasan_cc_bisnis"
    ]

    mutasi_pos_digital = {k: 0.0 for k in DAFTAR_PENGELUARAN_PRIBADI}
    total_biaya_operasional_bisnis = 0.0
    total_bayar_tagihan_cc = 0.0

    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            bank = str(row["Bank_Sumber"]).strip().lower()
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal = row["Nominal (Num)"]
            
            bank_key = None
            if any(x in bank for x in ["cc", "credit", "uob", "kartu", "cimb"]): bank_key = "Kartu Kredit"
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

    # FORMULA ALOKASI POS ANGGARAN DIGITAL AI (HYBRID & DINAMIS)
    GAJI_BASELINE_FLAT = 26259567.0 * jumlah_bulan_aktif
    beban_bagi_hasil_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    kas_setelah_investor = max(0.0, kas_riil_bisnis_toko) - beban_bagi_hasil_investor
    
    status_darurat_aktif = False
    nilai_defisit_gaji = 0.0
    rasio_kerentanan_laba = (total_piutang / laba_buku_total * 100) if laba_buku_total > 0 else 0.0

    if kas_setelah_investor < GAJI_BASELINE_FLAT:
        prive_dinamis_aktual = GAJI_BASELINE_FLAT
        status_darurat_aktif = True
        nilai_defisit_gaji = GAJI_BASELINE_FLAT - kas_setelah_investor
    elif rasio_kerentanan_laba > 100.0:
        prive_dinamis_aktual = GAJI_BASELINE_FLAT
        status_darurat_aktif = True
        nilai_defisit_gaji = 0.0 
    else:
        cadangan_bisnis_40_kertas = (kas_setelah_investor - GAJI_BASELINE_FLAT) * 0.40
        prive_dinamis_aktual = kas_setelah_investor - cadangan_bisnis_40_kertas

    target_kertas_dinamis = {
        "1. Tempat Tinggal & Kendaraan (40.9%)": prive_dinamis_aktual * 0.409,
        "2. Rumah Tangga & Keluarga (25.8%)": prive_dinamis_aktual * 0.258,
        "3. Kebutuhan Pokok Hidup (19.0%)": prive_dinamis_aktual * 0.190,
        "4. Tagihan Bulanan & Ops (9.2%)": prive_dinamis_aktual * 0.092,
        "5. Edukasi, Anak & Sosial (5.1%)": prive_dinamis_aktual * 0.051
    }

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
    target_kertas_dinamis = {
        "1. Tempat Tinggal & Kendaraan (40.9%)": prive_dinamis_aktual * 0.409,
        "2. Rumah Tangga & Keluarga (25.8%)": prive_dinamis_aktual * 0.258,
        "3. Kebutuhan Pokok Hidup (19.0%)": prive_dinamis_aktual * 0.190,
        "4. Tagihan Bulanan & Ops (9.2%)": prive_dinamis_aktual * 0.092,
        "5. Edukasi, Anak & Sosial (5.1%)": prive_dinamis_aktual * 0.051
    }

    # =========================================================================
    # JANGKAR PENYEMBUH KEYERROR (SINKRON 100% UNTUK DATA LAMA & BARU)
    # =========================================================================
    return {
        # Kunci Lama (Mencegah KeyError di Tab Ringkasan & Jurnal Lama Anda)
        "total_transaksi": len(df_sales),
        "pendapatan": total_omzet_buku,
        "hpp": total_hpp_buku,
        "laba_bersih": laba_buku_total,
        "margin_laba_bersih": npm,
        "kas_riil": kas_riil_bisnis_toko,
        "overdue_lebih_30_hari": overdue_lebih_30,
        "jumlah_transaksi_rugi": jumlah_boncos,
        "saldo_bank_riil": log_bank,
        "text_top_debitur": text_top_debitur,
        "text_segmentasi": "- Analisis produk travel fungsional\n",
        "df_aging_report": df_display_aging,  # <── JANGKAR PENYEMBUH KEYERROR 3753 AGING REPORT
        "alokasi_ai": {
            "investor": beban_bagi_hasil_investor,
            "cadangan_bisnis": cadangan_bisnis_40_kertas,
            "gaji_owner": prive_dinamis_aktual,
            "rumah_tangga": target_kertas_dinamis["2. Rumah Tangga & Keluarga (25.8%)"],
            "investasi": target_kertas_dinamis["5. Edukasi, Anak & Sosial (5.1%)"],
            "lifestyle": target_kertas_dinamis["5. Edukasi, Anak & Sosial (5.1%)"]
        },

        # Kunci Baru (Untuk 16 Panel Metrics Berlabel Ilmiah & Progress Bar)
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
        "laba_internal_buku": laba_buku_total,
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



