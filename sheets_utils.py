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

def append_dataframe_to_sheet(df: pd.DataFrame, worksheet):
    rows = df.fillna("").astype(str).values.tolist()
    # jika sheet masih kosong, tulis header dulu
    if not worksheet.get_all_values():
        worksheet.insert_row(df.columns.tolist(), index=1)
    worksheet.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")
