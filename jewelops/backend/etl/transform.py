from django.conf import settings
from typing import Dict, List, Sequence, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # jewelops/
ETL_OUTPUT_DIR = PROJECT_ROOT / "ETL_outputs"
ETL_OUTPUT_DIR.mkdir(exist_ok=True)

class SplitSalesAndExpenses:
    SECTION_WIDTHS = {
        "DATE": 1,
        "EXPENSES": 4,
        "SALES": 15,
        "ORDERS": 11,
    }

    EXPENSES_COLUMN_DATE_CUTOFF_INDEX = 2
    SALES_COLUMN_DATE_CUTOFF_INDEX = 16

    @classmethod
    def build_section_slices(cls, header: Sequence[str]) -> Dict[str, slice]:
        """
        Find the starting column index for each logical section based on the header row
        and SECTION_WIDTHS, and return a dict of slices for each section.

        Handles headers like 'DATE:' / 'EXPENSES:' / 'SALES:' by stripping colon + spaces.
        """
        indices: Dict[str, int] = {}

        for label in cls.SECTION_WIDTHS.keys():
            target = label.upper()
            found_idx = None

            for i, col in enumerate(header):
                # Normalize e.g. 'DATE:' -> 'DATE'
                norm = (col or "").strip().rstrip(":").upper()
                if norm == target:
                    found_idx = i
                    break

            if found_idx is None:
                raise ValueError(
                    f"Could not find section header '{label}' in header row: {header}"
                )

            indices[label] = found_idx

        slices: Dict[str, slice] = {}
        for label, start_idx in indices.items():
            width = cls.SECTION_WIDTHS[label]
            slices[label] = slice(start_idx, start_idx + width)

        return slices

    @staticmethod
    def pad_rows_to_width(rows: List[List[str]], width: int) -> List[List[str]]:
        """
        Ensure all rows have the same number of columns by right-padding with empty strings.
        """
        padded = []
        for row in rows:
            if len(row) < width:
                row = row + [""] * (width - len(row))
            else:
                row = row[:width]
            padded.append(row)
        return padded

    @staticmethod
    def compute_filled_dates(
        arr: np.ndarray,
        date_col_idx: int,
        cutoff_idx: int,
    ) -> np.ndarray:
        """
        Walk the 2D array row-wise and:
        - when a non-empty date appears in `date_col_idx`, set current_date
        - keep using that date for subsequent rows
        - BUT when `cutoff_idx` has 'total' (case-insensitive), do NOT assign
          a date on that row and reset current_date.

        Returns a 1D array of strings (shape (n_rows,)).
        """
        n_rows = arr.shape[0]
        out = np.full(n_rows, "", dtype=object)
        current_date = ""

        for i in range(n_rows):
            cutoff_val = str(arr[i, cutoff_idx] or "").strip().lower()
            # TOTAL row → break date block, no date for this row
            if cutoff_val.startswith("total"):
                current_date = ""
                continue

            # Update current_date if there's a date in this row
            date_cell = str(arr[i, date_col_idx] or "").strip()
            if date_cell:
                current_date = date_cell

            # Assign date if we have one
            if current_date:
                out[i] = current_date

        return out

    @classmethod
    def split_expenses_and_sales(
        cls,
        raw_rows: List[List[str]],
    ) -> Tuple[List[List[str]], List[List[str]]]:
        """
        Return:
          - expenses_rows: [filled_date_for_expenses | EXPENSES columns]
          - sales_rows:    [filled_date_for_sales    | SALES columns | ORDERS columns]
        """
        if not raw_rows:
            return [], []

        header = raw_rows[0]
        body = raw_rows[1:]

        width = len(header)
        body = cls.pad_rows_to_width(body, width)

        section_slices = cls.build_section_slices(header)

        date_slice = section_slices["DATE"]
        expenses_slice = section_slices["EXPENSES"]
        sales_slice = section_slices["SALES"]
        orders_slice = section_slices["ORDERS"]

        date_col_idx = date_slice.start  # single DATE column

        arr = np.array(body, dtype=object)

        # Compute date columns separately
        expenses_dates = cls.compute_filled_dates(
            arr,
            date_col_idx=date_col_idx,
            cutoff_idx=cls.EXPENSES_COLUMN_DATE_CUTOFF_INDEX,
        )
        sales_dates = cls.compute_filled_dates(
            arr,
            date_col_idx=date_col_idx,
            cutoff_idx=cls.SALES_COLUMN_DATE_CUTOFF_INDEX,
        )

        # Make them 2D for hstack
        expenses_date_col = expenses_dates.reshape(-1, 1)
        sales_date_col = sales_dates.reshape(-1, 1)

        # Expenses: DATE + EXPENSES
        expenses_arr = np.hstack([expenses_date_col, arr[:, expenses_slice]])

        # Sales: DATE + SALES + ORDERS
        sales_arr = np.hstack([sales_date_col, arr[:, sales_slice], arr[:, orders_slice]])

        # If you want to drop rows with no filled date, uncomment:
        idx = np.arange(expenses_arr.shape[0])
        exp_mask = ((expenses_dates != "") | (idx == 0))
        sales_mask = ((sales_dates != "") | (idx == 0))
        expenses_arr = expenses_arr[exp_mask]
        sales_arr = sales_arr[sales_mask]

        expenses_rows = expenses_arr.tolist()
        sales_rows = sales_arr.tolist()

        # print(sales_rows[:20])
        return expenses_rows, sales_rows





# ------------------------------ MAIN SCRIPT ------------------------------

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
    # output_dir = settings.BASE_DIR / "ETL_outputs"
    # output_dir.mkdir(exist_ok=True)

    # csv_path = output_dir / f"{filename}-May.csv"
    # df.to_csv(csv_path, index=False)

    # print(f"Saved CSV → {csv_path}")
    csv_path = ETL_OUTPUT_DIR / f"{filename}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved {filename} → {csv_path}")

def clean_dataframes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    # Treat "" as NaN
    df = df.replace("", np.nan)
    # Drop rows where *all* columns are NaN/empty
    df = df.dropna(how="all")

    # convert date column to datetime
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), dayfirst=True, format="%d/%m/%Y", errors="coerce")
    return df

def process_dataframes():
    raw_rows = fetch_rows_from_sheet(interactive=True)

    expenses_rows, sales_rows = SplitSalesAndExpenses.split_expenses_and_sales(raw_rows)

    # for debugging / DataFrames
    header = raw_rows[0]
    section_slices = SplitSalesAndExpenses.build_section_slices(header)

    date_slice = section_slices["DATE"]
    expenses_slice = section_slices["EXPENSES"]

    expenses_columns = list(header[date_slice]) + list(header[expenses_slice])
    sales_columns = ["DATE"] \
        + list(header[section_slices["SALES"]]) \
        + list(header[section_slices["ORDERS"]])

    print("Expenses rows after split:", len(expenses_rows), "x", len(expenses_rows[0]) if expenses_rows else 0)
    print("Sales rows after split:", len(sales_rows), "x", len(sales_rows[0]) if sales_rows else 0)
    print("len(expenses_columns) =", len(expenses_columns))
    print("len(sales_columns)    =", len(sales_columns))

    expenses_df = pd.DataFrame(expenses_rows[1:], columns=expenses_rows[0])
    sales_df = pd.DataFrame(sales_rows[1:], columns=sales_rows[0])

    expenses_df = clean_dataframes(expenses_df)
    sales_df = clean_dataframes(sales_df)

    #save to local csv files
    # save_df_to_csv(expenses_df, "expenses")
    save_df_to_csv(sales_df, "sales")

    # print("=== EXPENSES HEAD ===")
    # print(expenses_df.head(30))
    # print("=== SALES+ORDERS HEAD ===")
    # print(sales_df.head(30))
    # sales_df


    # make sure index is 0,1,2,... so previous row = idx-1


def main():
    process_dataframes()

if __name__ == "__main__":
    main()
