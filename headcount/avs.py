"""Swiss social security number (AVS / AHV, format 756.XXXX.XXXX.XX).

The last digit is an EAN-13 check digit computed over the first twelve.
"""

import re

_SEPARATORS = re.compile(r"[.\s]")


def check_digit(first_twelve: str) -> int:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first_twelve))
    return (10 - total % 10) % 10


def normalize(value: object) -> str | None:
    """Return the number in the official dotted format, or None if it has the wrong shape."""
    digits = _SEPARATORS.sub("", str(value))
    if len(digits) != 13 or not digits.isdigit():
        return None
    return f"{digits[:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:]}"


def is_valid(value: object) -> bool:
    formatted = normalize(value)
    if formatted is None:
        return False
    digits = formatted.replace(".", "")
    return digits.startswith("756") and int(digits[-1]) == check_digit(digits[:12])


def build(nine_digits: str) -> str:
    """Build a valid number from the nine digits that follow the 756 prefix."""
    body = "756" + nine_digits
    return normalize(body + str(check_digit(body)))
