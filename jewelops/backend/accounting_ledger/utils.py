import re
from typing import List, Tuple, Optional, Union

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
