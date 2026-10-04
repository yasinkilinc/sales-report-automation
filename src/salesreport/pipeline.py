"""read -> clean -> de-duplicate -> convert currency -> write report."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from salesreport import fx
from salesreport.clean import clean, drop_duplicates
from salesreport.load import load_config, read_source
from salesreport.report import Quality, kpis, write_report

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Result:
    lines: pd.DataFrame
    issues: pd.DataFrame
    quality: Quality
    kpis: dict[str, float]


def run(
    config_path: Path,
    input_dir: Path,
    output: Path,
    rates_cache: Path | None = None,
    offline: bool = False,
    fetch: fx.Fetcher = fx.fetch_ecb,
) -> Result:
    config = load_config(config_path)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input folder not found: {input_dir}")

    valid, issues, rows_read = [], [], 0
    for source in config.sources:
        raw = read_source(source, input_dir)
        rows_read += len(raw)
        good, bad = clean(raw, source)
        valid.append(good)
        issues.append(bad)
    lines = pd.concat(valid, ignore_index=True)
    if lines.empty:
        raise ValueError(f"no valid order lines found in {input_dir}")
    lines, duplicates = drop_duplicates(lines)
    rejected = pd.concat(issues, ignore_index=True)

    table = fx.load_rates(
        config.currency,
        set(lines["currency"]),
        lines["date"].min().date(),
        lines["date"].max().date(),
        cache=rates_cache,
        offline=offline,
        fetch=fetch,
    )
    lines = fx.convert(lines, table)

    quality = Quality(rows_read=rows_read, duplicates=len(duplicates), rejected=len(rejected))
    all_issues = pd.concat([rejected, duplicates], ignore_index=True)
    write_report(lines, all_issues, config.currency, quality, output)
    return Result(lines, all_issues, quality, kpis(lines, config.currency))
