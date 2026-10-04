"""Command line entry point: `salesreport --input data/sample --output out/sales_report.xlsx`."""

import argparse
import logging
import sys
from pathlib import Path

import requests

from salesreport.pipeline import run

log = logging.getLogger("salesreport")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="salesreport",
        description="Merge sales exports, convert currencies and write an Excel report.",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("sources.toml"), help="source definitions"
    )
    parser.add_argument("--input", type=Path, required=True, help="folder with the export files")
    parser.add_argument("--output", type=Path, default=Path("out/sales_report.xlsx"))
    parser.add_argument("--rates-cache", type=Path, default=Path("out/fx_rates.json"))
    parser.add_argument("--offline", action="store_true", help="use cached FX rates only")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    try:
        result = run(args.config, args.input, args.output, args.rates_cache, args.offline)
    except (FileNotFoundError, ValueError, LookupError, requests.RequestException) as error:
        log.error("%s", error)
        return 1

    q = result.quality
    log.info(
        "%s rows read, %s duplicates removed, %s rows rejected",
        f"{q.rows_read:,}",
        q.duplicates,
        q.rejected,
    )
    for label, value in result.kpis.items():
        log.info("%-22s %s", label, f"{value:,.2f}" if isinstance(value, float) else f"{value:,}")
    log.info("report written to %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
