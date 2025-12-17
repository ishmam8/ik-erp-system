import re
import math
from datetime import datetime
from typing import List, Tuple, Optional, Union
from decimal import Decimal, InvalidOperation

_num_re = re.compile(r"-?\d+(?:\.\d+)?")

def to_decimal(v, default="0"):
    if v is None:
        return Decimal(default)

    # Already numeric
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        # avoid float artifacts as much as possible
        return Decimal(str(v))

    s = str(v).strip().replace(",", "")
    m = _num_re.search(s)
    if not m:
        return Decimal(default)

    try:
        return Decimal(m.group(0))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def parse_item_codes(code_value: Optional[Union[str, int, list, tuple]],
                     name_value: Optional[Union[str, list, tuple]] = None
                    ) -> Tuple[List[int], List[str]]:
    """
    Parse item codes and optional item names from various frontend formats.

    Returns (codes_list, names_list).

    Examples accepted:
      - code_value: "(2450)(794)(346)"  -> [2450, 794, 346]
      - code_value: "2450,794,346"      -> [2450, 794, 346]
      - code_value: [2450, "794", "(346)"] -> [2450, 794, 346]
      - name_value: "Earring,Wristlet,D.nosepin" -> ["Earring","Wristlet","D.nosepin"]
      - name_value may be a list already.
    """
    codes: List[int] = []
    names: List[str] = []

    # Parse codes
    if code_value is None:
        codes = []
    elif isinstance(code_value, (list, tuple)):
        for v in code_value:
            s = str(v).strip()
            m = re.search(r'(\d+)', s)
            if m:
                codes.append(int(m.group(1)))
    elif isinstance(code_value, int):
        codes = [code_value]
    else:
        s = str(code_value).strip()
        found = re.findall(r'\d+', s)
        codes = [int(x) for x in found]

    # Parse names
    if name_value is None:
        names = []
    elif isinstance(name_value, (list, tuple)):
        names = [str(n).strip() for n in name_value if str(n).strip()]
    else:
        s = str(name_value).strip()
        # split on common separators (comma, semicolon, pipe)
        if re.search(r'[,\|;]', s):
            parts = re.split(r'[,\|;]+', s)
            names = [p.strip() for p in parts if p.strip()]
        else:
            # fallback: try to extract non-numeric tokens between or after parentheses
            # e.g. "(2450)Earring(794)Wristlet" -> ["Earring","Wristlet"]
            tokens = re.findall(r'\)\s*([^\(\)\d,;|]+)', s)
            if tokens:
                names = [t.strip() for t in tokens if t.strip()]
            else:
                # last resort: whole string as single name
                if s:
                    names = [s]

    # Normalize lengths: if only codes present, produce empty name placeholders
    if codes and not names:
        names = [''] * len(codes)

    return codes, names


def parse_payment_methods(value: Optional[Union[str, List[str]]]) -> List[str]:
    """
    Parse payment methods from input like "Card,Cash" or a list and return
    a list of trimmed method strings. Returns [] for empty/None input.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        return []
    # split on comma, semicolon or pipe and trim whitespace
    return [part.strip() for part in re.split(r'[,\|;]+', s) if part.strip()]


def safe_int(value):
    """
    Placeholder: safely parse invoice_number (may be '', None, 'Order', etc.).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or not s.isdigit():
        return None
    return int(s)

def parse_order_date(value):
    """
    Placeholder: parse 'Date to Deliver' / 'Ready for Handover'.
    Your CSV seems to use DD/MM/YYYY, e.g. '03/06/2025'.
    Adjust this if format differs or allow empty.
    """
    if not value or isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    # tweak format to your actual sheet
    return datetime.strptime(s, "%d/%m/%Y").date()