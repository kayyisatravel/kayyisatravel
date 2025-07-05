import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st

def connect_to_gsheet(SHEET_ID:str, worksheet_name: str = "Data"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = st.secrets["gcp_service_account"]  # Ambil dari secrets.toml
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(worksheet_name)  # <- Perbaikan di sini
    return worksheet

def _safe_to_str(val):
    """
    Konversi nilai ke string dengan aman untuk dikirim ke Google Sheets.
    """
    import datetime

    if pd.isna(val):
        return ""
    if isinstance(val, (datetime.datetime, datetime.date, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")  # atau format lain sesuai kebutuhan
    return str(val)


def append_dataframe_to_sheet(df: pd.DataFrame, worksheet):
    """
    Menambahkan data dari DataFrame ke Google Sheet dengan aman.
    Semua nilai dikonversi ke string agar kompatibel dengan Google Sheets API.
    """
    if df.empty:
        print("❌ DataFrame kosong, tidak ada data untuk dikirim.")
        return

    # Bersihkan & konversi semua nilai agar bisa dikirim ke Google Sheets
    cleaned_df = (
        df.fillna("")                 # Hilangkan NaN/None
          .applymap(_safe_to_str)     # Konversi semua nilai ke string aman
    )
    print("Jumlah kolom yang terbaca:", len(worksheet.row_values(1)))
    print("Kolom header:", worksheet.row_values(1))

    # Konversi ke list of lists (rows)
    rows = cleaned_df.values.tolist()

    # Kirim ke Google Sheets
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
