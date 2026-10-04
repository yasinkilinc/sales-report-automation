"""European Central Bank reference rates (via the free Frankfurter API), cached on disk."""

import json
import logging
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

API = "https://api.frankfurter.dev/v1"
# ECB publishes no rates on weekends and TARGET holidays; look back this far for the last published one
LOOKBACK_DAYS = 7

log = logging.getLogger(__name__)

# fetch(base, symbols, start, end) -> {"2026-08-03": {"USD": 1.1535, ...}, ...}
Fetcher = Callable[[str, list[str], date, date], dict[str, dict[str, float]]]


def fetch_ecb(base: str, symbols: list[str], start: date, end: date) -> dict[str, dict[str, float]]:
    url = f"{API}/{start.isoformat()}..{end.isoformat()}"
    response = requests.get(url, params={"base": base, "symbols": ",".join(symbols)}, timeout=20)
    response.raise_for_status()
    return response.json()["rates"]


class RateTable:
    """1 unit of `base` = rate units of currency, per publication day."""

    def __init__(self, base: str, rates: dict[str, dict[str, float]]):
        self.base = base
        self.rates = rates

    def rate(self, currency: str, day: date) -> float:
        if currency == self.base:
            return 1.0
        for back in range(LOOKBACK_DAYS + 1):
            published = self.rates.get((day - timedelta(days=back)).isoformat(), {})
            if currency in published:
                return published[currency]
        raise LookupError(
            f"no {self.base}/{currency} rate within {LOOKBACK_DAYS} days before {day}"
        )


def load_rates(
    base: str,
    currencies: set[str],
    start: date,
    end: date,
    cache: Path | None = None,
    offline: bool = False,
    fetch: Fetcher = fetch_ecb,
) -> RateTable:
    symbols = sorted(currencies - {base})
    if not symbols:
        return RateTable(base, {})
    first = start - timedelta(days=LOOKBACK_DAYS)
    cached = _read_cache(cache)
    if _covers(cached, base, symbols, first, end):
        log.info("FX: using cached ECB rates from %s", cache)
        return RateTable(base, cached["rates"])
    if offline:
        raise LookupError(
            f"offline mode: {cache} has no {base}->{symbols} rates for {first}..{end}"
        )

    log.info("FX: downloading ECB rates %s->%s for %s..%s", base, ",".join(symbols), first, end)
    rates = fetch(base, symbols, first, end)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        payload = {"base": base, "symbols": symbols, "start": str(first), "end": str(end)}
        cache.write_text(json.dumps({**payload, "rates": rates}, indent=1, sort_keys=True))
    return RateTable(base, rates)


def convert(lines: pd.DataFrame, table: RateTable) -> pd.DataFrame:
    """Adds fx_rate and amount_<base> columns."""
    out = lines.copy()
    out["fx_rate"] = [table.rate(c, d.date()) for c, d in zip(out["currency"], out["date"])]
    out[f"amount_{table.base.lower()}"] = (out["amount"] / out["fx_rate"]).round(2)
    return out


def _read_cache(cache: Path | None) -> dict | None:
    if not cache or not cache.exists():
        return None
    try:
        return json.loads(cache.read_text())
    except json.JSONDecodeError:
        log.warning("FX: ignoring unreadable cache %s", cache)
        return None


def _covers(cached: dict | None, base: str, symbols: list[str], start: date, end: date) -> bool:
    if not cached or cached.get("base") != base:
        return False
    return (
        set(symbols) <= set(cached.get("symbols", []))
        and cached["start"] <= str(start)
        and cached["end"] >= str(end)
    )
