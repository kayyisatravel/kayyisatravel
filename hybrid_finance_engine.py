# hybrid_finance_engine.py
import pandas as pd
import numpy as np
import re
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import os

# =========================================================================
# 1. SKEMA DATA PYDANTIC UNTUK MENGUNCI FORMAT OUTPUT AI GEMINI
# =========================================================================
class AICategorizationSchema(BaseModel):
    id_pos_terpilih: int = Field(description="Nomor pos anggaran dari 1 sampai 5 berdasarkan makna teks keterangan.")
    nama_pos_terpilih: str = Field(description="Nama label pos anggaran yang dipilih.")
    analisis_konteks: str = Field(description="Alasan singkat mengapa AI memilih pos tersebut.")

def pilah_pengeluaran_domestik_dengan_gemini(keterangan_transaksi: str) -> int:
    """
    Menggunakan Gemini 3.1 Flash Lite + Pydantic Structured Output 
    untuk memilah pengeluaran berdasarkan arti teks secara dinamis.
    """
    # Ambil kunci otentikasi resmi dari st.secrets
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
    except Exception:
        # Fallback aman jika API Key tidak ditemukan/gagal koneksi
        return 2

    # Instruksi kaku prompt engineer untuk melatih otak Gemini
    prompt_rules = f"""
    Anda adalah sistem kecerdasan buatan entri data akuntansi profesional terpadu.
    Tugas Anda adalah membaca kalimat pengeluaran domestik rumah tangga berikut dan mengklasifikasikannya ke salah satu dari 5 pos ini:
    
    Pos 1: Tempat Tinggal & Kendaraan (Cicilan ruko, cicilan rumah, kontrakan, mobil, motor)
    Pos 2: Rumah Tangga & Keluarga (Belanja harian umum, perlengkapan umum, pasar, swalayan)
    Pos 3: Kebutuhan Pokok Hidup (Pangan, makanan, galon air, beras, sayur, McD, KFC, kuliner, restoran)
    Pos 4: Tagihan Bulanan & Ops (Listrik, token, PLN, PDAM, air, pulsa, wifi, internet, sapu, alat pembersih rumah)
    Pos 5: Edukasi, Anak & Sosial (Sekolah, SPP, les, Inggris, bisyaroh, ustadzah, ngaji, kursus, infak, sedekah)
    
    Kalimat Transaksi: "{keterangan_transaksi}"
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt_rules,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AICategorizationSchema, # Mengunci output AI secara kaku via Pydantic
                temperature=0.1
            ),
        )
        # Ekstrak hasil JSON bersih yang sudah tervalidasi
        import json
        parsed_result = json.loads(response.text)
        return int(parsed_result["id_pos_terpilih"])
    except Exception:
        # Fallback sistem: Jika internet putus, masukkan ke Pos 2 (Rumah Tangga Umum) agar sistem tidak crash
        return 2


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
    Engine V2 Resmi: Menggunakan logika filter status berbasis Regex Negatif 
    agar sinkron 100% dengan realitas pembukuan travel dan responsif terhadap filter.
    """
    df_sales = df_sales_raw.copy().reset_index(drop=True)
    df_pribadi = df_pribadi_raw.copy().reset_index(drop=True)
    
    # Nilai passthrough untuk Panel Debugging UI
    debug_raw_sales_count = len(df_sales)
    debug_raw_pribadi_count = len(df_pribadi)
    
    # 1. STANDARISASI DATA PENJUALAN TOKO (BUKU UTAMA)
    if not df_sales.empty:
        df_sales["Harga Beli (Num)"] = df_sales["Harga Beli"].apply(bersihkan_angka)
        df_sales["Harga Jual (Num)"] = df_sales["Harga Jual"].apply(bersihkan_angka)
        df_sales["Laba (Num)"] = df_sales["Harga Jual (Num)"] - df_sales["Harga Beli (Num)"]
        
        # ─────────────────────────────────────────────────────────────────
        # INTEGRASI LOGIKA VALID: DETEKSI STATUS BELUM LUNAS VS LUNAS
        # ─────────────────────────────────────────────────────────────────
        # Normalisasi teks kolom No Invoice agar string murni
        df_sales["No Invoice"] = df_sales["No Invoice"].fillna("").astype(str).str.strip()
        
        # Sensor pencari status menggunakan rumus andalan Anda
        is_belum_lunas = df_sales["Keterangan"].astype(str).str.contains("Belum Lunas", case=False, na=False)
        is_sudah_lunas = df_sales["Keterangan"].astype(str).str.contains(r'(?<!belum\s)lunas', case=False, na=False, regex=True)
        
        # Saring baris yang murni merupakan piutang aktif
        df_unpaid = df_sales[is_belum_lunas & (~is_sudah_lunas)].copy()
        
        if not df_unpaid.empty:
            # Kelompokkan murni berdasarkan No Invoice tunggal untuk meringkas nota bulk
            df_agg_piutang = df_unpaid.groupby("No Invoice", as_index=False).agg({"Harga Jual (Num)": "sum"})
            total_piutang = df_agg_piutang["Harga Jual (Num)"].sum()
            # Mencegah nomor invoice kosong ikut terhitung sebagai nota aktif
            df_agg_piutang_clean = df_agg_piutang[df_agg_piutang["No Invoice"] != ""]
            jumlah_invoice_piutang = df_agg_piutang_clean["No Invoice"].nunique()
        else:
            total_piutang = 0.0
            jumlah_invoice_piutang = 0
            
        # Hitung omzet dari baris transaksi yang terdeteksi sudah lunas
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

    # =========================================================================
    # KEMBALI KE 100% RUMUS LOGIKA CORPORATE LAMA ANDA
    # =========================================================================
    total_omzet_buku = df_sales["Harga Jual (Num)"].sum()
    total_hpp_buku = df_sales["Harga Beli (Num)"].sum()
    laba_buku_total = df_sales["Laba (Num)"].sum()

    npm = (laba_buku_total / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    roi = (laba_buku_total / total_hpp_buku * 100) if total_hpp_buku > 0 else 0.0
    rasio_keterikatan_modal = (total_piutang / total_omzet_buku * 100) if total_omzet_buku > 0 else 0.0
    
    # BALANCING TRANSPARANSI BUKU BANK AKTUAL
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

    mutasi_pos_digital = {"cadangan_bisnis": 0.0, "rumah_tangga": 0.0, "investasi": 0.0, "lifestyle": 0.0}

    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            bank = str(row["Bank_Sumber"]).strip().lower()
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            keterangan_riil = str(row.get("Keterangan", "")).strip()
            nominal = row["Nominal (Num)"]
            if kat == "pengeluaran" and keterangan_riil != "":
                # Serahkan teks keterangan ke Otak AI Gemini untuk ditentukan ID Pos-nya
                id_pos_keputusan_ai = pilah_pengeluaran_domestik_dengan_gemini(keterangan_riil)
                
                # Distribusi nominal uang secara akurat berdasarkan keputusan AI
                if id_pos_keputusan_ai == 1: mutasi_pos_digital["cicilan"] += nominal
                elif id_pos_keputusan_ai == 2: mutasi_pos_digital["rumah_tangga"] += nominal
                elif id_pos_keputusan_ai == 3: mutasi_pos_digital["pangan"] += nominal
                elif id_pos_keputusan_ai == 4: mutasi_pos_digital["tagihan"] += nominal
                elif id_pos_keputusan_ai == 5: mutasi_pos_digital["edukasi"] += nominal
            
            bank_key = None
            if any(x in bank for x in ["cc", "credit", "uob", "kartu kredit"]): bank_key = "Kartu Kredit"
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
                elif kat == "pengeluaran":
                    log_bank[bank_key]["keluar"] += nominal
                    log_bank[bank_key]["saldo"] -= nominal
                    
            if "cadangan" in pos_rek: mutasi_pos_digital["cadangan_bisnis"] += nominal if kat == "pemasukan" else -nominal
            elif "rumah tangga" in pos_rek: mutasi_pos_digital["rumah_tangga"] += nominal if kat == "pemasukan" else -nominal
            elif "investasi" in pos_rek: mutasi_pos_digital["investasi"] += nominal if kat == "pemasukan" else -nominal
            elif "lifestyle" in pos_rek: mutasi_pos_digital["lifestyle"] += nominal if kat == "pemasukan" else -nominal

    total_atm_pribadi = sum(info["saldo"] for bank_nm, info in log_bank.items() if bank_nm != "Kartu Kredit")

    total_cash_in_pribadi = sum(info["masuk"] for info in log_bank.values())
    total_cash_out_pribadi = sum(info["keluar"] for info in log_bank.values())
    rasio_menabung_domestik = (total_atm_pribadi / total_cash_in_pribadi * 100) if total_cash_in_pribadi > 0 else 0.0

    # PROTOKOL ALOKASI BASELINE FIXED COST LAMA Anda
    GAJI_BASELINE_FLAT = 26259567.0
    wajib_setor_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    kas_setelah_investor = max(0.0, kas_riil_bisnis_toko) - wajib_setor_investor
    
    # =========================================================================
    # BLOK A: LOGIKA STATUS DARURAT & GAJI FIXED COST FLATS
    # =========================================================================
    status_darurat_aktif = False
    nilai_defisit_gaji = 0.0
    rasio_kerentanan_laba = (total_piutang / laba_buku_total * 100) if laba_buku_total > 0 else 0.0

    if kas_setelah_investor < GAJI_BASELINE_FLAT:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True
        nilai_defisit_gaji = GAJI_BASELINE_FLAT - kas_setelah_investor
    elif rasio_kerentanan_laba > 100.0:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = 0.0
        status_darurat_aktif = True
        # Defisit diisi 0 karena kas fisik aman, tetapi lampu darurat wajib menyala sebagai peringatan piutang macet
        nilai_defisit_gaji = 0.0 
    else:
        gaji_owner_dialokasikan = GAJI_BASELINE_FLAT
        cadangan_bisnis_40_kertas = (kas_setelah_investor - GAJI_BASELINE_FLAT) * 0.40

    # =========================================================================
    # BLOK B: FORENSIK DETEKSI TRANSAKSI RUGI LAMA Anda
    # =========================================================================
    transaksi_boncos = df_sales[df_sales["Laba (Num)"] < 0] if not df_sales.empty else pd.DataFrame()
    jumlah_boncos = len(transaksi_boncos)
    total_kerugian = abs(transaksi_boncos["Laba (Num)"].sum()) if not transaksi_boncos.empty else 0.0

    top_admin = "N/A"
    if not df_sales.empty and "Admin" in df_sales.columns:
        mode_admin = df_sales["Admin"].dropna().mode()
        if not mode_admin.empty: top_admin = str(mode_admin[0])

    total_aset_lancar_toko = max(0.0, kas_riil_bisnis_toko) + total_piutang

    # =========================================================================
    # BLOK C: OPERASIONAL KARTU KREDIT (LANGKAH 1 - 3) - REVISI CUT-OFF TOTAL
    # =========================================================================
    outstanding_cc_total = 0.0
    
    # LANGKAH 1: Hitung total SEMUA transaksi tiket belanja modal yang digesek pakai CC (Mulai 1 Mei 2026)
    if not df_sales.empty and "Sumber Dana" in df_sales.columns:
        mask_sumber_cc = df_sales["Sumber Dana"].astype(str).str.lower().str.contains("credit|cc|kartu", na=False)
        df_cc_all = df_sales[mask_sumber_cc].copy()
        
        if not df_cc_all.empty:
            df_cc_all["Tgl_Parsed_CC"] = pd.to_datetime(df_cc_all["Tgl Pemesanan"], dayfirst=True, errors="coerce")
            df_cc_cutoff = df_cc_all[df_cc_all["Tgl_Parsed_CC"] >= pd.Timestamp("2026-05-01")]
            outstanding_cc_total = df_cc_cutoff["Harga Beli (Num)"].sum()

    # LANGKAH 2: Hitung total uang pembayaran tagihan CC di sheet Pribadi (Mulai 1 Mei 2026)
    total_bayar_tagihan_cc = 0.0
    if not df_pribadi.empty and "Keterangan" in df_pribadi.columns:
        # Buat kolom parsing tanggal mandiri untuk data pribadi
        df_pribadi["Tgl_Parsed_Pribadi"] = pd.to_datetime(df_pribadi["Tanggal"], errors="coerce")
        
        mask_bayar_cc = (
            df_pribadi["Keterangan"].astype(str).str.lower().str.contains("tagihan cc|pelunasan cc|bayar cc|tagihan kartu", na=False) &
            (df_pribadi["Kategori"].astype(str).str.strip().str.lower() == "pengeluaran") &
            (df_pribadi["Tgl_Parsed_Pribadi"] >= pd.Timestamp("2026-05-01")) # <── LOCK TIME CUT-OFF
        )
        total_bayar_tagihan_cc = df_pribadi[mask_bayar_cc]["Nominal (Num)"].sum()

    # LANGKAH 3: Sisa Beban Kartu Kredit Berjalan Masa Berjalan (100% Cocok & Adil)
    outstanding_cc_final = max(0.0, outstanding_cc_total - total_bayar_tagihan_cc)


    # =========================================================================
    # BLOK D: SENSOR DETEKSI OTOMATIS BIAYA OPS TOKO & INTEGRASI VARIABEL UTAMA
    # =========================================================================
    total_biaya_operasional_bisnis = 0.0 
    if not df_pribadi.empty and "Bank_Sumber" in df_pribadi.columns:
        for _, row in df_pribadi.iterrows():
            kat = str(row.get("Kategori", "")).strip().lower()
            pos_rek = str(row.get("No_Rekening_AI", "")).strip().lower()
            nominal = row["Nominal (Num)"]
            
            if kat == "pengeluaran":
                if "cadangan" in pos_rek or "aset kantor" in pos_rek:
                    total_biaya_operasional_bisnis += nominal

    beban_bagi_hasil_investor = max(0.0, kas_riil_bisnis_toko) * 0.075
    laba_bersih_riil_bisnis = laba_buku_total - total_biaya_operasional_bisnis - beban_bagi_hasil_investor
    daya_tahan_bulan = (kas_riil_bisnis_toko / GAJI_BASELINE_FLAT) if kas_riil_bisnis_toko > 0 else 0.0

    
        # === PASTIKAN VARIABEL DAYA_TAHAN_BULAN INI ADA DI DALAM RETURN FILE HYBRID_FINANCE_ENGINE.PY ===
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
        
        "daya_tahan_bulan": daya_tahan_bulan, # <── SUNTIKKAN INI YANG HILANG (Penyembuh Eror)
        "wajib_setor_investor": beban_bagi_hasil_investor,
        "laba_bersih_riil_bisnis": laba_bersih_riil_bisnis, # <── Pengganti top_admin di level data
        "total_biaya_operasional_bisnis": total_biaya_operasional_bisnis,
        "total_aset_lancar_toko": total_aset_lancar_toko,
        "laba_buku_total": laba_buku_total, 
        "jumlah_boncos": jumlah_boncos, 
        "total_kerugian": total_kerugian, 
        "top_admin": top_admin,
        "wajib_setor_investor": wajib_setor_investor, 
        "gaji_owner_dialokasikan": gaji_owner_dialokasikan, 
        "cadangan_bisnis_kertas": cadangan_bisnis_40_kertas,
        "status_darurat_aktif": status_darurat_aktif, 
        "nilai_defisit_gaji": nilai_defisit_gaji,
        "log_bank_pribadi": log_bank, 
        "mutasi_pos_digital": mutasi_pos_digital,
        "target_kertas_domestik": {
            "1. Tempat Tinggal & Kendaraan (40.9%)": 10728067.0, 
            "2. Rumah Tangga & Keluarga (25.8%)": 6768500.0, 
            "3. Kebutuhan Pokok Hidup (19.0%)": 5000000.0, 
            "4. Tagihan Bulanan & Ops (9.2%)": 2405000.0, 
            "5. Edukasi, Anak & Sosial (5.1%)": 1358000.0
        },
        "total_omzet_buku": total_omzet_buku, 
        "total_hpp_buku": total_hpp_buku,
        "debug_raw_sales_count": debug_raw_sales_count, 
        "debug_raw_pribadi_count": debug_raw_pribadi_count
    }

