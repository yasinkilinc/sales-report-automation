import pandas as pd
import pytest

from salesreport.clean import clean, drop_duplicates, parse_number
from salesreport.load import Source

SOURCE = Source(
    name="Wholesale",
    pattern="*.csv",
    currency="USD",
    date_format="%d.%m.%Y",
    decimal=",",
    columns={},
)


def raw(*rows):
    columns = ["order_id", "date", "sku", "product", "quantity", "unit_price"]
    frame = pd.DataFrame(rows, columns=columns, dtype=object)
    frame["source_file"] = "f.csv"
    frame["source_row"] = range(2, len(rows) + 2)
    return frame


@pytest.mark.parametrize(
    "text, decimal, expected",
    [
        ("1.234,50", ",", 1234.5),
        ("12,7", ",", 12.7),
        ("1,234.50", ".", 1234.5),
        (" 19.90 ", ".", 19.9),
        ("£8.71", ".", 8.71),
        ("-1", ".", -1.0),
    ],
)
def test_parse_number_handles_regional_formats(text, decimal, expected):
    assert parse_number(pd.Series([text]), decimal)[0] == expected


def test_parse_number_returns_nan_for_text_and_empty():
    result = parse_number(pd.Series(["n/a", "", None], dtype=object), ".")
    assert result.isna().all()


def test_clean_normalises_sku_and_computes_amount():
    valid, issues = clean(raw(["INV-1", "02.07.2026", " mug - 350 ", "Mug", "3", "14,04"]), SOURCE)
    assert issues.empty
    line = valid.iloc[0]
    assert line["sku"] == "MUG-350"
    assert line["date"] == pd.Timestamp(2026, 7, 2)
    assert (line["quantity"], line["amount"]) == (3, 42.12)
    assert (line["channel"], line["currency"]) == ("Wholesale", "USD")


def test_clean_rejects_bad_rows_with_every_reason():
    valid, issues = clean(
        raw(
            ["INV-1", "31.09.2026", "MUG-350", "Mug", "0", "1,00"],
            ["", "02.07.2026", "MUG-350", "Mug", "1", ""],
            ["INV-3", "02.07.2026", "MUG-350", "Mug", "1,5", "1,00"],
        ),
        SOURCE,
    )
    assert valid.empty
    assert list(issues["problem"]) == [
        "invalid date '31.09.2026'; quantity is 0",
        "missing order id; missing or unreadable price",
        "quantity is not a whole number",
    ]
    assert list(issues["source_row"]) == [2, 3, 4]


def test_negative_quantity_is_a_valid_refund():
    valid, issues = clean(raw(["INV-1-R", "02.07.2026", "MUG-350", "Mug", "-1", "14,90"]), SOURCE)
    assert issues.empty
    assert valid.iloc[0]["amount"] == -14.9


def test_drop_duplicates_keeps_first_and_points_to_it():
    rows = raw(
        ["A", "01.08.2026", "MUG-350", "Mug", "1", "5,00"],
        ["B", "01.08.2026", "MUG-350", "Mug", "1", "5,00"],
        ["A", "01.08.2026", "MUG-350", "Mug", "1", "5,00"],
    )
    valid, _ = clean(rows, SOURCE)
    unique, duplicates = drop_duplicates(valid)
    assert list(unique["order_id"]) == ["A", "B"]
    assert list(duplicates["problem"]) == ["duplicate of f.csv row 2"]
    assert list(duplicates["source_row"]) == [4]
