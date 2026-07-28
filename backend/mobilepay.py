from datetime import datetime
from hashlib import sha256
import io
import math
import re

import pandas as pd

from .serializers import decimal_to_cents


class MobilePayImportError(ValueError):
    """Raised when an XLSX export cannot be understood safely."""


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).strip().casefold()
    return re.sub(r"\s+", " ", text)


def normalize_identifier(value):
    """Normalize Excel numbers such as 4542443246.0 without changing text IDs."""
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def transaction_fingerprint(item):
    fingerprint_value = "|".join(
        [
            item["date"].isoformat(),
            normalize_text(item.get("name")),
            normalize_text(normalize_identifier(item.get("number"))),
            normalize_text(normalize_identifier(item.get("message"))),
            str(item["amount_cents"]),
            normalize_text(item.get("currency")),
            item["transaction_type"],
        ]
    )
    return sha256(fingerprint_value.encode("utf-8")).hexdigest()


def _is_empty(value):
    return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)


def _column_map(dataframe):
    aliases = {
        "date": {"date", "dato"},
        "name": {"name", "navn"},
        "type": {"type"},
        "number": {"number", "nummer"},
        "message": {"message", "besked"},
        "amount": {"amount", "beløb", "beloeb"},
        "currency": {"currency", "valuta"},
        "transaction_type": {"transaction type", "transaktionstype"},
    }
    columns = {normalize_text(column): column for column in dataframe.columns}
    result = {}
    for key, accepted in aliases.items():
        for candidate in accepted:
            if candidate in columns:
                result[key] = columns[candidate]
                break
    missing = {"date", "amount", "transaction_type"} - result.keys()
    if missing:
        raise MobilePayImportError(f"Missing MobilePay columns: {', '.join(sorted(missing))}")
    return result


def _value(row, columns, key, default=None):
    column = columns.get(key)
    if column is None:
        return default
    value = row.get(column)
    return default if _is_empty(value) else value


def parse_mobilepay_file(file_data):
    try:
        dataframe = pd.read_excel(io.BytesIO(file_data), engine="openpyxl")
    except Exception as error:
        raise MobilePayImportError(f"Could not read the XLSX file: {error}") from error

    columns = _column_map(dataframe)
    rows = []
    for index, row in dataframe.iterrows():
        raw_date = _value(row, columns, "date")
        parsed_date = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
        if pd.isna(parsed_date):
            raise MobilePayImportError(f"Invalid date on row {index + 2}")
        parsed_date = parsed_date.to_pydatetime().replace(tzinfo=None)

        raw_amount = _value(row, columns, "amount", 0)
        try:
            amount_cents = decimal_to_cents(raw_amount)
        except Exception as error:
            raise MobilePayImportError(f"Invalid amount on row {index + 2}") from error

        transaction_type_name = str(_value(row, columns, "transaction_type", "")).strip()
        transaction_type = normalize_text(transaction_type_name).replace(" ", "_")
        if transaction_type not in {"pay_in", "pay_out"}:
            transaction_type = "other"
        elif transaction_type == "pay_in":
            amount_cents = abs(amount_cents)
        else:
            amount_cents = -abs(amount_cents)

        item = {
            "row_number": index + 2,
            "date": parsed_date,
            "name": str(_value(row, columns, "name", "")).strip(),
            "type": str(_value(row, columns, "type", "")).strip(),
            "number": normalize_identifier(_value(row, columns, "number", "")),
            "message": normalize_identifier(_value(row, columns, "message", "")),
            "amount_cents": amount_cents,
            "currency": str(_value(row, columns, "currency", "")).strip(),
            "transaction_type_name": transaction_type_name,
            "transaction_type": transaction_type,
        }
        item["fingerprint"] = transaction_fingerprint(item)
        rows.append(item)
    return rows
