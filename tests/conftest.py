from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FAKE_RATES = {"GBP": 0.85, "USD": 1.10}


def fake_fetch(base, symbols, start, end):
    """Weekday rates only, like the ECB. Counts calls so tests can check the cache."""
    fake_fetch.calls += 1
    days = (start + timedelta(days=i) for i in range((end - start).days + 1))
    return {d.isoformat(): {s: FAKE_RATES[s] for s in symbols} for d in days if d.weekday() < 5}


fake_fetch.calls = 0


@pytest.fixture
def fetch():
    fake_fetch.calls = 0
    return fake_fetch


@pytest.fixture
def config_path() -> Path:
    return ROOT / "sources.toml"


@pytest.fixture
def sample_dir() -> Path:
    return ROOT / "data" / "sample"


@pytest.fixture
def weekend() -> date:
    return date(2026, 8, 8)  # Saturday
