import os
from django.conf import settings
from typing import Dict, List, Sequence, Tuple
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env.local")

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # jewelops/
ETL_OUTPUT_DIR = PROJECT_ROOT / "ETL_outputs/artisans"
ETL_OUTPUT_DIR.mkdir(exist_ok=True)

def fetch_rows_from_sheet(interactive: bool = True) -> List[List[str]]:
    try:
        from etl import extract as extract_mod
    except ModuleNotFoundError:
        import extract as extract_mod  # type: ignore

    client = extract_mod.get_gspread_client(interactive=interactive)
    return extract_mod.fetch_sheet_rows(
        client,
        extract_mod.SPREADSHEET_ID,
        extract_mod.WORKSHEET_NAME,
    )

def save_df_to_csv(df: pd.DataFrame, filename: str) -> None:
    csv_path = ETL_OUTPUT_DIR / f"uncleaned/{filename}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved {filename} → {csv_path}")


def split_karigar_blocks(raw_rows: list[list[str]]) -> List[pd.DataFrame]:
    """
    raw_rows: list-of-lists from Google Sheets (e.g. sheet.get_all_values()).
              Assumes:
                - raw_rows[0] is the single big header row.
                - Subsequent rows are data.
              Pattern: repeated blocks from 'Karigar' ... 'Balance'.
    Returns: list of DataFrames, one per [Karigar ... Balance] block.
    """

    if not raw_rows:
        return []

    header = raw_rows[0]
    data_rows = raw_rows[1:]

    # 1) Find all starting indices of blocks (where header == 'Karigar')
    start_idxs = [i for i, v in enumerate(header) if v == "Karigar"]

    # 2) For each start, find the first 'Balance' after it → end of that block
    blocks: list[tuple[int, int]] = []
    for s in start_idxs:
        e = None
        for j in range(s, len(header)):
            if header[j] == "Balance":
                e = j
                break
        if e is not None:
            blocks.append((s, e))

    dfs: List[pd.DataFrame] = []

    # 3) Slice each block into its own DataFrame
    for s, e in blocks:
        cols = header[s : e + 1]
        block_rows = [row[s : e + 1] for row in data_rows]

        df = pd.DataFrame(block_rows, columns=cols)

        # Normalize empty cells → NaN, then drop fully-empty rows
        df = df.replace("", pd.NA)
        df = df.dropna(how="all")

        if not df.empty:
            dfs.append(df)

    return dfs


def split_karigar_gold_and_payments(csv_file: Path):
    df = pd.read_csv(csv_file)
    gold_history_dir = ETL_OUTPUT_DIR / "gold_history"
    transactions_dir = ETL_OUTPUT_DIR / "transactions"

    # (Optional but safer) validate structure
    if df.shape[1] != 11:
        raise ValueError(f"{csv_file} expected 12 columns, found {df.shape[1]}")

    # 1️⃣ First CSV → first 7 columns as-is
    df_first = df.iloc[:, :6]
    first_out = gold_history_dir / (csv_file.stem + "_gold_history.csv")
    df_first.to_csv(first_out, index=False)

    # 2️⃣ Second CSV:
    # columns by position:
    # 0: Karigar
    # 7: 2nd Date
    # 8: Gold History
    # 9: Bought Gold
    # 10: Payment
    # 11: Balance
    df_second = df.iloc[:, [0, 6, 7, 8, 9, 10]].copy()
    df_second.columns = [
        "Karigar",
        "Date",
        "Gold History",
        "Bought Gold",
        "Payment",
        "Balance",
    ]
    second_out = transactions_dir / (csv_file.stem + "_payments.csv")
    df_second.to_csv(second_out, index=False)

    return first_out, second_out

def process_local_csv_files():

    csv_files = list(ETL_OUTPUT_DIR.glob("uncleaned/artisan_table_*.csv"))
    for csv_file in csv_files:
        split_karigar_gold_and_payments(csv_file)


def fix_gold_history_rows_format():
    csv_files = list(
        ETL_OUTPUT_DIR.glob("gold_history/artisan_table_*.csv")
    )
    if not csv_files:
        print("No artisan gold history CSVs found to fix.")
        return

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        norm = (
        df.astype(str)
          .apply(lambda col: (
              col.str.lower()
                 .str.replace(r"\s+", " ", regex=True)  # collapse all whitespace to single space
                 .str.strip()
          ))
        )

        mask_cell = df.astype(str).applymap(
        lambda v: "new balance" in v.strip().lower()
    )
        rows_before = len(df)
        df = df[~mask_cell.any(axis=1)].copy()
        rows_after = len(df)
        print(f"{csv_file}: removed {rows_before - rows_after} rows containing 'new balance'")

        # 1) If any cell in the second column contains "Closing",
        #    clear just that cell (keep other rows/values intact).
        if len(df.columns) >= 2:
            second_col = df.columns[1]
            mask = df[second_col].astype(str).str.contains("Closing", case=False, na=False)
            df.loc[mask, second_col] = ""  # or pd.NA if you prefer nulls

        # 2) If there is a 'Date' column:
        #    - parse values to datetime (invalid -> NaT)
        #    - forward-fill missing dates from the previous row
        #    - format as 'YYYY-MM-DD'
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df["Date"] = df["Date"].ffill()
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        
        if "Transaction Type" in df.columns:
            # Treat empty strings as missing
            df["Transaction Type"] = df["Transaction Type"].replace("", pd.NA)
            # Forward-fill from previous row
            df["Transaction Type"] = df["Transaction Type"].ffill()


        df.to_csv(csv_file, index=False)
        print(f"Fixed date format and cleaned 'Closing' cells in {csv_file}")


def fix_payments_rows_format():
    csv_files = list(
        ETL_OUTPUT_DIR.glob("transactions/artisan_table_*.csv")
    )
    if not csv_files:
        print("No artisan payments CSVs found to fix.")
        return

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        # 1) If there is a 'Date' column:
        #    - parse values to datetime (invalid -> NaT)
        #    - forward-fill missing dates from the previous row
        #    - format as 'YYYY-MM-DD'
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df["Date"] = df["Date"].ffill()
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        
        df = df.replace("", pd.NA)

        df.to_csv(csv_file, index=False)
        print(f"Fixed date format in {csv_file}")



def process_dataframes():
    raw_rows = fetch_rows_from_sheet(interactive=True)

    cleaned_table_asrtisans = split_karigar_blocks(raw_rows[1:])
    print(f"Found {len(cleaned_table_asrtisans)} artisan tables.")
    print(cleaned_table_asrtisans[0].head())
    print(cleaned_table_asrtisans[0].iloc[0,0])

    for idx, df in enumerate(cleaned_table_asrtisans):
        artisan_name = cleaned_table_asrtisans[idx].iloc[0,0].split()[0]
        save_df_to_csv(df, f"artisan_table_{artisan_name}")
    
    process_local_csv_files()
    fix_gold_history_rows_format()
    fix_payments_rows_format()



# ---- main entry point ----
def main():
    process_dataframes()

if __name__ == "__main__":
    main()
