# etl/extract.py
import os
import json
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ----- CONFIG -----
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env.local")

CLIENT_SECRET_PATH = BASE_DIR / os.getenv("ETL_CLIENT_SECRET_PATH")
TOKEN_PATH = BASE_DIR / os.getenv("ETL_TOKEN_PATH")
SPREADSHEET_ID = os.getenv("ETL_SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("ETL_WORKSHEET_NAME", "May")
SCOPES = json.loads(os.getenv(
    "ETL_SCOPES",
    '["https://www.googleapis.com/auth/spreadsheets.readonly"]'
))  


# ----- AUTH -----

def get_gspread_client(interactive: bool = True):
    """
    interactive=True (first run): opens browser for OAuth login.
    interactive=False: uses saved token; no browser (good for prod).
    """
    creds = None

    # 1) Try to load existing token
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "r") as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)

    # 2) If no token and interactive: do OAuth browser flow
    if not creds and interactive:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_PATH),
            SCOPES,
        )
        creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    if not creds:
        raise RuntimeError(
            "No credentials found and interactive=False. "
            "Run once with interactive=True to generate token."
        )

    return gspread.authorize(creds)


# ----- EXTRACT -----

def fetch_sheet_rows(
    client,
    spreadsheet_id: str,
    worksheet_name: str,
) -> List[Dict[str, str]]:
    """
    Returns list of dict rows, keyed by header row.
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    return ws.get_all_values()

