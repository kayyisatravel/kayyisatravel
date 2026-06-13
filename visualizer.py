# visualizer.py
import streamlit as st
import plotly.express as px
import pandas as pd

def render_grafik_tren_harian(df_daily):
    """Merender grafik garis interaktif tren omzet harian."""
    if df_daily.empty:
        st.info("Tidak ada data harian untuk ditampilkan.")
        return

    fig = px.line(
        df_daily, 
        x="Tgl Pemesanan_Parsed", 
        y="Harga Jual (Num)",
        title="📈 Tren Pergerakan Omzet Harian (Interaktif)",
        labels={"Tgl Pemesanan_Parsed": "Tanggal", "Harga Jual (Num)": "Total Omzet (Rp)"},
        markers=True
    )
    
    fig.update_traces(line_color='#1f77b4', line_width=2, marker=dict(size=6))
    fig.update_layout(
        hovermode="x unified",
        xaxis_gridcolor='rgba(230,230,230,0.5)',
        yaxis_gridcolor='rgba(230,230,230,0.5)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True)


def render_grafik_margin_aman(df_raw_input):
    """
    Fungsi grafik batang baru dengan proteksi super ketat.
    Membuat data agregat secara independen tanpa bergantung pada finance_engine.
    """
    if df_raw_input.empty:
        st.info("Data kosong, tidak bisa membuat grafik segmentasi.")
        return
        
    # Salin data agar tidak merusak dataframe asli aplikasi
    df_local = df_raw_input.copy()
    
    # Fungsi pembersih angka internal yang sangat aman
    def _bersihkan_ke_float(val):
        if pd.isna(val): return 0.0
        s = str(val).replace("Rp", "").replace(".", "").replace(" ", "").strip().replace(",", "")
        try: return float(s)
        except: return 0.0

    # Pastikan kolom-kolom matematika ini terbuat dengan aman
    df_local["Harga Jual (Num)"] = df_local["Harga Jual"].apply(_bersihkan_ke_float)
    df_local["Harga Beli (Num)"] = df_local["Harga Beli"].apply(_bersihkan_ke_float)
    df_local["Laba (Num)"] = df_local["Harga Jual (Num)"] - df_local["Harga Beli (Num)"]
    
    # Deteksi otomatis kolom kategori tipe produk travel
    kolom_tipe = "Tipe" if "Tipe" in df_local.columns else None
    if not kolom_tipe:
        st.warning("⚠️ Kolom 'Tipe' tidak ditemukan pada database GSheets Anda.")
        return

    # Hitung data agregat untuk grafik batang
    df_grouped = df_local.groupby(kolom_tipe).agg(
        Total_Omzet=("Harga Jual (Num)", "sum"),
        Total_Laba=("Laba (Num)", "sum")
    ).reset_index()
    
    # Hitung persentase profit margin
    df_grouped["Margin (%)"] = (df_grouped["Total_Laba"] / df_grouped["Total_Omzet"] * 100).fillna(0).round(2)
    
    # Render grafik batang interaktif Plotly
    fig = px.bar(
        df_grouped,
        x=kolom_tipe,
        y="Margin (%)",
        text="Margin (%)",
        title="💼 Segmentasi Kekuatan Profit Margin per Kategori Produk",
        labels={kolom_tipe: "Kategori Produk", "Margin (%)": "Persentase Margin Keuntungan"},
        color=kolom_tipe,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig.update_layout(
        yaxis_suffix="%", 
        plot_bgcolor='rgba(0,0,0,0)', 
        showlegend=False,
        margin=dict(t=50, b=20, l=20, r=20)
    )
    st.plotly_chart(fig, use_container_width=True)
