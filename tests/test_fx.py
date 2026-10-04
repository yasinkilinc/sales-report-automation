from datetime import date

import pandas as pd
import pytest

from salesreport.fx import RateTable, convert, load_rates


def test_weekend_uses_last_published_rate(weekend):
    table = RateTable("EUR", {"2026-08-07": {"USD": 1.15}})  # Friday
    assert table.rate("USD", weekend) == 1.15


def test_base_currency_rate_is_one(weekend):
    assert RateTable("EUR", {}).rate("EUR", weekend) == 1.0


def test_missing_rate_is_an_error_not_a_guess(weekend):
    with pytest.raises(LookupError, match="no EUR/USD rate"):
        RateTable("EUR", {"2026-07-01": {"USD": 1.15}}).rate("USD", weekend)


def test_convert_divides_by_the_rate():
    lines = pd.DataFrame(
        {"currency": ["USD", "EUR"], "date": pd.to_datetime(["2026-08-07", "2026-08-07"])}
    )
    lines["amount"] = [125.0, 10.0]
    out = convert(lines, RateTable("EUR", {"2026-08-07": {"USD": 1.25}}))
    assert list(out["amount_eur"]) == [100.0, 10.0]


def test_rates_are_cached_and_reused(tmp_path, fetch):
    cache = tmp_path / "rates.json"
    args = ("EUR", {"EUR", "USD", "GBP"}, date(2026, 7, 1), date(2026, 9, 30))
    first = load_rates(*args, cache=cache, fetch=fetch)
    second = load_rates(*args, cache=cache, fetch=fetch)
    assert fetch.calls == 1
    assert first.rate("GBP", date(2026, 8, 9)) == second.rate("GBP", date(2026, 8, 9)) == 0.85


def test_cache_for_a_shorter_period_is_refreshed(tmp_path, fetch):
    cache = tmp_path / "rates.json"
    load_rates("EUR", {"USD"}, date(2026, 7, 1), date(2026, 7, 31), cache=cache, fetch=fetch)
    load_rates("EUR", {"USD"}, date(2026, 7, 1), date(2026, 8, 31), cache=cache, fetch=fetch)
    assert fetch.calls == 2


def test_offline_without_cache_fails_clearly(tmp_path, fetch):
    with pytest.raises(LookupError, match="offline mode"):
        load_rates(
            "EUR", {"USD"}, date(2026, 7, 1), date(2026, 7, 2),
            cache=tmp_path / "none.json", offline=True, fetch=fetch,
        )  # fmt: skip
    assert fetch.calls == 0
