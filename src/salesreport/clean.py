"""Turn raw text rows into typed, validated order lines. Bad rows are kept aside with a reason."""

import pandas as pd

from salesreport.load import Source

DUPLICATE_KEY = ["channel", "order_id", "sku", "date", "quantity", "unit_price"]
ISSUE_COLUMNS = ["channel", "source_file", "source_row", "problem", "order_id", "sku"]


def clean(raw: pd.DataFrame, source: Source) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse one source's rows. Returns (valid lines, issues)."""
    df = raw.copy()
    for col in ("order_id", "sku", "product"):
        df[col] = df[col].str.strip()
    df["sku"] = df["sku"].str.upper().str.replace(r"\s+", "", regex=True)
    df["date"] = pd.to_datetime(df["date"].str.strip(), format=source.date_format, errors="coerce")
    df["quantity"] = parse_number(df["quantity"], source.decimal)
    df["unit_price"] = parse_number(df["unit_price"], source.decimal)
    df["channel"] = source.name
    df["currency"] = source.currency

    problems = find_problems(df, raw)
    bad = problems != ""
    issues = df[bad].assign(problem=problems[bad])[ISSUE_COLUMNS]
    valid = df[~bad].copy()
    valid["quantity"] = valid["quantity"].astype(int)
    valid["amount"] = (valid["quantity"] * valid["unit_price"]).round(2)
    return valid, issues


def parse_number(values: pd.Series, decimal: str) -> pd.Series:
    """'1.234,50' with decimal=',' or '1,234.50' with decimal='.' -> 1234.5; anything else -> NaN."""
    text = values.str.strip().str.replace(r"[\s'£$€]", "", regex=True)
    thousands = "." if decimal == "," else ","
    text = text.str.replace(thousands, "", regex=False).str.replace(decimal, ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def find_problems(df: pd.DataFrame, raw: pd.DataFrame) -> pd.Series:
    """One readable reason per row ('' when the row is fine)."""
    if df.empty:
        return pd.Series("", index=df.index, dtype=object)
    checks = [
        (df["order_id"].isna() | (df["order_id"] == ""), "missing order id"),
        (df["sku"].isna() | (df["sku"] == ""), "missing SKU"),
        (df["date"].isna(), "invalid date '" + raw["date"].fillna("").astype(str) + "'"),
        (df["quantity"].isna(), "quantity is not a number"),
        (df["quantity"] == 0, "quantity is 0"),
        (df["quantity"].notna() & (df["quantity"] % 1 != 0), "quantity is not a whole number"),
        (df["unit_price"].isna(), "missing or unreadable price"),
        (df["unit_price"] < 0, "negative price"),
    ]
    columns = []
    for mask, reason in checks:
        hit = mask.fillna(False).astype(bool)
        columns.append(pd.Series(reason, index=df.index, dtype=object).where(hit, ""))
    found = pd.concat(columns, axis=1)
    return found.apply(lambda row: "; ".join(r for r in row if r), axis=1).astype(object)


def drop_duplicates(lines: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove lines that appear twice (e.g. overlapping exports). The first occurrence is kept."""
    dup = lines.duplicated(DUPLICATE_KEY, keep="first")
    first = lines.groupby(DUPLICATE_KEY, sort=False)[["source_file", "source_row"]].transform(
        "first"
    )
    reason = "duplicate of " + first["source_file"] + " row " + first["source_row"].astype(str)
    issues = lines[dup].assign(problem=reason[dup])[ISSUE_COLUMNS]
    return lines[~dup].reset_index(drop=True), issues
