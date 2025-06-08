import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st

def connect_to_gsheet(SHEET_ID, worksheet_name="Data"):
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

def append_dataframe_to_sheet(df, worksheet):
    existing = worksheet.get_all_values()
    if not existing:
        worksheet.insert_rows([df.columns.tolist()])
    worksheet.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")
