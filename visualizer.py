# visualizer.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def render_grafik_tren_harian(df_daily):
    """Merender grafik garis interaktif tren omzet harian dengan penanda anomali."""
    if df_daily.empty:
        st.info("Tidak ada data harian untuk ditampilkan.")
        return

    # Buat grafik garis utama
    fig = px.line(
        df_daily, 
        x="Tgl Pemesanan_Parsed", 
        y="Harga Jual (Num)",
        title="📈 Tren Pergerakan Omzet Harian (Interaktif)",
        labels={"Tgl Pemesanan_Parsed": "Tanggal", "Harga Jual (Num)": "Total Omzet (Rp)"},
        markers=True
    )
    
    # Kustomisasi estetika grafik
    fig.update_traces(line_color='#1f77b4', line_width=2, marker=dict(size=6))
    fig.update_layout(
        hovermode="x unified",
        xaxis_gridcolor='rgba(230,230,230,0.5)',
        yaxis_gridcolor='rgba(230,230,230,0.5)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True)

def render_segmentasi_profit_margin(df):
    """Merender grafik batang komparasi profit margin antar jenis produk travel."""
    # Kelompokkan data untuk grafik
    df_segment = df.groupby("Tipe").agg(
        Omzet=("Harga Jual (Num)", "sum"),
        Laba=("Laba (Num)", "sum")
    ).reset_index()
    
    df_segment["Margin (%)"] = (df_segment["Laba"] / df_segment["Omzet"] * 100).round(2)
    
    # Grafik batang margin persentase
    fig = px.bar(
        df_segment,
        x="Tipe",
        y="Margin (%)",
        text="Margin (%)",
        title="💼 Segmentasi Kekuatan Profit Margin per Kategori Produk",
        labels={"Tipe": "Kategori Produk", "Margin (%)": "Persentase Margin Keuntungan"},
        color="Tipe",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig.update_layout(yaxis_suffix="%", plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
