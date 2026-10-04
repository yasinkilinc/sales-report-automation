import pytest

from salesreport.load import load_config, read_source


def test_config_lists_all_sources(config_path):
    config = load_config(config_path)
    assert config.currency == "EUR"
    assert [s.name for s in config.sources] == ["Webshop", "Marketplace", "Wholesale"]


def test_config_without_a_column_mapping_is_rejected(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text(
        '[report]\ncurrency = "EUR"\n[[source]]\nname = "X"\npattern = "*.csv"\n'
        'currency = "EUR"\ndate_format = "%Y"\ncolumns = { order_id = "id" }\n'
    )
    with pytest.raises(ValueError, match="no column mapping"):
        load_config(path)


def test_source_rows_match_what_the_user_sees(config_path, sample_dir):
    """Row numbers in the Issues sheet must point at the right line, even with title rows and blank lines."""
    sources = {s.name: s for s in load_config(config_path).sources}

    market = read_source(sources["Marketplace"], sample_dir)
    first = market[market["source_file"] == "marketplace_orders_2026-07.xlsx"].iloc[0]
    assert first["source_row"] == 4  # two title rows + header

    wholesale = read_source(sources["Wholesale"], sample_dir)
    lines = (sample_dir / "wholesale_invoices_2026-Q3.csv").read_text().splitlines()
    for _, row in wholesale.iterrows():
        assert lines[row["source_row"] - 1].startswith(row["order_id"] + ";")


def test_missing_column_names_the_file(tmp_path, config_path):
    source = load_config(config_path).sources[0]
    (tmp_path / "webshop_orders_x.csv").write_text("Order ID,Created at\n1,2026-07-01 10:00\n")
    with pytest.raises(ValueError, match="webshop_orders_x.csv: expected columns"):
        read_source(source, tmp_path)
